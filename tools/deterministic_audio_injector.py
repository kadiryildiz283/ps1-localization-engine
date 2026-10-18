"""High-Performance Deterministic Audio Injector & SPU ADPCM Synthesis Engine.

Key Invariants:
1. Category A (SFX/BGM loops/Spells) are 100% bit-exact preserved from original European disc.
2. 1-to-1 deterministic dialogue cue injection: No sentence slicing across foreign cues.
3. SPU ADPCM conformance: Resampled to target frequency, bounded atempo fitting, and bit-exact 0x01 terminal mute blocks.
4. Post-injection verification gate: Asserts all Category A cues maintain matching pre-injection MD5 hashes.
"""

import argparse
import glob
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import time
import wave
from collections import defaultdict
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.audio_vag import encode_pcm_to_vag

MANIFEST_PATH = "audio/deterministic_manifest.json"
UNIQUE_LINES_PATH = "audio/deterministic_unique_lines.json"
EXCLUSION_MAP_PATH = "audio/category_a_exclusion_map.json"
INGAME_DUB_DIR = "audio/ingame_dub"
EXTRACTED_DIR = "extracted"


def print_status():
    """Print current progress of synthesized files vs deterministic unique lines."""
    if not os.path.exists(UNIQUE_LINES_PATH):
        print("Run tools/build_deterministic_manifest.py first.")
        return

    with open(UNIQUE_LINES_PATH, "r", encoding="utf-8") as f:
        unique_lines = json.load(f)

    os.makedirs(INGAME_DUB_DIR, exist_ok=True)
    existing_hashes = set(
        f.replace(".wav", "")
        for f in os.listdir(INGAME_DUB_DIR)
        if f.endswith(".wav") and os.path.getsize(os.path.join(INGAME_DUB_DIR, f)) > 1000
    )

    by_char = defaultdict(lambda: {"total": 0, "done": 0})
    for l in unique_lines:
        c = l["character"]
        h = l["line_hash"]
        by_char[c]["total"] += 1
        if h in existing_hashes:
            by_char[c]["done"] += 1

    total_all = len(unique_lines)
    done_all = len(existing_hashes.intersection(set(l["line_hash"] for l in unique_lines)))

    print("=" * 70)
    print("  DETERMINISTIC IN-GAME TURKISH DUBBING PROGRESS")
    print("=" * 70)
    for c, stats in sorted(by_char.items(), key=lambda x: -x[1]["total"]):
        done = stats["done"]
        tot = stats["total"]
        pct = (done / tot * 100) if tot > 0 else 0
        bar = "#" * int(pct // 5) + "-" * (20 - int(pct // 5))
        print(f"  {c:14s} [{bar}] {done:4d}/{tot:4d} ({pct:5.1f}%)")
    print("-" * 70)
    overall_pct = (done_all / total_all * 100) if total_all > 0 else 0
    print(f"  TOTAL PROGRESS: {done_all}/{total_all} ({overall_pct:.1f}%)")
    print(f"  REMAINING TO SYNTHESIZE: {total_all - done_all}")
    print("=" * 70)


def synthesize_missing_lines(characters: Optional[List[str]] = None,
                             worker_id: int = 0,
                             num_workers: int = 1,
                             limit: Optional[int] = None):
    """Synthesize missing lines using XTTS-v2 with character conditioning latents."""
    os.makedirs(INGAME_DUB_DIR, exist_ok=True)

    with open(UNIQUE_LINES_PATH, "r", encoding="utf-8") as f:
        unique_lines = json.load(f)

    # Filter by character
    if characters:
        unique_lines = [l for l in unique_lines if l["character"] in characters]

    # Filter only lines that need synthesis
    missing_lines = [
        l for l in unique_lines
        if not (os.path.exists(os.path.join(INGAME_DUB_DIR, f"{l['line_hash']}.wav")) and
                os.path.getsize(os.path.join(INGAME_DUB_DIR, f"{l['line_hash']}.wav")) > 1000)
    ]

    if num_workers > 1:
        missing_lines = [l for i, l in enumerate(missing_lines) if i % num_workers == worker_id]

    if limit is not None:
        missing_lines = missing_lines[:limit]

    total = len(missing_lines)
    print(f"[Worker {worker_id}/{num_workers}] Starting synthesis for {total} missing lines...")
    if total == 0:
        print(f"[Worker {worker_id}] No missing lines to synthesize.")
        return

    from tools.voice_cloner import NeuralVoiceEngine
    engine = NeuralVoiceEngine()
    completed = 0

    for idx, item in enumerate(missing_lines):
        line_hash = item["line_hash"]
        char = item["character"]
        tr_text = item["tr"]
        min_dur = item.get("min_duration")
        out_wav = os.path.join(INGAME_DUB_DIR, f"{line_hash}.wav")

        print(f"\n[{idx+1}/{total}] (W{worker_id}) [{char.upper()}] \"{tr_text[:60]}\"")
        try:
            t0 = time.time()
            engine.synthesize_line(
                text_tr=tr_text,
                character=char,
                output_wav=out_wav,
                max_duration=min_dur
            )
            completed += 1
            print(f"      Synthesized in {time.time()-t0:.2f}s -> {os.path.basename(out_wav)}")
        except Exception as ex:
            print(f"      [!] Error synthesizing {line_hash}: {ex}")

    print(f"\n[Worker {worker_id}] Synthesis finished: {completed}/{total} completed.")


def conform_and_inject_wads(dry_run: bool = False):
    """Inject synthesized Turkish dialogue cues into WADs while preserving 100% of Category A."""
    print("=" * 75)
    print("DETERMINISTIC INJECTION OF TURKISH SPU ADPCM INTO WAD CONTAINERS")
    print("=" * 75)

    if not os.path.exists(MANIFEST_PATH):
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")
    if not os.path.exists(EXCLUSION_MAP_PATH):
        raise FileNotFoundError(f"Exclusion map not found: {EXCLUSION_MAP_PATH}")

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(EXCLUSION_MAP_PATH, "r", encoding="utf-8") as f:
        exclusion_map = json.load(f)

    # Group manifest entries by WAD
    by_wad = defaultdict(list)
    for e in manifest:
        by_wad[e["wad"]].append(e)

    silence_mute_block = b"\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    silence_mid_block  = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

    import numpy as np

    total_injected = 0
    total_missing = 0
    wads_updated = 0
    cat_a_violations = 0

    t_start = time.time()

    for wad_name, entries in sorted(by_wad.items()):
        wad_path = os.path.join(EXTRACTED_DIR, wad_name)
        if not os.path.exists(wad_path):
            print(f"[!] Warning: {wad_name} not found in {EXTRACTED_DIR}, skipping.")
            continue

        with open(wad_path, "rb") as f:
            wad_data = bytearray(f.read())

        audio_base = entries[0]["audio_base"]
        spsx_pos = wad_data.find(b"XSPS")
        spsx_sz = struct.unpack("<I", wad_data[spsx_pos+4 : spsx_pos+8])[0] if spsx_pos != -1 else 0
        wad_modified = False

        # Pre-capture Category A bytes for verification
        cat_a_cues = exclusion_map.get(wad_name, [])
        cat_a_baseline = {}
        for ca in cat_a_cues:
            off = ca["audio_offset"]
            sz = ca["size_bytes"]
            cat_a_baseline[ca["cue"]] = wad_data[audio_base + off : audio_base + off + sz]

        for entry in entries:
            sz = entry["size_bytes"]
            a_off = entry["audio_offset"]
            e_off = entry["table_entry_offset"]
            target_sr = entry["target_sample_rate"]
            max_allowed_samples = entry["max_allowed_samples"]
            wav_path = entry.get("wav_path", os.path.join(INGAME_DUB_DIR, f"{entry['line_hash']}.wav"))

            if sz < 16:
                continue

            if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 100:
                total_missing += 1
                continue

            # Maintain hw = 2 ONLY for in-game dialogue cues in SPSX table
            if spsx_pos != -1 and not entry.get("is_cutscene") and e_off >= 0 and e_off + 16 <= spsx_sz:
                f0, f1, f2, f3 = struct.unpack("<IIII", wad_data[spsx_pos+8+e_off : spsx_pos+8+e_off+16])
                new_f1 = (f1 & 0x0000FFFF) | 0x00020000
                wad_data[spsx_pos+8+e_off+4 : spsx_pos+8+e_off+8] = struct.pack("<I", new_f1)
                wad_modified = True

            # Load WAV & trim dead lead/trail silence (with 25ms attack/decay safety margin)
            with wave.open(wav_path, "rb") as wf:
                in_sr = wf.getframerate()
                in_ch = wf.getnchannels()
                raw_bytes = wf.readframes(wf.getnframes())
            
            raw_pcm = np.frombuffer(raw_bytes, dtype=np.int16)
            if in_ch > 1:
                raw_pcm = raw_pcm[::in_ch]  # mono extract

            # Voice activity boundary detection
            non_silent = np.where(np.abs(raw_pcm) > 300)[0]
            if len(non_silent) > 0:
                pad_samples = int(in_sr * 0.025)  # 25ms safety padding
                start_idx = max(0, non_silent[0] - pad_samples)
                end_idx = min(len(raw_pcm), non_silent[-1] + pad_samples)
                trimmed_pcm = raw_pcm[start_idx:end_idx]
            else:
                trimmed_pcm = raw_pcm

            trimmed_dur = len(trimmed_pcm) / float(in_sr)
            max_dur_sec = max(0.1, (max_allowed_samples - 28) / float(target_sr))

            # Resample & strict acoustic tempo-fit
            if trimmed_dur > max_dur_sec:
                speed_ratio = trimmed_dur / max_dur_sec
                if speed_ratio > 1.28:
                    print(f"      [!] Strict Gate Notice ({wad_name} {entry['character']} cue {entry['cue']}): "
                          f"tempo={speed_ratio:.2f}x ({trimmed_dur:.2f}s vs {max_dur_sec:.2f}s budget) -> '{entry['tr'][:45]}...'")

                # Multi-stage atempo filter construction
                if speed_ratio > 2.0:
                    filter_str = f"aformat=sample_fmts=s16:sample_rates={target_sr}:channel_layouts=mono,atempo=2.0,atempo={speed_ratio/2.0:.4f}"
                else:
                    filter_str = f"aformat=sample_fmts=s16:sample_rates={target_sr}:channel_layouts=mono,atempo={speed_ratio:.4f}"

                # Write trimmed PCM to stdin of ffmpeg
                cmd = [
                    "ffmpeg", "-y", "-f", "s16le", "-ar", str(in_sr), "-ac", "1", "-i", "-",
                    "-af", filter_str,
                    "-ac", "1", "-ar", str(target_sr),
                    "-f", "s16le", "-"
                ]
                res = subprocess.run(cmd, input=trimmed_pcm.tobytes(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
                samples = np.frombuffer(res.stdout, dtype=np.int16)
            else:
                if in_sr != target_sr:
                    cmd = [
                        "ffmpeg", "-y", "-f", "s16le", "-ar", str(in_sr), "-ac", "1", "-i", "-",
                        "-ac", "1", "-ar", str(target_sr),
                        "-f", "s16le", "-"
                    ]
                    res = subprocess.run(cmd, input=trimmed_pcm.tobytes(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
                    samples = np.frombuffer(res.stdout, dtype=np.int16)
                else:
                    samples = trimmed_pcm

            if len(samples) > max_allowed_samples:
                samples = samples[:max_allowed_samples]

            # SPU ADPCM encoding with loop=True (all blocks flag 0x00)
            vag_data = encode_pcm_to_vag(samples, loop=True)

            # SPU silence padding with guaranteed single terminal 0x01 mute block
            pad_bytes = sz - len(vag_data)
            num_pad_blocks = pad_bytes // 16

            if num_pad_blocks > 0:
                vag_data = vag_data + (silence_mid_block * (num_pad_blocks - 1)) + silence_mute_block
            else:
                vag_data = bytearray(vag_data[:sz])
                vag_data[-15] = 0x01
                vag_data = bytes(vag_data)

            # Inject into WAD bytearray
            wad_pos = audio_base + a_off
            wad_data[wad_pos : wad_pos + sz] = vag_data
            wad_modified = True
            total_injected += 1

        # Post-injection Category A verification
        for ca in cat_a_cues:
            cid = ca["cue"]
            off = ca["audio_offset"]
            sz = ca["size_bytes"]
            curr_bytes = wad_data[audio_base + off : audio_base + off + sz]
            if curr_bytes != cat_a_baseline[cid]:
                cat_a_violations += 1
                print(f"[!] CRITICAL: Category A cue {cid} in {wad_name} was mutated!")

        if wad_modified and not dry_run:
            with open(wad_path, "wb") as f:
                f.write(wad_data)
            wads_updated += 1

    dt = time.time() - t_start
    print(f"\n[OK] Deterministic Injection complete in {dt:.2f}s!")
    print(f"     -> Updated WADs:        {wads_updated}")
    print(f"     -> Dialogue Cues Injected: {total_injected}")
    print(f"     -> Missing Dialogue Cues:  {total_missing}")
    print(f"     -> Category A Violations:  {cat_a_violations}")
    if cat_a_violations > 0:
        raise RuntimeError(f"ABORT: {cat_a_violations} Category A cues were violated during injection!")


def main():
    parser = argparse.ArgumentParser(description="Deterministic PS1 Audio Injector")
    parser.add_argument("--status", action="store_true", help="Print dubbing coverage status")
    parser.add_argument("--synthesize", action="store_true", help="Synthesize missing dialogue lines")
    parser.add_argument("--char", nargs="+", help="Specific characters to synthesize")
    parser.add_argument("--workers", type=int, default=1, help="Parallel workers")
    parser.add_argument("--worker-id", type=int, default=0, help="Worker index [0..N-1]")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of lines to synthesize")
    parser.add_argument("--inject", action="store_true", help="Inject audio into all level WADs")
    parser.add_argument("--dry-run", action="store_true", help="Dry run injection without saving")
    parser.add_argument("--rebuild-iso", action="store_true", help="Rebuild final PS1 ISO")
    args = parser.parse_args()

    if args.status:
        print_status()
        return

    if args.synthesize:
        synthesize_missing_lines(
            characters=args.char,
            worker_id=args.worker_id,
            num_workers=args.workers,
            limit=args.limit
        )
        return

    if args.inject:
        conform_and_inject_wads(dry_run=args.dry_run)
        if args.rebuild_iso:
            from tools.build_turkish_iso import build_turkish_iso
            build_turkish_iso()
        return

    if args.rebuild_iso:
        from tools.build_turkish_iso import build_turkish_iso
        build_turkish_iso()
        return

    print_status()


if __name__ == "__main__":
    main()
