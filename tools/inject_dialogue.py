"""Centralized multi-cue / split-stream dialogue injector.

Generalizes the Burrow (T1L2M001) exact-split engine to any Argonaut WAD:

  * Category A (SFX/BGM/spells)  → 100% bit-exact preserved
  * Split-stream dialogue        → silence in [0x0000, 0xA800), TR at +0xA800
  * Unsplit dialogue             → TR at +0x0000
  * Foreign language leftovers   → hardware-muted silence (no EN/FR leakage)

CLI:
  python tools/inject_dialogue.py --plan --wad extracted/T1L2M001.WAD
  python tools/inject_dialogue.py --inject --wad extracted/T1L2M001.WAD \\
      --manifest audio/deterministic_manifest.json --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.argonaut_xsp import (
    ADPCM_BLOCK_BYTES,
    SPLIT_OFFSET,
    StreamKind,
    XspsEntry,
    build_slot_payload,
    classify_stream,
    duration_budget,
    find_audio_base,
    find_xsps,
    make_silence,
    parse_xsps_table,
    summarize_plan,
    table_entry_bytes,
    write_point_offset,
)

# Marker for dialogue slots: hardware flag 2 (in-game speech channel).
VOICE_HW = 2


@dataclass
class CuePlan:
    entry: XspsEntry
    kind: StreamKind
    character: str = ""
    line_hash: str = ""
    tr: str = ""
    wav_path: str = ""

    @property
    def write_offset(self) -> int:
        return write_point_offset(self.kind)

    @property
    def tr_budget_bytes(self) -> int:
        # SPLIT: a_sz is the Turkish budget at +0xA800 (German prefix is extra).
        # UNSPLIT: a_sz is the whole slot at +0x0000.
        return self.entry.size_bytes

    @property
    def tr_budget_sec(self) -> float:
        return duration_budget(self.tr_budget_bytes, self.entry.sample_rate)


def _md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def snapshot_category_a(
    wad: bytes, audio_base: int, entries: Sequence[XspsEntry], cat_a_cues: Sequence[int]
) -> dict[int, str]:
    by_cue = {e.cue: e for e in entries}
    out: dict[int, str] = {}
    for cue in cat_a_cues:
        e = by_cue.get(cue)
        if e is None:
            continue
        chunk = wad[audio_base + e.audio_offset : audio_base + e.audio_offset + e.size_bytes]
        out[cue] = _md5(chunk)
    return out


def verify_category_a(
    wad: bytes, audio_base: int, entries: Sequence[XspsEntry], baseline: dict[int, str]
) -> list[int]:
    by_cue = {e.cue: e for e in entries}
    violated = []
    for cue, digest in baseline.items():
        e = by_cue.get(cue)
        if e is None:
            continue
        chunk = wad[audio_base + e.audio_offset : audio_base + e.audio_offset + e.size_bytes]
        if _md5(chunk) != digest:
            violated.append(cue)
    return violated


def build_plan(
    entries: Sequence[XspsEntry],
    *,
    cat_a_cues: Sequence[int],
    foreign_cues: Sequence[int],
    dialogue: dict[int, dict] | None = None,
    forced_kinds: dict[int, StreamKind] | None = None,
) -> list[CuePlan]:
    """Classify every cue and attach dialogue metadata when available.

    `forced_kinds` wins over heuristics (use for verified fixtures such as
    the Burrow map, or for energy-based detection results).
    """
    cat_a = set(cat_a_cues)
    foreign = set(foreign_cues)
    dialogue = dialogue or {}
    forced_kinds = forced_kinds or {}
    plan: list[CuePlan] = []
    for e in entries:
        if e.cue in cat_a:
            kind = StreamKind.CATEGORY_A
        elif e.cue in forced_kinds:
            kind = forced_kinds[e.cue]
        elif e.cue in foreign:
            kind = StreamKind.FOREIGN
        elif e.hw == VOICE_HW and e.cue in dialogue:
            kind = classify_stream(e, is_category_a=False, is_foreign=False)
        elif e.hw != VOICE_HW:
            kind = StreamKind.FOREIGN
        else:
            kind = StreamKind.FOREIGN

        meta = dialogue.get(e.cue, {})
        plan.append(
            CuePlan(
                entry=e,
                kind=kind,
                character=meta.get("character", ""),
                line_hash=meta.get("line_hash", ""),
                tr=meta.get("tr", ""),
                wav_path=meta.get("wav_path", ""),
            )
        )
    return plan


def encode_wav_to_vag_bytes(wav_path: str, max_samples: int, target_sr: int) -> bytes:
    """Load mono WAV, trim silence, resample if needed, ADPCM-encode.

    Returns raw VAG bytes (16-byte blocks), without slot padding.
    """
    import wave

    import numpy as np
    from tools.audio_vag import encode_pcm_to_vag

    with wave.open(wav_path, "rb") as wf:
        sr = wf.getframerate()
        ch = wf.getnchannels()
        raw = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    if ch > 1:
        raw = raw[::ch]

    # Trim dead silence, keep 25 ms attack/decay margin.
    non_silent = np.where(np.abs(raw) > 300)[0]
    if len(non_silent) > 0:
        pad = int(sr * 0.025)
        start = max(0, non_silent[0] - pad)
        end = min(len(raw), non_silent[-1] + pad)
        raw = raw[start:end]

    if sr != target_sr:
        import subprocess

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "s16le",
            "-ar",
            str(sr),
            "-ac",
            "1",
            "-i",
            "-",
            "-ac",
            "1",
            "-ar",
            str(target_sr),
            "-f",
            "s16le",
            "-",
        ]
        res = subprocess.run(
            cmd, input=raw.tobytes(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True
        )
        raw = np.frombuffer(res.stdout, dtype=np.int16)

    if len(raw) > max_samples:
        raw = raw[:max_samples]

    return encode_pcm_to_vag(raw, loop=False)


def inject_wad(
    wad_bytes: bytes,
    plan: Sequence[CuePlan],
    *,
    dry_run: bool = False,
    cat_a_cues: Sequence[int] = (),
    table_base: int | None = None,
) -> tuple[bytes, dict]:
    """Apply plan to a WAD image. Returns (new_wad, report)."""
    wad = bytearray(wad_bytes)
    audio_base = find_audio_base(wad)
    spsx_off, spsx_payload = find_xsps(wad)
    entries = parse_xsps_table(spsx_payload, table_base=table_base)
    by_cue = {e.cue: e for e in entries}

    baseline = snapshot_category_a(wad, audio_base, entries, cat_a_cues)
    report = {
        "audio_base": audio_base,
        "injected": [],
        "muted": [],
        "skipped_missing_wav": [],
        "category_a_violations": [],
        "split_count": 0,
        "unsplit_count": 0,
        "foreign_count": 0,
    }

    # Pass 1: mute foreign language leftovers FIRST. SPLIT Turkish payloads
    # are written at a_off+0xA800 and may extend into neighbouring foreign
    # slots; those regions must already be silence-owned by us.
    for item in plan:
        if item.kind is not StreamKind.FOREIGN:
            continue
        e = by_cue.get(item.entry.cue, item.entry)
        payload = make_silence(e.size_bytes, end_with_flag1=True)
        wad[audio_base + e.audio_offset : audio_base + e.audio_offset + e.size_bytes] = payload
        wad[spsx_off + e.table_entry_offset + 4 : spsx_off + e.table_entry_offset + 8] = (
            table_entry_bytes(e, hw=VOICE_HW, sr_raw=0x05CE)[4:8]
        )
        report["muted"].append(e.cue)
        report["foreign_count"] += 1

    # Pass 2: inject split / unsplit dialogue
    for item in plan:
        e = by_cue.get(item.entry.cue, item.entry)

        if item.kind is StreamKind.CATEGORY_A or item.kind is StreamKind.FOREIGN:
            continue

        if not item.wav_path or not os.path.exists(item.wav_path):
            report["skipped_missing_wav"].append(e.cue)
            continue

        # a_sz is the Turkish budget (SPLIT writes it at +0xA800 with prefix).
        max_samples = (e.size_bytes // 16) * 28
        vag = encode_wav_to_vag_bytes(item.wav_path, max_samples, e.sample_rate)
        payload = build_slot_payload(vag, e.size_bytes, item.kind)
        start = audio_base + e.audio_offset
        wad[start : start + len(payload)] = payload

        # Descriptor: force voice channel + correct SR, keep size
        wad[spsx_off + e.table_entry_offset : spsx_off + e.table_entry_offset + 16] = (
            table_entry_bytes(e, hw=VOICE_HW, sr_raw=0x0800 if e.sample_rate >= 22050 else 0x05CE)
        )

        # Descriptor: force voice channel + correct SR, keep size
        wad[spsx_off + e.table_entry_offset : spsx_off + e.table_entry_offset + 16] = (
            table_entry_bytes(e, hw=VOICE_HW, sr_raw=0x0800 if e.sample_rate >= 22050 else 0x05CE)
        )

        report["injected"].append(
            {
                "cue": e.cue,
                "kind": item.kind.value,
                "character": item.character,
                "write_offset": write_point_offset(item.kind),
                "size_bytes": e.size_bytes,
                "tr_budget_sec": round(item.tr_budget_sec, 3),
            }
        )
        if item.kind is StreamKind.SPLIT:
            report["split_count"] += 1
        else:
            report["unsplit_count"] += 1

    violated = verify_category_a(wad, audio_base, entries, baseline)
    report["category_a_violations"] = violated
    if violated:
        raise RuntimeError(f"Category A corruption in cues: {violated}")

    return (bytes(wad) if not dry_run else bytes(wad)), report


# ---------------------------------------------------------------------------
# Burrow reference layout (regression fixture — documents the known-good map)
# ---------------------------------------------------------------------------

BURROW_CATEGORY_A = [0, 1, 38, 48]

BURROW_FOREIGN_CUES = [
    3,
    4,
    6,
    7,
    9,
    10,
    12,
    13,
    15,
    16,
    18,
    19,
    21,
    22,
    24,
    25,
    27,
    28,
    30,
    31,
    33,
    34,
    36,
    37,
    40,
    41,
    43,
    44,
    46,
    47,
    50,
    51,
    53,
    54,
]

BURROW_SPLIT_CUES = [2, 8, 11, 14, 17, 20, 23, 26, 29, 42, 45]
BURROW_UNSPLIT_CUES = [5, 32, 35, 39, 49, 52]


def burrow_expected_kind(cue: int) -> StreamKind | None:
    if cue in BURROW_CATEGORY_A:
        return StreamKind.CATEGORY_A
    if cue in BURROW_FOREIGN_CUES:
        return StreamKind.FOREIGN
    if cue in BURROW_SPLIT_CUES:
        return StreamKind.SPLIT
    if cue in BURROW_UNSPLIT_CUES:
        return StreamKind.UNSPLIT
    return None


def plan_matches_burrow(plan: Sequence[CuePlan]) -> list[str]:
    """Return list of mismatch messages vs the verified Burrow map."""
    problems = []
    for item in plan:
        expected = burrow_expected_kind(item.entry.cue)
        if expected is None:
            continue
        if item.kind is not expected:
            problems.append(
                f"cue {item.entry.cue}: kind={item.kind.value} expected={expected.value}"
            )
    return problems


def load_table_base(stem: str, bases_path: str = "audio/ground_truth_bases.json") -> int | None:
    """Return documented XSPS table base for a stem, if known."""
    if not os.path.exists(bases_path):
        return None
    with open(bases_path, encoding="utf-8") as f:
        gt = json.load(f)
    row = gt.get(stem) or {}
    base = row.get("base_offset")
    return int(base) if base is not None else None


def load_dialogue_map(manifest_path: str, stem: str) -> dict[int, dict]:
    with open(manifest_path, encoding="utf-8") as f:
        rows = json.load(f)
    out: dict[int, dict] = {}
    for row in rows:
        if row.get("stem") != stem:
            continue
        out[row["cue"]] = row
    return out


def detect_split_kinds_from_energy(
    wad_bytes: bytes,
    entries: Sequence[XspsEntry],
    dialogue_cues: Sequence[int],
) -> dict[int, StreamKind]:
    """Classify dialogue cues by ADPCM energy around the 0xA800 boundary.

    Quiet/silent [0x0000, 0xA800) + speech after → SPLIT (shared DE/EN).
    Speech starting at 0x0000 → UNSPLIT.
    """
    from tools.argonaut_xsp import split_detection_from_energy
    from tools.audio_vag import decode_vag_block

    audio_base = find_audio_base(wad_bytes)
    by_cue = {e.cue: e for e in entries}
    out: dict[int, StreamKind] = {}

    for cue in dialogue_cues:
        e = by_cue.get(cue)
        if e is None:
            continue
        if e.size_bytes < SPLIT_OFFSET + ADPCM_BLOCK_BYTES:
            out[cue] = StreamKind.UNSPLIT
            continue

        raw = wad_bytes[audio_base + e.audio_offset : audio_base + e.audio_offset + e.size_bytes]
        h1 = h2 = 0.0
        prefix_pcm: list[int] = []
        tail_pcm: list[int] = []
        for i in range(0, len(raw) - 15, ADPCM_BLOCK_BYTES):
            block = raw[i : i + ADPCM_BLOCK_BYTES]
            samples, h1, h2 = decode_vag_block(block, h1, h2)
            if i < SPLIT_OFFSET:
                prefix_pcm.extend(samples)
            else:
                tail_pcm.extend(samples)

        looks = split_detection_from_energy(prefix_pcm, tail_pcm)
        out[cue] = StreamKind.SPLIT if looks else StreamKind.UNSPLIT
    return out


def burrow_forced_kinds() -> dict[int, StreamKind]:
    forced = {c: StreamKind.SPLIT for c in BURROW_SPLIT_CUES}
    forced.update({c: StreamKind.UNSPLIT for c in BURROW_UNSPLIT_CUES})
    forced.update({c: StreamKind.FOREIGN for c in BURROW_FOREIGN_CUES})
    return forced


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Centralized Argonaut dialogue injector")
    parser.add_argument("--wad", required=True, help="Path to level .WAD")
    parser.add_argument("--manifest", default="audio/deterministic_manifest.json")
    parser.add_argument(
        "--wav-dir",
        help="Override wav_path with <wav-dir>/cue_XX_<char>.wav (verified clean set)",
    )
    parser.add_argument("--plan", action="store_true", help="Print classification plan only")
    parser.add_argument("--inject", action="store_true", help="Write Turkish dialogue into WAD")
    parser.add_argument("--dry-run", action="store_true", help="Do not write file")
    parser.add_argument("--out", help="Output WAD path (default: in-place)")
    parser.add_argument(
        "--regression-burrow", action="store_true", help="Assert plan matches verified T1L2M001 map"
    )
    args = parser.parse_args(argv)

    with open(args.wad, "rb") as f:
        wad_bytes = f.read()

    audio_base = find_audio_base(wad_bytes)
    _, spsx_payload = find_xsps(wad_bytes)
    stem = os.path.basename(args.wad).replace(".WAD", "")
    table_base = load_table_base(stem)
    entries = parse_xsps_table(spsx_payload, table_base=table_base)

    dialogue = {}
    if os.path.exists(args.manifest):
        dialogue = load_dialogue_map(args.manifest, stem)

    if args.wav_dir:
        for cue, meta in dialogue.items():
            cand = os.path.join(args.wav_dir, f"cue_{cue:02d}_{meta.get('character', 'ron')}.wav")
            if not os.path.exists(cand):
                # try generic char-agnostic name
                alt = [
                    os.path.join(args.wav_dir, f)
                    for f in os.listdir(args.wav_dir)
                    if f.startswith(f"cue_{cue:02d}_") and f.endswith(".wav")
                ]
                cand = alt[0] if alt else cand
            meta["wav_path"] = cand

    # Build cue sets from dialogue vs not (plus known Burrow fixture).
    if stem == "T1L2M001":
        cat_a = BURROW_CATEGORY_A
        foreign = BURROW_FOREIGN_CUES
    else:
        cat_a = [e.cue for e in entries if e.hw != VOICE_HW]
        foreign = [e.cue for e in entries if e.hw != VOICE_HW and e.cue not in dialogue]
        # hw==voice without dialogue text → foreign leftover
        for e in entries:
            if e.hw == VOICE_HW and e.cue not in dialogue and e.cue not in cat_a:
                foreign.append(e.cue)

    plan = build_plan(
        entries,
        cat_a_cues=cat_a,
        foreign_cues=foreign,
        dialogue=dialogue,
        forced_kinds=burrow_forced_kinds() if stem == "T1L2M001" else None,
    )

    if args.regression_burrow:
        problems = plan_matches_burrow(plan)
        if problems:
            print("BURROW REGRESSION FAIL:")
            print("\n".join(problems))
            return 1
        print(f"OK: {len(plan)} cues match verified Burrow map")

    if args.plan:
        kinds = [p.kind for p in plan]
        print(f"WAD: {args.wad}")
        print(f"audio_base: 0x{audio_base:X}")
        print(f"summary: {summarize_plan(kinds)}")
        print(f"{'cue':>4} {'kind':<10} {'sr':>6} {'sz':>8} {'write':>8} {'budget_s':>9} char")
        for p in plan:
            print(
                f"{p.entry.cue:4d} {p.kind.value:<10} {p.entry.sample_rate:6d} "
                f"{p.entry.size_bytes:8d} 0x{p.write_offset:05X}  {p.tr_budget_sec:9.3f} "
                f"{p.character}"
            )
        return 0

    if args.inject:
        new_wad, report = inject_wad(
            wad_bytes,
            plan,
            dry_run=args.dry_run,
            cat_a_cues=cat_a,
            table_base=table_base,
        )
        print(
            json.dumps({k: v for k, v in report.items() if k != "category_a_violations"}, indent=2)
        )
        print(f"category_a_violations: {report['category_a_violations']}")
        if not args.dry_run:
            out = args.out or args.wad
            with open(out, "wb") as f:
                f.write(new_wad)
            print(f"wrote {len(new_wad)} bytes -> {out}")
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
