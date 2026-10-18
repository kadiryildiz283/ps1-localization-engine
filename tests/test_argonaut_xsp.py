"""Unit tests for Argonaut XSPS / SPU helpers (no game assets required)."""

import struct

import pytest
from tools.argonaut_xsp import (
    SPLIT_OFFSET,
    StreamKind,
    XspsEntry,
    build_slot_payload,
    classify_stream,
    duration_budget,
    find_audio_base,
    find_xsps,
    find_xsps_table_base,
    make_silence,
    max_samples_for_size,
    pack_p2,
    pad_vag_to_size,
    parse_xsps_table,
    split_detection_from_energy,
    sr_raw_to_hz,
    table_entry_bytes,
    write_point_offset,
)
from tools.inject_dialogue import (
    BURROW_FOREIGN_CUES,
    BURROW_SPLIT_CUES,
    BURROW_UNSPLIT_CUES,
    burrow_expected_kind,
)

# --- sample-rate register ------------------------------------------------


def test_sr_raw_22050():
    assert sr_raw_to_hz(0x0800) == 22050


def test_sr_raw_16000():
    assert sr_raw_to_hz(0x05CE) == 16000


def test_sr_raw_zero_defaults_to_22050():
    assert sr_raw_to_hz(0) == 22050


# --- SPU math ------------------------------------------------------------


def test_max_samples_block_math():
    assert max_samples_for_size(16) == 28
    assert max_samples_for_size(51200) == (51200 // 16) * 28


def test_duration_budget_burrow_cue02():
    # 51200 bytes @ 22050 Hz → 4.063 s (matches remediation table)
    assert duration_budget(51200, 22050) == pytest.approx(4.063, abs=0.01)


def test_duration_budget_rejects_bad_rate():
    assert duration_budget(51200, 0) == 0.0


# --- silence / padding ---------------------------------------------------


def test_make_silence_zero():
    assert make_silence(0) == b""


def test_make_silence_end_flag():
    data = make_silence(32, end_with_flag1=True)
    assert len(data) == 32
    assert data[16] == 0x00  # mid block flag
    assert data[17] == 0x01  # terminal mute


def test_make_silence_requires_alignment():
    with pytest.raises(ValueError):
        make_silence(15)


def test_pad_vag_exact():
    vag = b"\x00" * 16
    out = pad_vag_to_size(vag, 48)
    assert len(out) == 48
    assert out[-15] == 0x01


def test_pad_vag_truncates_with_terminal():
    vag = b"\x00" * 64
    out = pad_vag_to_size(vag, 32)
    assert len(out) == 32
    assert out[-15] == 0x01


# --- XSPS parse ----------------------------------------------------------


def _make_entry(a_off, p2, p3, a_sz):
    return struct.pack("<IIII", a_off, p2, p3, a_sz)


def test_parse_xsps_table_basic():
    payload = _make_entry(0x1000, pack_p2(), 0, 51200) + _make_entry(0x2000, pack_p2(), 0, 32768)
    entries = parse_xsps_table(payload, table_base=0)
    assert len(entries) == 2
    assert entries[0].audio_offset == 0x1000
    assert entries[0].size_bytes == 51200
    assert entries[0].sample_rate == 22050
    assert entries[0].hw == 2
    assert entries[0].table_entry_offset == 0
    assert entries[1].table_entry_offset == 16


def test_parse_xsps_stops_at_sentinel():
    payload = _make_entry(0x1000, pack_p2(), 0, 64) + _make_entry(0xFFFFFFFF, 0, 0, 0)
    entries = parse_xsps_table(payload, table_base=0)
    assert len(entries) == 1


def test_find_table_base_burrow_header_layout():
    header = bytearray(0x3F8)
    struct.pack_into("<I", header, 0x3F0, 2)
    struct.pack_into("<I", header, 0x3F4, SPLIT_OFFSET)
    payload = (
        bytes(header)
        + _make_entry(0x1000, pack_p2(), 0, 64)
        + _make_entry(0x2000, pack_p2(), 0, 64)
    )
    assert find_xsps_table_base(payload) == 0x3F8
    entries = parse_xsps_table(payload)
    assert len(entries) == 2
    assert entries[0].table_entry_offset == 0x3F8


def test_find_table_base_scan_without_header():
    payload = b"".join(_make_entry(0x1000 * (i + 1), pack_p2(), 0, 64) for i in range(8))
    assert find_xsps_table_base(payload) == 0


def test_find_audio_base_rounds_to_sector():
    # ' DNE' at offset 100 → base = 2048
    wad = b"\x00" * 100 + b" DNE" + b"\x00" * 4000
    assert find_audio_base(wad) == 2048


def test_find_xsps_roundtrip():
    payload = _make_entry(0x10, pack_p2(), 0, 64)
    wad = b"XXXX" + b"XSPS" + struct.pack("<I", len(payload)) + payload + b"TAIL"
    off, got = find_xsps(wad)
    assert off == 4 + 8  # 'XSPS' at 4, 8-byte header, then payload
    assert got == payload


# --- classification (Burrow map regression) ------------------------------


def _entry(cue, size, sr_raw=0x0800, hw=2):
    return XspsEntry(
        cue=cue,
        table_entry_offset=cue * 16,
        audio_offset=0x1000 * cue,
        p2=pack_p2(hw=hw, sr_raw=sr_raw),
        p3=0,
        size_bytes=size,
    )


def test_classify_requires_evidence_for_split():
    e = _entry(2, 51200)
    # Without explicit/energy evidence the conservative default is UNSPLIT.
    assert classify_stream(e, is_category_a=False) is StreamKind.UNSPLIT
    assert classify_stream(e, is_category_a=False, looks_split=True) is StreamKind.SPLIT
    assert classify_stream(e, is_category_a=False, explicit=StreamKind.SPLIT) is StreamKind.SPLIT


def test_classify_unsplit_when_too_small_for_prefix():
    e = _entry(5, 32768)
    assert classify_stream(e, is_category_a=False) is StreamKind.UNSPLIT


def test_classify_category_a_wins():
    e = _entry(0, 172032)
    assert classify_stream(e, is_category_a=True) is StreamKind.CATEGORY_A


def test_classify_foreign():
    e = _entry(3, 26624, sr_raw=0x05CE)
    assert classify_stream(e, is_category_a=False, is_foreign=True) is StreamKind.FOREIGN


def test_write_point_offsets():
    assert write_point_offset(StreamKind.SPLIT) == SPLIT_OFFSET
    assert write_point_offset(StreamKind.UNSPLIT) == 0
    assert write_point_offset(StreamKind.FOREIGN) == 0


# --- payload builder -----------------------------------------------------


def test_build_split_payload_layout():
    vag = b"\x00\x00" + b"\x00" * 14  # one block
    tr_budget = 32  # a_sz is the Turkish budget
    payload = build_slot_payload(vag, tr_budget, StreamKind.SPLIT)
    # prefix silence + Turkish budget
    assert len(payload) == SPLIT_OFFSET + tr_budget
    # German-region silence ends with 0x01 at block 2687
    assert payload[SPLIT_OFFSET - 15] == 0x01
    # Turkish starts at split point
    assert payload[SPLIT_OFFSET : SPLIT_OFFSET + 16] == vag[:16]


def test_build_unsplit_payload_pads():
    vag = b"\x00\x00" + b"\x00" * 14
    payload = build_slot_payload(vag, 48, StreamKind.UNSPLIT)
    assert len(payload) == 48
    assert payload[-15] == 0x01


def test_build_foreign_payload_is_silence():
    payload = build_slot_payload(b"", 64, StreamKind.FOREIGN)
    assert len(payload) == 64
    assert payload[-15] == 0x01


def test_build_split_rejects_empty_budget():
    with pytest.raises(ValueError):
        build_slot_payload(b"\x00" * 16, 0, StreamKind.SPLIT)


def test_build_category_a_rejected():
    with pytest.raises(ValueError):
        build_slot_payload(b"", 64, StreamKind.CATEGORY_A)


# --- energy-based split detection ---------------------------------------


def test_split_detect_quiet_prefix_loud_tail():
    assert split_detection_from_energy([0] * 100, [2000] * 100) is True


def test_split_detect_loud_prefix():
    assert split_detection_from_energy([2000] * 100, [2000] * 100) is False


def test_split_detect_empty_tail():
    assert split_detection_from_energy([0] * 10, []) is False


# --- Burrow fixture map --------------------------------------------------


def test_burrow_map_covers_dialogue_cues():
    assert 2 in BURROW_SPLIT_CUES
    assert 5 in BURROW_UNSPLIT_CUES
    assert 3 in BURROW_FOREIGN_CUES
    assert burrow_expected_kind(2) is StreamKind.SPLIT
    assert burrow_expected_kind(5) is StreamKind.UNSPLIT
    assert burrow_expected_kind(3) is StreamKind.FOREIGN
    assert burrow_expected_kind(0) is StreamKind.CATEGORY_A


def test_table_entry_bytes_roundtrip():
    e = _entry(7, 22528)
    raw = table_entry_bytes(e, hw=2, sr_raw=0x05CE)
    assert len(raw) == 16
    a_off, p2, p3, sz = struct.unpack("<IIII", raw)
    assert a_off == e.audio_offset
    assert sz == 22528
    assert p2 == pack_p2(hw=2, sr_raw=0x05CE)
