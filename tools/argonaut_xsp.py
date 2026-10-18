"""Argonaut XSPS / SPU ADPCM pure helpers.

Asset-free math and classification used by the centralized dialogue injector.
No file I/O of game data here — callers pass bytes/ints.
"""

from __future__ import annotations

import struct
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum

# --- SPU hardware constants (Sony ADPCM) ---------------------------------

ADPCM_BLOCK_BYTES = 16
ADPCM_SAMPLES_PER_BLOCK = 28
SILENCE_MID_BLOCK = b"\x00" * 16
SILENCE_MUTE_BLOCK = b"\x00\x01" + b"\x00" * 14

# Argonaut multi-language shared stream split point (bytes from a_off).
SPLIT_OFFSET = 0xA800
SPLIT_OFFSET_BLOCKS = SPLIT_OFFSET // ADPCM_BLOCK_BYTES  # 2688

# p2 low half: sample-rate register. 44100 * raw / 4096 = Hz.
SR_RAW_22050 = 0x0800  # -> 22050 Hz
SR_RAW_16000 = 0x05CE  # -> 16000 Hz (French secondary slots)
HW_VOICE = 2


class StreamKind(str, Enum):
    """How an XSPS cue must be written for a Turkish localization."""

    CATEGORY_A = "category_a"  # SFX / BGM / spells — never touch
    SPLIT = "split"  # silence 0xA800, TR audio at +0xA800
    UNSPLIT = "unsplit"  # TR audio at +0x0000
    FOREIGN = "foreign"  # mute descriptor (FR/DE leftover)


@dataclass(frozen=True)
class XspsEntry:
    """One 16-byte XSPS table descriptor: (a_off, p2, p3, a_sz)."""

    cue: int
    table_entry_offset: int
    audio_offset: int
    p2: int
    p3: int
    size_bytes: int

    @property
    def hw(self) -> int:
        return (self.p2 >> 16) & 0xFFFF

    @property
    def sr_raw(self) -> int:
        return self.p2 & 0xFFFF

    @property
    def sample_rate(self) -> int:
        return sr_raw_to_hz(self.sr_raw)

    @property
    def max_samples(self) -> int:
        return (self.size_bytes // ADPCM_BLOCK_BYTES) * ADPCM_SAMPLES_PER_BLOCK

    @property
    def max_duration(self) -> float:
        if self.sample_rate <= 0:
            return 0.0
        return self.max_samples / float(self.sample_rate)


def sr_raw_to_hz(sr_raw: int) -> int:
    """Convert SPSX p2 sample-rate register to Hz (Argonaut formula)."""
    if sr_raw == SR_RAW_16000:
        return 16000
    if sr_raw <= 0:
        return 22050
    calc = round(44100 * sr_raw / 4096)
    return calc if 8000 <= calc <= 48000 else 22050


def hz_to_sr_raw_22050() -> int:
    return SR_RAW_22050


def max_samples_for_size(size_bytes: int) -> int:
    return (size_bytes // ADPCM_BLOCK_BYTES) * ADPCM_SAMPLES_PER_BLOCK


def duration_budget(size_bytes: int, sample_rate: int) -> float:
    """Playable seconds that fit in an SPU slot (full block budget)."""
    if sample_rate <= 0 or size_bytes < ADPCM_BLOCK_BYTES:
        return 0.0
    return max_samples_for_size(size_bytes) / float(sample_rate)


def make_silence(num_bytes: int, *, end_with_flag1: bool = True) -> bytes:
    """SPU silence; optionally terminate with the 0x01 mute block."""
    if num_bytes < 0 or num_bytes % ADPCM_BLOCK_BYTES != 0:
        raise ValueError(f"silence length must be >=0 and 16-aligned, got {num_bytes}")
    if num_bytes == 0:
        return b""
    blocks = num_bytes // ADPCM_BLOCK_BYTES
    if end_with_flag1:
        return SILENCE_MID_BLOCK * (blocks - 1) + SILENCE_MUTE_BLOCK
    return SILENCE_MID_BLOCK * blocks


def pad_vag_to_size(vag: bytes, size_bytes: int) -> bytes:
    """Pad/truncate encoded VAG to exactly size_bytes with terminal mute."""
    if size_bytes % ADPCM_BLOCK_BYTES != 0:
        raise ValueError(f"slot size must be 16-aligned, got {size_bytes}")
    if len(vag) > size_bytes:
        out = bytearray(vag[:size_bytes])
        out[-15] = 0x01
        return bytes(out)
    pad = size_bytes - len(vag)
    blocks = pad // ADPCM_BLOCK_BYTES
    if blocks > 0:
        return vag + SILENCE_MID_BLOCK * (blocks - 1) + SILENCE_MUTE_BLOCK
    # pad == 0
    return vag


def parse_xsps_table(spsx_payload: bytes, *, max_cues: int = 2000) -> list[XspsEntry]:
    """Parse XSPS payload (after 8-byte header) into descriptors.

    Stops at sentinel 0xFFFFFFFF audio offsets or undersized slots.
    """
    entries: list[XspsEntry] = []
    for cue in range(max_cues):
        e_off = cue * 16
        if e_off + 16 > len(spsx_payload):
            break
        a_off, p2, p3, a_sz = struct.unpack_from("<IIII", spsx_payload, e_off)
        if a_off == 0xFFFFFFFF or a_sz < 32:
            break
        entries.append(
            XspsEntry(
                cue=cue,
                table_entry_offset=e_off,
                audio_offset=a_off,
                p2=p2,
                p3=p3,
                size_bytes=a_sz,
            )
        )
    return entries


def find_audio_base(wad_bytes: bytes) -> int:
    """Audio region start: ' DNE' marker rounded up to 2048-byte sector."""
    dne = wad_bytes.find(b" DNE")
    if dne == -1:
        raise ValueError("WAD missing ' DNE' audio marker")
    return (dne + 2047) // 2048 * 2048


def find_xsps(wad_bytes: bytes) -> tuple[int, bytes]:
    """Return (spsx_payload_abs_offset, payload). Payload starts after 8-byte header."""
    pos = wad_bytes.find(b"XSPS")
    if pos == -1:
        raise ValueError("WAD missing XSPS chunk")
    size = struct.unpack_from("<I", wad_bytes, pos + 4)[0]
    return pos + 8, bytes(wad_bytes[pos + 8 : pos + 8 + size])


def pack_p2(*, hw: int = HW_VOICE, sr_raw: int = SR_RAW_22050) -> int:
    return ((hw & 0xFFFF) << 16) | (sr_raw & 0xFFFF)


def classify_stream(
    entry: XspsEntry,
    *,
    is_category_a: bool,
    is_foreign: bool = False,
    explicit: StreamKind | None = None,
    looks_split: bool | None = None,
) -> StreamKind:
    """Decide write strategy for one cue.

    Priority:
      1. Category A (SFX/BGM/spell) — never touch
      2. Explicit override (fixture / energy detection / manual map)
      3. Foreign language leftovers — mute
      4. Size heuristic fallback (SPLIT only if slot holds 0xA800 + one block)

    The size heuristic alone is NOT sufficient: Burrow cue 39 is 57344 B
    (would fit a split prefix) but is an UNSPLIT short line. Real detection
    must look at original ADPCM energy around the 0xA800 boundary.
    """
    if is_category_a:
        return StreamKind.CATEGORY_A
    if explicit is not None:
        return explicit
    if looks_split is True:
        return StreamKind.SPLIT
    if looks_split is False:
        return StreamKind.UNSPLIT
    if is_foreign:
        return StreamKind.FOREIGN
    if entry.size_bytes >= SPLIT_OFFSET + ADPCM_BLOCK_BYTES:
        return StreamKind.SPLIT
    return StreamKind.UNSPLIT


def write_point_offset(kind: StreamKind) -> int:
    """Byte offset from a_off where Turkish ADPCM must start."""
    return SPLIT_OFFSET if kind is StreamKind.SPLIT else 0


def build_slot_payload(
    vag_audio: bytes,
    size_bytes: int,
    kind: StreamKind,
) -> bytes:
    """Build the exact bytes to place at audio_base + a_off for this slot."""
    if size_bytes % ADPCM_BLOCK_BYTES != 0:
        raise ValueError(f"size_bytes must be 16-aligned, got {size_bytes}")

    if kind is StreamKind.FOREIGN:
        return make_silence(size_bytes, end_with_flag1=True)

    if kind is StreamKind.CATEGORY_A:
        raise ValueError("Category A slots must not be rebuilt; preserve original bytes")

    if kind is StreamKind.SPLIT:
        if size_bytes < SPLIT_OFFSET + ADPCM_BLOCK_BYTES:
            raise ValueError(f"split slot too small: {size_bytes}")
        tr_region = size_bytes - SPLIT_OFFSET
        tr = pad_vag_to_size(vag_audio, tr_region)
        prefix = make_silence(SPLIT_OFFSET, end_with_flag1=True)
        assert prefix[SPLIT_OFFSET - 15] == 0x01  # block 2687 flag
        payload = prefix + tr
        assert len(payload) == size_bytes
        return payload

    # UNSPLIT
    return pad_vag_to_size(vag_audio, size_bytes)


def split_detection_from_energy(
    pcm_prefix: Sequence[int],
    pcm_tail: Sequence[int],
    *,
    silence_threshold: int = 300,
    min_tail_ratio: float = 0.5,
) -> bool:
    """Heuristic split-stream detector from original ADPCM energy profile.

    A shared DE/EN stream has quiet/silence in the first 0xA800 bytes (German
    end flag region) and speech energy after the split point.
    """
    if not pcm_tail:
        return False
    if not pcm_prefix:
        return True

    def energy(samples: Sequence[int]) -> float:
        return sum(abs(s) for s in samples) / float(len(samples))

    pre_e = energy(pcm_prefix)
    tail_e = energy(pcm_tail)
    if pre_e >= silence_threshold:
        return False
    return tail_e >= silence_threshold and tail_e >= pre_e * 4 * min_tail_ratio


def table_entry_bytes(
    entry: XspsEntry,
    *,
    hw: int = HW_VOICE,
    sr_raw: int = SR_RAW_22050,
    size_bytes: int | None = None,
) -> bytes:
    """Serialize a replacement 16-byte XSPS descriptor."""
    sz = entry.size_bytes if size_bytes is None else size_bytes
    return struct.pack("<IIII", entry.audio_offset, pack_p2(hw=hw, sr_raw=sr_raw), entry.p3, sz)


def summarize_plan(kinds: Iterable[StreamKind]) -> dict:
    counts = {k.value: 0 for k in StreamKind}
    for k in kinds:
        counts[k.value] += 1
    return counts
