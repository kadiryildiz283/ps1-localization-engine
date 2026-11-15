"""Full-game Turkish dubbing orchestrator (Issue #3).

Unifies the entire localization audio pipeline across all 68+ level WADs:
  1. build-profiles : Auto-extract dedicated WAV profiles from original PS1
                      English dialogue for any speaker without a human recording.
  2. inject-all     : Run centralized split-stream / multi-cue injection
                      (tools.inject_dialogue) across all WADs with Category A
                      100% bit-exact verification.
  3. patch-disc     : Patch all updated WADs into the target PS1 .bin image
                      with Mode 2 Form 1 EDC/ECC and verify local == iso.

Usage:
  python tools/full_game_dub.py build-profiles
  python tools/full_game_dub.py inject-all --dry-run
  python tools/full_game_dub.py patch-disc --output "Harry Potter and the Chamber of Secrets (Turkish).bin"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import wave
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.argonaut_xsp import SPLIT_OFFSET, find_xsps, parse_xsps_table
from tools.audio_vag import decode_adpcm_to_wav
from tools.cd_patcher import USER_DATA_SIZE, encode_mode2_form1_sector
from tools.dirdat import DirDatArchive
from tools.inject_dialogue import (
    BURROW_CATEGORY_A,
    BURROW_FOREIGN_CUES,
    VOICE_HW,
    build_plan,
    burrow_forced_kinds,
    detect_split_kinds_from_energy,
    inject_wad,
    load_dialogue_map,
    load_table_base,
)
from tools.iso_fs import Ps1IsoReader

ORIGINAL_BIN = "Harry Potter and the Chamber of Secrets (Europe) (En,Fr,De).bin"
TARGET_BIN = "Harry Potter and the Chamber of Secrets (Turkish).bin"
MANIFEST_PATH = "audio/deterministic_manifest.json"
PROFILES_DIR = "audio/profiles"


def _concat_wavs_22k(wav_paths: list[str], out_path: str, pause_ms: int = 250) -> float:
    """Concatenate mono 16-bit WAVs at 22050 Hz with short silence padding."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    frames: list[bytes] = []
    silence = b"\x00\x00" * int(22050 * pause_ms / 1000)
    for path in wav_paths:
        with wave.open(path, "rb") as wf:
            frames.append(wf.readframes(wf.getnframes()))
            frames.append(silence)
    with wave.open(out_path, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(22050)
        out.writeframes(b"".join(frames))
    with wave.open(out_path, "rb") as out:
        return out.getnframes() / float(out.getframerate())


def build_missing_profiles(
    manifest_path: str = MANIFEST_PATH,
    orig_bin: str = ORIGINAL_BIN,
    profiles_dir: str = PROFILES_DIR,
    max_clips: int = 3,
) -> list[str]:
    """Extract dedicated English reference WAVs for speakers lacking a profile."""
    if not os.path.exists(orig_bin):
        raise FileNotFoundError(f"Original disc image not found: {orig_bin}")

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    by_profile: dict[str, list[dict]] = defaultdict(list)
    for row in manifest:
        if row.get("is_cutscene"):
            continue
        prof = row.get("voice_profile") or row.get("character")
        if prof:
            by_profile[prof].append(row)

    missing = sorted(
        p for p in by_profile if not os.path.exists(os.path.join(profiles_dir, f"{p}.wav"))
    )
    if not missing:
        print("[OK] All voice profiles already exist in", profiles_dir)
        return []

    created: list[str] = []
    with Ps1IsoReader(orig_bin) as iso, tempfile.TemporaryDirectory() as tmpdir:
        archive = DirDatArchive.from_iso(iso)
        wad_cache: dict[str, bytes] = {}

        for prof in missing:
            # Prefer unsplit 22050 Hz cues, longest duration first.
            candidates = sorted(
                by_profile[prof],
                key=lambda r: (
                    not r.get("is_split_stream", False),
                    r.get("target_sample_rate", 0) >= 22050,
                    r.get("size_bytes", 0),
                ),
                reverse=True,
            )[:max_clips]

            clip_wavs: list[str] = []
            for idx, row in enumerate(candidates):
                wad_name = row["wad"]
                if wad_name not in wad_cache:
                    entry = archive.entry_map.get(wad_name)
                    if entry is None:
                        continue
                    wad_cache[wad_name] = iso.read_file_bytes(
                        "POTTER.DAT", entry.offset, entry.size
                    )
                wad_bytes = wad_cache[wad_name]
                start = row["audio_base"] + row["audio_offset"]
                if row.get("is_split_stream"):
                    start += SPLIT_OFFSET
                chunk = wad_bytes[start : start + row["size_bytes"]]
                if len(chunk) < 32:
                    continue
                tmp_wav = os.path.join(tmpdir, f"{prof}_{idx}.wav")
                decode_adpcm_to_wav(chunk, tmp_wav, sample_rate=22050)
                clip_wavs.append(tmp_wav)

            if not clip_wavs:
                print(f"[!] No extractable clips for profile '{prof}'")
                continue

            out_wav = os.path.join(profiles_dir, f"{prof}.wav")
            dur = _concat_wavs_22k(clip_wavs, out_wav)
            created.append(out_wav)
            print(f"[OK] Extracted profile '{prof}' -> {out_wav} ({dur:.2f}s)")

    return created


def inject_all_wads(
    manifest_path: str = MANIFEST_PATH,
    src_dir: str = "extracted_text_only",
    out_dir: str = "extracted",
    dry_run: bool = False,
) -> dict:
    """Run centralized split-stream injection across all manifest WADs."""
    with open(manifest_path, encoding="utf-8") as f:
        rows = json.load(f)
    stems = sorted({r["stem"] for r in rows if r.get("stem") and r["stem"] != "T1L1M007"})

    summary = {
        "wads_processed": 0,
        "wads_skipped_missing": 0,
        "split_injected": 0,
        "unsplit_injected": 0,
        "foreign_muted": 0,
        "skipped_missing_wav": 0,
        "category_a_violations": 0,
    }

    os.makedirs(out_dir, exist_ok=True)
    for stem in stems:
        src_wad = os.path.join(src_dir, f"{stem}.WAD")
        dst_wad = os.path.join(out_dir, f"{stem}.WAD")
        in_wad = src_wad if os.path.exists(src_wad) else dst_wad
        if not os.path.exists(in_wad):
            summary["wads_skipped_missing"] += 1
            continue

        with open(in_wad, "rb") as f:
            raw = f.read()

        table_base = load_table_base(stem) or 0
        dialogue_map = load_dialogue_map(manifest_path, stem)
        _, spsx_data = find_xsps(raw)
        entries = parse_xsps_table(spsx_data, table_base=table_base)
        if stem == "T1L2M001":
            cat_a = BURROW_CATEGORY_A
            foreign = BURROW_FOREIGN_CUES
            forced = burrow_forced_kinds()
        else:
            cat_a = [e.cue for e in entries if e.hw != VOICE_HW]
            foreign = [e.cue for e in entries if e.hw == VOICE_HW and e.cue not in dialogue_map]
            forced = detect_split_kinds_from_energy(raw, entries, list(dialogue_map.keys()))
        plan = build_plan(
            entries,
            cat_a_cues=cat_a,
            foreign_cues=foreign,
            dialogue=dialogue_map,
            forced_kinds=forced,
        )
        patched, report = inject_wad(
            raw, plan, cat_a_cues=cat_a, table_base=table_base, dry_run=dry_run
        )
        if not dry_run:
            with open(dst_wad, "wb") as f:
                f.write(patched)

        summary["wads_processed"] += 1
        summary["split_injected"] += report["split_count"]
        summary["unsplit_injected"] += report["unsplit_count"]
        summary["foreign_muted"] += report["foreign_count"]
        summary["skipped_missing_wav"] += len(report["skipped_missing_wav"])
        summary["category_a_violations"] += len(report["category_a_violations"])

    print(json.dumps(summary, indent=2))
    return summary


def patch_disc_wads(
    output_bin: str = TARGET_BIN,
    wads_dir: str = "extracted",
    verify: bool = True,
) -> int:
    """Patch modified WADs inside POTTER.DAT and optionally verify local == iso."""
    if not os.path.exists(output_bin):
        raise FileNotFoundError(f"Target disc image not found: {output_bin}")

    with Ps1IsoReader(output_bin) as iso:
        potter_entry = iso.files.get("POTTER.DAT")
        dir_entry = iso.files.get("POTTER.DIR")
        if potter_entry is None or dir_entry is None:
            raise RuntimeError("POTTER.DAT or POTTER.DIR not found in ISO")
        archive = DirDatArchive.from_iso(iso)
        potter_lba = potter_entry.lba

    patched_wads: list[str] = []
    with open(output_bin, "r+b") as f:
        for wad_name, entry in sorted(archive.entry_map.items()):
            if not wad_name.endswith(".WAD"):
                continue
            local_path = os.path.join(wads_dir, wad_name)
            if not os.path.exists(local_path):
                continue
            with open(local_path, "rb") as wf:
                new_data = wf.read()
            if len(new_data) > entry.size:
                print(f"[!] Skipping {wad_name}: size {len(new_data)} > {entry.size}")
                continue
            start_lba = potter_lba + (entry.offset // USER_DATA_SIZE)
            sectors_needed = (len(new_data) + USER_DATA_SIZE - 1) // USER_DATA_SIZE
            padded = new_data.ljust(sectors_needed * USER_DATA_SIZE, b"\x00")
            bulk = bytearray()
            for s in range(sectors_needed):
                chunk = padded[s * USER_DATA_SIZE : (s + 1) * USER_DATA_SIZE]
                bulk.extend(encode_mode2_form1_sector(start_lba + s, chunk))
            f.seek(start_lba * 2352)
            f.write(bulk)
            patched_wads.append(wad_name)

    print(f"[OK] Patched {len(patched_wads)} WADs into {output_bin}")

    if verify:
        mismatches = []
        with Ps1IsoReader(output_bin) as iso:
            for wad_name in patched_wads:
                entry = archive.entry_map[wad_name]
                iso_bytes = iso.read_file_bytes("POTTER.DAT", entry.offset, entry.size)
                with open(os.path.join(wads_dir, wad_name), "rb") as wf:
                    local_bytes = wf.read()
                if iso_bytes[: len(local_bytes)] != local_bytes:
                    mismatches.append(wad_name)
        if mismatches:
            raise RuntimeError(f"ISO verification mismatch on: {mismatches}")
        print(f"[OK] Verified local == iso: True ({len(patched_wads)} WADs)")

    return len(patched_wads)


def main() -> None:
    parser = argparse.ArgumentParser(description="Full-game PS1 Turkish dubbing pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_prof = sub.add_parser("build-profiles", help="Extract missing speaker WAV profiles")
    p_prof.add_argument("--manifest", default=MANIFEST_PATH)
    p_prof.add_argument("--orig-bin", default=ORIGINAL_BIN)
    p_prof.add_argument("--profiles-dir", default=PROFILES_DIR)

    p_inj = sub.add_parser("inject-all", help="Inject all WADs with Category A gate")
    p_inj.add_argument("--manifest", default=MANIFEST_PATH)
    p_inj.add_argument("--src-dir", default="extracted_text_only")
    p_inj.add_argument("--out-dir", default="extracted")
    p_inj.add_argument("--dry-run", action="store_true")

    p_patch = sub.add_parser("patch-disc", help="Patch all updated WADs into .bin image")
    p_patch.add_argument("--output", default=TARGET_BIN)
    p_patch.add_argument("--wads-dir", default="extracted")
    p_patch.add_argument("--no-verify", action="store_true")

    args = parser.parse_args()
    if args.cmd == "build-profiles":
        build_missing_profiles(args.manifest, args.orig_bin, args.profiles_dir)
    elif args.cmd == "inject-all":
        inject_all_wads(args.manifest, args.src_dir, args.out_dir, dry_run=args.dry_run)
    elif args.cmd == "patch-disc":
        patch_disc_wads(args.output, args.wads_dir, verify=not args.no_verify)


if __name__ == "__main__":
    main()
