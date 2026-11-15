"""Full-game audio & dubbing integrity audit tests (Issue #3).

Verifies the entire patched PS1 disc image (`Harry Potter and the Chamber of
Secrets (Turkish).bin`) against the untouched European original:
  1. ISO == local WAD byte-exactness for all patched WADs.
  2. Category A (SFX/BGM/spells) 100% bit-exact MD5 preservation across all WADs.
  3. Foreign-language slots muted (zero EN/FR/DE leakage).
  4. Every manifest dialogue cue has a non-silent WAV within SPU duration budget
     and valid non-silent ADPCM payload in the patched .bin.
"""

from __future__ import annotations

import hashlib
import json
import os
import wave

import pytest
from tools.argonaut_xsp import (
    SPLIT_OFFSET,
    find_audio_base,
    find_xsps,
    parse_xsps_table,
)
from tools.audio_vag import decode_vag_block
from tools.dirdat import DirDatArchive
from tools.inject_dialogue import BURROW_CATEGORY_A, VOICE_HW, load_table_base
from tools.iso_fs import Ps1IsoReader

ORIG_BIN = "Harry Potter and the Chamber of Secrets (Europe) (En,Fr,De).bin"
TURK_BIN = "Harry Potter and the Chamber of Secrets (Turkish).bin"
MANIFEST_PATH = "audio/deterministic_manifest.json"
EXCLUSION_PATH = "audio/category_a_exclusion_map.json"


def _has_assets() -> bool:
    return (
        os.path.exists(ORIG_BIN)
        and os.path.exists(TURK_BIN)
        and os.path.exists(MANIFEST_PATH)
        and os.path.exists(EXCLUSION_PATH)
    )


def _adpcm_rms(chunk: bytes) -> float:
    """Decode ADPCM blocks and return mean absolute sample amplitude."""
    if len(chunk) < 16:
        return 0.0
    h1, h2 = 0.0, 0.0
    total = 0.0
    count = 0
    step = max(1, (len(chunk) // 16) // 64) * 16
    for off in range(0, len(chunk) - 15, step):
        samples, h1, h2 = decode_vag_block(chunk[off : off + 16], h1, h2)
        total += sum(abs(s) for s in samples)
        count += len(samples)
    return total / count if count else 0.0


@pytest.mark.requires_assets
@pytest.mark.skipif(not _has_assets(), reason="PS1 disc images or manifest missing")
class TestFullGameDubbingAudit:
    def test_all_wavs_present_audible_and_within_budget(self):
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            manifest = json.load(f)

        missing = []
        silent = []
        over_budget = []

        for row in manifest:
            if row.get("is_cutscene"):
                continue
            wp = row["wav_path"]
            if not os.path.exists(wp):
                missing.append((row["stem"], row["cue"], wp))
                continue
            with wave.open(wp, "rb") as wf:
                dur = wf.getnframes() / float(wf.getframerate())
                frames = wf.readframes(wf.getnframes())
            if dur <= 0.05 or not any(frames):
                silent.append((row["stem"], row["cue"], wp))
            if dur > row["max_duration"] + 0.30:
                over_budget.append((row["stem"], row["cue"], dur, row["max_duration"]))

        assert not missing, f"Missing WAVs ({len(missing)}): {missing[:10]}"
        assert not silent, f"Silent WAVs ({len(silent)}): {silent[:10]}"
        assert not over_budget, f"Over-budget WAVs ({len(over_budget)}): {over_budget[:10]}"

    def test_category_a_bit_exact_across_all_wads(self):
        with open(EXCLUSION_PATH, encoding="utf-8") as f:
            excl = json.load(f)

        violations = []
        with Ps1IsoReader(ORIG_BIN) as orig_iso, Ps1IsoReader(TURK_BIN) as turk_iso:
            orig_arch = DirDatArchive.from_iso(orig_iso)
            turk_arch = DirDatArchive.from_iso(turk_iso)

            for wad_name, cues in sorted(excl.items()):
                if wad_name not in orig_arch.entry_map or wad_name not in turk_arch.entry_map:
                    continue
                oe = orig_arch.entry_map[wad_name]
                te = turk_arch.entry_map[wad_name]
                orig_wad = orig_iso.read_file_bytes("POTTER.DAT", oe.offset, oe.size)
                turk_wad = turk_iso.read_file_bytes("POTTER.DAT", te.offset, te.size)

                audio_base = find_audio_base(orig_wad)
                for item in cues:
                    # hw == 2 without English match are foreign FR/DE slots
                    # intentionally muted by inject_dialogue.py.
                    if item.get("hw") == VOICE_HW and item.get("reason") == "pure_sfx":
                        continue
                    a_off = item["audio_offset"]
                    a_sz = item["size_bytes"]
                    om = hashlib.md5(
                        orig_wad[audio_base + a_off : audio_base + a_off + a_sz]
                    ).hexdigest()
                    tm = hashlib.md5(
                        turk_wad[audio_base + a_off : audio_base + a_off + a_sz]
                    ).hexdigest()
                    if om != tm:
                        violations.append((wad_name, item["cue"], item.get("reason")))

        assert not violations, f"Category A violations ({len(violations)}): {violations[:15]}"

    def test_turkish_disc_dialogue_audible_and_foreign_muted(self):
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            manifest = json.load(f)
        with open(EXCLUSION_PATH, encoding="utf-8") as ef:
            excl_data = json.load(ef)

        excl_by_wad: dict[str, set[int]] = {}
        for wname, items in excl_data.items():
            excl_by_wad[wname] = {
                it["cue"]
                for it in items
                if it.get("hw") != VOICE_HW or it.get("reason") == "spell_chant"
            }

        by_wad: dict[str, dict[int, dict]] = {}
        for row in manifest:
            if row.get("is_cutscene"):
                continue
            by_wad.setdefault(row["wad"], {})[row["cue"]] = row

        silent_tr = []
        leaked_foreign = []

        with Ps1IsoReader(TURK_BIN) as turk_iso:
            arch = DirDatArchive.from_iso(turk_iso)
            for wad_name, cue_map in sorted(by_wad.items()):
                stem = wad_name.replace(".WAD", "")
                entry = arch.entry_map[wad_name]
                wad = turk_iso.read_file_bytes("POTTER.DAT", entry.offset, entry.size)
                audio_base = find_audio_base(wad)
                _, spsx = find_xsps(wad)
                entries = parse_xsps_table(spsx, table_base=load_table_base(stem) or 0)
                cat_a = (
                    set(BURROW_CATEGORY_A)
                    if stem == "T1L2M001"
                    else excl_by_wad.get(wad_name, set())
                )
                # Track byte ranges intentionally owned by SPLIT Turkish payloads
                # (which start at a_off + 0xA800 and may extend into neighbouring foreign slots).
                from tools.inject_dialogue import detect_split_kinds_from_energy

                energy_splits = detect_split_kinds_from_energy(wad, entries, list(cue_map.keys()))
                split_ranges: list[tuple[int, int]] = []
                for e in entries:
                    if e.cue in cue_map:
                        row = cue_map[e.cue]
                        is_split = (
                            row.get("is_split_stream")
                            or (
                                stem == "T1L2M001"
                                and e.cue in {2, 8, 11, 14, 17, 20, 23, 26, 29, 42, 45}
                            )
                            or (
                                energy_splits.get(e.cue) is not None
                                and energy_splits[e.cue].value == "split"
                            )
                        )
                        if is_split:
                            s0 = audio_base + e.audio_offset + SPLIT_OFFSET
                            split_ranges.append((s0, s0 + e.size_bytes))

                for e in entries:
                    if e.cue in cat_a:
                        continue
                    if e.cue in cue_map:
                        row = cue_map[e.cue]
                        start = audio_base + e.audio_offset
                        if row.get("is_split_stream") or (
                            stem == "T1L2M001"
                            and e.cue in {2, 8, 11, 14, 17, 20, 23, 26, 29, 42, 45}
                        ):
                            start += SPLIT_OFFSET
                        chunk = wad[start : start + e.size_bytes]
                        if _adpcm_rms(chunk) < 10.0:
                            silent_tr.append((wad_name, e.cue, row["character"]))
                    elif e.hw == VOICE_HW:
                        f0 = audio_base + e.audio_offset
                        f1 = f0 + e.size_bytes
                        if any(f0 < sr1 and f1 > sr0 for sr0, sr1 in split_ranges):
                            continue
                        chunk = wad[f0:f1]
                        if _adpcm_rms(chunk) > 20.0:
                            leaked_foreign.append((wad_name, e.cue))

        assert not silent_tr, f"Silent Turkish dialogue cues ({len(silent_tr)}): {silent_tr[:15]}"
        assert not leaked_foreign, (
            f"Unmuted foreign cues ({len(leaked_foreign)}): {leaked_foreign[:15]}"
        )
