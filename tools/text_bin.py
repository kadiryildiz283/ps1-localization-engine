"""Encoder and Decoder for PS1 Harry Potter .BIN Language Files.

Handles dumping UI/system/card strings to editable UTF-8 JSON and compiling JSON
back into .BIN files with custom Caesar font encoding, dynamic length recalculation,
and repointing.
"""

import json
import os
import struct

# Custom glyph mappings for accented characters discovered in European release
ACCENT_TO_CODE = {
    "é": 0x00A3,
    "è": 0x00A2,
    "ü": 0x00B4,
    "ä": 0x009E,
    "à": 0x009A,
    "ö": 0x00AF,  # European font glyph for ö (glyph 246)
    "Ö": 0x0094,  # European font glyph for Ö (glyph 214)
    "Ü": 0x0098,  # European font glyph for Ü (glyph 220)
    "ç": 0x00A1,  # French/European font glyph for ç (glyph 231)
    "Ç": 0x008E,  # French/European font glyph for Ç (glyph 199)
    # Native Turkish glyphs custom injected into UNIF/FINU:
    "ı": 0x00A0,  # dotless i (replaces æ)
    "İ": 0x008D,  # dotted I (replaces Æ)
    "ş": 0x00B0,  # s with cedilla (replaces ø)
    "Ş": 0x0095,  # S with cedilla (replaces Ø)
    "ğ": 0x009D,  # g with breve (replaces ã)
    "Ğ": 0x008A,  # G with breve (replaces Ã)
}

CODE_TO_ACCENT = {v: k for k, v in ACCENT_TO_CODE.items()}

# Turkish character fallback mapping (when using standard European font)
TURKISH_FALLBACK = {
    "ı": "i",
    "İ": "I",
    "ş": "s",
    "Ş": "S",
    "ğ": "g",
    "Ğ": "G",
}


def decode_bin_string(raw_bytes: bytes) -> str:
    """Decode 16-bit word characters with Argonaut -1 lowercase Caesar shift."""
    chars = struct.unpack(f"<{len(raw_bytes) // 2}H", raw_bytes)
    result = []
    for c in chars:
        if c == 0:
            break
        if c in CODE_TO_ACCENT:
            result.append(CODE_TO_ACCENT[c])
        elif 0x60 <= c <= 0x79:  # Lowercase a-z are shifted by -1 (0x60='`' is 'a', 0x79='y' is 'z')
            result.append(chr(c + 1))
        elif 32 <= c <= 126:
            result.append(chr(c))
        else:
            result.append(f"\\u{c:04x}")
    return "".join(result)


def encode_bin_string(text: str, use_turkish_fallback: bool = True) -> bytes:
    """Encode UTF-8 text into 16-bit words with Argonaut -1 lowercase Caesar shift."""
    u16_words = []
    i = 0
    while i < len(text):
        # Support escape sequences like \u00a3
        if text[i : i + 2] == "\\u" and i + 6 <= len(text):
            try:
                code = int(text[i + 2 : i + 6], 16)
                u16_words.append(code)
                i += 6
                continue
            except ValueError:
                pass

        ch = text[i]
        i += 1

        if ch in ACCENT_TO_CODE:
            u16_words.append(ACCENT_TO_CODE[ch])
        elif use_turkish_fallback and ch in TURKISH_FALLBACK:
            fb = TURKISH_FALLBACK[ch]
            # Encoded ASCII
            if "a" <= fb <= "z":
                u16_words.append(ord(fb) - 1)
            else:
                u16_words.append(ord(fb))
        elif "a" <= ch <= "z":
            u16_words.append(ord(ch) - 1)
        elif 32 <= ord(ch) <= 126:
            u16_words.append(ord(ch))
        else:
            # Unhandled character, fallback to '?'
            u16_words.append(ord("?"))

    # Null terminator
    u16_words.append(0)
    return struct.pack(f"<{len(u16_words)}H", *u16_words)


def dump_bin_file(bin_data: bytes) -> list[dict]:
    """Parse a .BIN language file into a structured list of string entries."""
    total_len = struct.unpack("<I", bin_data[:4])[0]
    pos = 4
    entries = []
    idx = 0

    while pos < len(bin_data):
        if pos + 4 > len(bin_data):
            break
        chunk_len = struct.unpack("<I", bin_data[pos : pos + 4])[0]
        pos += 4
        if chunk_len == 0 or pos + chunk_len > len(bin_data):
            break
        chunk = bin_data[pos : pos + chunk_len]
        pos += chunk_len
        decoded = decode_bin_string(chunk)
        entries.append({
            "id": idx,
            "original_length": chunk_len,
            "text": decoded
        })
        idx += 1

    return entries


def compile_bin_file(entries: list[dict], use_turkish_fallback: bool = True) -> bytes:
    """Compile structured string entries back into a binary .BIN language file.
    
    Dynamically recalculates all chunk lengths and total file length, allowing arbitrary
    string expansions without crashing.
    """
    payload = bytearray()
    for entry in entries:
        text = entry.get("translation", entry.get("text", ""))
        encoded = encode_bin_string(text, use_turkish_fallback=use_turkish_fallback)
        payload.extend(struct.pack("<I", len(encoded)))
        payload.extend(encoded)

    total_len = len(payload)
    return struct.pack("<I", total_len) + bytes(payload)


def export_bin_to_json(bin_path: str, json_path: str):
    with open(bin_path, "rb") as f:
        data = f.read()
    entries = dump_bin_file(data)
    os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"Exported {len(entries)} strings to {json_path}")


def import_json_to_bin(json_path: str, bin_output_path: str, use_turkish_fallback: bool = True):
    with open(json_path, encoding="utf-8") as f:
        entries = json.load(f)
    bin_data = compile_bin_file(entries, use_turkish_fallback=use_turkish_fallback)
    os.makedirs(os.path.dirname(os.path.abspath(bin_output_path)), exist_ok=True)
    with open(bin_output_path, "wb") as f:
        f.write(bin_data)
    print(f"Compiled {len(entries)} strings to {bin_output_path} ({len(bin_data)} bytes)")
