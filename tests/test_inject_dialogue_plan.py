"""Tests for centralized injector planning (no game assets)."""

from tools.argonaut_xsp import StreamKind, XspsEntry, pack_p2
from tools.inject_dialogue import (
    BURROW_SPLIT_CUES,
    BURROW_UNSPLIT_CUES,
    build_plan,
    burrow_expected_kind,
    burrow_forced_kinds,
    plan_matches_burrow,
)


def _e(cue, size, hw=2, sr_raw=0x0800):
    return XspsEntry(
        cue=cue,
        table_entry_offset=cue * 16,
        audio_offset=0x1000 * (cue + 1),
        p2=pack_p2(hw=hw, sr_raw=sr_raw),
        p3=0,
        size_bytes=size,
    )


def test_forced_kinds_win_over_size_heuristic():
    # Cue 39 in Burrow is 57344 B (size says SPLIT) but verified UNSPLIT.
    entries = [_e(39, 57344), _e(2, 51200)]
    forced = burrow_forced_kinds()
    plan = build_plan(
        entries,
        cat_a_cues=[],
        foreign_cues=[],
        dialogue={39: {"character": "ron", "tr": "x"}, 2: {"character": "ron", "tr": "y"}},
        forced_kinds=forced,
    )
    kinds = {p.entry.cue: p.kind for p in plan}
    assert kinds[39] is StreamKind.UNSPLIT
    assert kinds[2] is StreamKind.SPLIT


def test_plan_matches_burrow_fixture():
    # Synthetic entries with correct sizes from the verified table.
    sizes = {
        0: 172032,
        1: 151552,
        2: 51200,
        5: 32768,
        8: 59392,
        11: 88064,
        3: 26624,
        4: 40960,
        38: 751616,
        48: 3028992,
    }
    entries = [_e(cue, sz) for cue, sz in sizes.items()]
    plan = build_plan(
        entries,
        cat_a_cues=[0, 1, 38, 48],
        foreign_cues=[3, 4],
        dialogue={
            2: {"character": "ron"},
            5: {"character": "ron"},
            8: {"character": "ron"},
            11: {"character": "ron"},
        },
        forced_kinds=burrow_forced_kinds(),
    )
    assert plan_matches_burrow(plan) == []


def test_foreign_gets_write_offset_zero_but_is_muted():
    plan = build_plan(
        [_e(3, 26624, sr_raw=0x05CE)],
        cat_a_cues=[],
        foreign_cues=[3],
        dialogue={},
    )
    assert plan[0].kind is StreamKind.FOREIGN
    assert plan[0].write_offset == 0


def test_split_budget_is_full_asz():
    # a_sz is the Turkish budget at +0xA800; German prefix is extra.
    plan = build_plan(
        [_e(2, 51200)],
        cat_a_cues=[],
        foreign_cues=[],
        dialogue={2: {"character": "ron", "tr": "Merhaba Harry!", "wav_path": "x.wav"}},
        forced_kinds=burrow_forced_kinds(),
    )
    p = plan[0]
    assert p.kind is StreamKind.SPLIT
    assert p.tr_budget_bytes == 51200
    assert p.tr_budget_sec == 51200 / 16 * 28 / 22050


def test_burrow_expected_kind_helpers():
    assert burrow_expected_kind(2) is StreamKind.SPLIT
    assert burrow_expected_kind(5) is StreamKind.UNSPLIT
    assert 2 in BURROW_SPLIT_CUES and 5 in BURROW_UNSPLIT_CUES
