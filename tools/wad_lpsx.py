"""Parser, Dumper, and Compiler with Dynamic Repointing for WAD LPSX sections.

Handles level-specific dialogue, cutscene text, and quest objectives.
Automatically recalculates all 32-bit pointers when strings expand or shrink,
preventing game crashes and buffer overflows.
"""

import json
import os
import struct

from tools.text_bin import decode_bin_string, encode_bin_string

LPSX_MAGIC = b"XSPL"
STRIDE_LANGS = 4  # 4 slots per entry: [English, French, German, Extra/Empty]


class LpsxRecord:
    def __init__(self, record_id: int, en: str, fr: str, de: str, extra: str):
        self.record_id = record_id
        self.en = en
        self.fr = fr
        self.de = de
        self.extra = extra

    def to_dict(self) -> dict:
        return {
            "id": self.record_id,
            "en": self.en,
            "fr": self.fr,
            "de": self.de,
            "tr": ""  # Ready for Turkish translation
        }


class WadLpsxHandler:
    def __init__(self, wad_bytes: bytes):
        self.raw_wad = bytearray(wad_bytes)
        self.lpsx_offset: int | None = None
        self.lpsx_size: int | None = None
        self.n_langs = 0
        self.n_records = 0
        self.records: list[LpsxRecord] = []
        self._find_and_parse_lpsx()

    def _find_and_parse_lpsx(self):
        pos = 4
        while pos + 8 <= len(self.raw_wad):
            tag = self.raw_wad[pos : pos + 4]
            size = struct.unpack("<I", self.raw_wad[pos + 4 : pos + 8])[0]
            if tag == LPSX_MAGIC:
                self.lpsx_offset = pos
                self.lpsx_size = size
                self._parse_payload(self.raw_wad[pos + 8 : pos + 8 + size])
                break
            if tag == b" DNE" or size == 0:
                break
            pos += 8 + size

    def _parse_payload(self, payload: bytes):
        if len(payload) < 12:
            return
        self.n_langs, self.n_records, pool_words = struct.unpack("<III", payload[:12])
        if self.n_records == 0:
            return

        total_ptrs = self.n_records * STRIDE_LANGS
        ptrs_end = 12 + total_ptrs * 4
        ptrs = struct.unpack(f"<{total_ptrs}I", payload[12:ptrs_end])

        str_pool_base = ptrs_end
        str_pool = payload[str_pool_base:]

        def read_str(offset: int) -> str:
            if offset >= len(str_pool):
                return ""
            cur = offset
            while cur + 2 <= len(str_pool):
                val = struct.unpack("<H", str_pool[cur : cur + 2])[0]
                cur += 2
                if val == 0:
                    break
            raw_chunk = str_pool[offset:cur]
            return decode_bin_string(raw_chunk)

        self.records = []
        for i in range(self.n_records):
            p0 = ptrs[i * STRIDE_LANGS + 0]
            p1 = ptrs[i * STRIDE_LANGS + 1]
            p2 = ptrs[i * STRIDE_LANGS + 2]
            p3 = ptrs[i * STRIDE_LANGS + 3]
            rec = LpsxRecord(
                record_id=i,
                en=read_str(p0),
                fr=read_str(p1),
                de=read_str(p2),
                extra=read_str(p3)
            )
            self.records.append(rec)

    def export_to_json(self, json_path: str):
        # Filter out empty records or export all
        data = [r.to_dict() for r in self.records]
        os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Exported {len(data)} dialogue/objective records to {json_path}")

    def rebuild_lpsx(self, translated_records: list[dict], target_lang: str = "en", use_turkish_fallback: bool = True) -> bytes:
        """Rebuild LPSX with dynamic repointing for all 4 slots per record."""
        new_ptrs = []
        new_pool = bytearray()

        # Helper to add string to pool and return its offset
        def add_to_pool(text: str) -> int:
            nonlocal new_pool
            if not text:
                # Share a single empty string offset or write empty string
                off = len(new_pool)
                new_pool.extend(b"\x00\x00")
                return off
            enc = encode_bin_string(text, use_turkish_fallback=use_turkish_fallback)
            off = len(new_pool)
            new_pool.extend(enc)
            return off

        # Shared empty string offset
        empty_str_off = add_to_pool("")

        for rec_dict in translated_records:
            rid = rec_dict["id"]
            orig = self.records[rid]

            tr_text = rec_dict.get("tr") or rec_dict.get("translation") or rec_dict.get("en", "")
            slot3_text = orig.extra

            p0 = add_to_pool(tr_text) if tr_text else empty_str_off
            # Share offset across all language slots (English, French, German) so Turkish plays in all modes
            p1 = p0
            p2 = p0
            p3 = add_to_pool(slot3_text) if slot3_text else empty_str_off

            new_ptrs.extend([p0, p1, p2, p3])

        # Pad pool to 4-byte boundary
        pad = (4 - (len(new_pool) % 4)) % 4
        if pad > 0:
            new_pool.extend(b"\x00" * pad)

        pool_words = len(new_pool) // 4
        header = struct.pack("<III", self.n_langs, len(translated_records), pool_words)
        ptrs_bytes = struct.pack(f"<{len(new_ptrs)}I", *new_ptrs)

        return header + ptrs_bytes + bytes(new_pool)

    def compile_wad_with_translations(self, translated_records: list[dict], output_wad_path: str, target_lang: str = "en") -> bytes:
        """Replace LPSX in WAD, repoint pointers, and update all section sizes."""
        new_lpsx_payload = bytearray(self.rebuild_lpsx(translated_records, target_lang=target_lang))

        # CRITICAL: Preserve original LPSX size by padding to keep all subsequent
        # streaming audio chunks (35MB VAG in END chunk) perfectly sector-aligned!
        if self.lpsx_size and len(new_lpsx_payload) < self.lpsx_size:
            pad_len = self.lpsx_size - len(new_lpsx_payload)
            new_lpsx_payload.extend(b"\x00" * pad_len)

        new_wad = bytearray()
        new_wad.extend(struct.pack("<I", 0))  # Placeholder for total size

        pos = 4
        while pos + 8 <= len(self.raw_wad):
            tag = self.raw_wad[pos : pos + 4]
            size = struct.unpack("<I", self.raw_wad[pos + 4 : pos + 8])[0]
            if tag == LPSX_MAGIC:
                new_wad.extend(tag)
                new_wad.extend(struct.pack("<I", len(new_lpsx_payload)))
                new_wad.extend(new_lpsx_payload)
            elif tag == b"FINU":
                from tools.font_finu import generate_turkish_finu
                orig_finu = bytes(self.raw_wad[pos + 8 : pos + 8 + size])
                tr_finu = generate_turkish_finu(orig_finu)
                new_wad.extend(tag)
                new_wad.extend(struct.pack("<I", len(tr_finu)))
                new_wad.extend(tr_finu)
            else:
                new_wad.extend(self.raw_wad[pos : pos + 8 + size])

            if tag == b" DNE" or size == 0:
                break
            pos += 8 + size

        # Update declared size in header (file_size - 4 + 0x800)
        final_size = len(new_wad)
        new_wad[0:4] = struct.pack("<I", final_size - 4 + 0x800)

        os.makedirs(os.path.dirname(os.path.abspath(output_wad_path)), exist_ok=True)
        with open(output_wad_path, "wb") as f:
            f.write(new_wad)

        print(f"Compiled WAD with repointed LPSX: {output_wad_path} ({len(new_wad)} bytes)")
        return bytes(new_wad)
