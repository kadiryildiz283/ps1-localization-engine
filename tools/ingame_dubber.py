"""High-Performance In-Game Dubbing Synthesis & WAD SPU Injection Engine.

Features:
1. Multi-character neural voice synthesis with Coqui XTTS-v2 and golden latents.
2. Ultra-fast SPU ADPCM encoding via C extension (vag_fast.so).
3. Sector-budget tempo fitting and alignment for all 1,611 dialogue cues across 70 WADs.
4. Seamless integration with PS1 ISO Mode 2 Form 1 disc rebuilder.
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

MANIFEST_PATH = "audio/true_ingame_manifest.json"
UNIQUE_LINES_PATH = "audio/true_unique_lines.json"
BASES_PATH = "audio/ground_truth_bases.json"
INGAME_DUB_DIR = "audio/ingame_dub"
EXTRACTED_DIR = "extracted"


def synthesize_lines(characters: Optional[List[str]] = None,
                     worker_id: int = 0,
                     num_workers: int = 1,
                     limit: Optional[int] = None):
    """Synthesize unique in-game lines using XTTS-v2 neural engine."""
    os.makedirs(INGAME_DUB_DIR, exist_ok=True)

    with open(UNIQUE_LINES_PATH, "r", encoding="utf-8") as f:
        unique_lines = json.load(f)

    # Filter by character if specified
    if characters:
        unique_lines = [l for l in unique_lines if l["character"] in characters]

    # Partition by worker
    if num_workers > 1:
        unique_lines = [l for i, l in enumerate(unique_lines) if i % num_workers == worker_id]

    if limit is not None:
        unique_lines = unique_lines[:limit]

    total = len(unique_lines)
    print(f"[Worker {worker_id}/{num_workers}] Starting synthesis for {total} lines...")

    from tools.voice_cloner import clean_text_for_tts, resample_audio, NeuralVoiceEngine
    engine = NeuralVoiceEngine()
    completed = 0
    skipped = 0

    for idx, item in enumerate(unique_lines):
        line_hash = item["line_hash"]
        char = item["character"]
        tr_text = item["tr"]
        min_dur = item.get("min_duration")

        out_wav = os.path.join(INGAME_DUB_DIR, f"{line_hash}.wav")

        # Skip if already synthesized
        if os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000:
            skipped += 1
            continue

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

    print(f"\n[Worker {worker_id}] Finished: {completed} synthesized, {skipped} skipped, {total} total.")


def print_status():
    """Print current progress of synthesized files vs total lines."""
    if not os.path.exists(UNIQUE_LINES_PATH):
        print("Run tools/build_ingame_manifest.py first.")
        return

    with open(UNIQUE_LINES_PATH, "r", encoding="utf-8") as f:
        unique_lines = json.load(f)

    os.makedirs(INGAME_DUB_DIR, exist_ok=True)
    existing = set(f.replace(".wav", "") for f in os.listdir(INGAME_DUB_DIR) if f.endswith(".wav") and os.path.getsize(os.path.join(INGAME_DUB_DIR, f)) > 1000)

    by_char = defaultdict(lambda: {"total": 0, "done": 0})
    for l in unique_lines:
        c = l["character"]
        h = l["line_hash"]
        by_char[c]["total"] += 1
        if h in existing:
            by_char[c]["done"] += 1

    total_all = len(unique_lines)
    done_all = len(existing.intersection(set(l["line_hash"] for l in unique_lines)))

    print("=" * 65)
    print("  IN-GAME TURKISH DUBBING PROGRESS")
    print("=" * 65)
    for c, stats in sorted(by_char.items(), key=lambda x: -x[1]["total"]):
        done = stats["done"]
        tot = stats["total"]
        pct = (done / tot * 100) if tot > 0 else 0
        bar = "#" * int(pct // 5) + "-" * (20 - int(pct // 5))
        print(f"  {c:12s} [{bar}] {done:4d}/{tot:4d} ({pct:5.1f}%)")
    print("-" * 65)
    overall_pct = (done_all / total_all * 100) if total_all > 0 else 0
    print(f"  TOTAL PROGRESS: {done_all}/{total_all} ({overall_pct:.1f}%)")
    print("=" * 65)


def inject_into_wads():
    """Inject all synthesized SPU ADPCM audio tracks into their respective WAD files."""
    print("=" * 70)
    print("INJECTING TURKISH SPU ADPCM AUDIO INTO 70 WAD FILES")
    print("=" * 70)

    if not os.path.exists(MANIFEST_PATH):
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    by_wad = defaultdict(list)
    for e in manifest:
        by_wad[e["wad"]].append(e)

    silence_block = b"\x0C\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

    wads_updated = 0
    cues_injected = 0
    cues_missing = 0

    t_start = time.time()

    for wad_name, entries in by_wad.items():
        wad_path = os.path.join(EXTRACTED_DIR, wad_name)
        if not os.path.exists(wad_path):
            print(f"[!] Warning: {wad_name} not found in {EXTRACTED_DIR}, skipping.")
            continue

        with open(wad_path, "rb") as f:
            wad_data = bytearray(f.read())

        audio_base = entries[0]["audio_base"]
        stem = entries[0]["stem"]
        wad_modified = False

        spsx_pos = wad_data.find(b"XSPS")

        silence_mute_block = b"\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        silence_mid_block  = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

        for entry in entries:
            line_hash = entry["line_hash"]
            a_off = entry["audio_offset"]
            sz = entry["size_bytes"]
            max_dur = entry["max_duration"]
            e_off = entry["table_entry_offset"]
            wav_path = os.path.join(INGAME_DUB_DIR, f"{line_hash}.wav")

            if sz < 16:
                # Dummy placeholder in original game, skip
                continue

            if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 100:
                cues_missing += 1
                continue

            # Determine native target sample rate from SPSX entry
            target_sr = 22050
            if spsx_pos != -1 and e_off + 16 <= len(wad_data) - (spsx_pos + 8):
                f0, f1, f2, f3 = struct.unpack("<IIII", wad_data[spsx_pos+8+e_off : spsx_pos+8+e_off+16])
                sr_raw = f1 & 0xffff
                if sr_raw > 0:
                    calculated_sr = round(44100 * sr_raw / 4096)
                    if 8000 <= calculated_sr <= 48000:
                        target_sr = 16000 if sr_raw == 1486 else calculated_sr

                # Maintain hw = 2 (one-shot dialogue mode, preventing infinite ambient loop)
                new_f1 = (f1 & 0x0000ffff) | 0x00020000
                wad_data[spsx_pos+8+e_off+4 : spsx_pos+8+e_off+8] = struct.pack("<I", new_f1)
                wad_modified = True

            import numpy as np

            # Load WAV and measure duration
            with wave.open(wav_path, "rb") as wf:
                in_sr = wf.getframerate()
                in_ch = wf.getnchannels()
                in_frames = wf.getnframes()
                in_dur = in_frames / in_sr

            # Maximum allowed audio samples in sector budget (reserving 28 samples = 1 block for clean terminal mute)
            max_allowed_samples = (sz // 16) * 28
            max_dur_sec = max(0.1, (max_allowed_samples - 28) / target_sr)

            # Resample and fit tempo to target sample rate
            if in_dur > max_dur_sec:
                speed_ratio = in_dur / max_dur_sec
                filter_str = f"aformat=sample_fmts=s16:sample_rates={target_sr}:channel_layouts=mono,atempo={speed_ratio:.4f}"
                if speed_ratio > 2.0:
                    filter_str = f"aformat=sample_fmts=s16:sample_rates={target_sr}:channel_layouts=mono,atempo=2.0,atempo={speed_ratio/2.0:.4f}"

                cmd = [
                    "ffmpeg", "-y", "-i", wav_path,
                    "-af", filter_str,
                    "-ac", "1", "-ar", str(target_sr),
                    "-f", "s16le", "-"
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
                samples = np.frombuffer(res.stdout, dtype=np.int16)
            else:
                if in_sr != target_sr or in_ch != 1:
                    cmd = [
                        "ffmpeg", "-y", "-i", wav_path,
                        "-ac", "1", "-ar", str(target_sr),
                        "-f", "s16le", "-"
                    ]
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
                    samples = np.frombuffer(res.stdout, dtype=np.int16)
                else:
                    with wave.open(wav_path, "rb") as wf:
                        raw_frames = wf.readframes(wf.getnframes())
                    samples = np.frombuffer(raw_frames, dtype=np.int16)

            if len(samples) > max_allowed_samples:
                samples = samples[:max_allowed_samples]

            # Fast C-accelerated SPU ADPCM encoding with loop=True so all speech blocks have flag=0x00
            vag_data = encode_pcm_to_vag(samples, loop=True)

            # SPU silence padding to exact budget with guaranteed single 0x01 terminal block at the very end
            pad_bytes = sz - len(vag_data)
            num_pad_blocks = pad_bytes // 16

            if num_pad_blocks > 0:
                vag_data = vag_data + (silence_mid_block * (num_pad_blocks - 1)) + silence_mute_block
            else:
                vag_data = bytearray(vag_data[:sz])
                vag_data[-15] = 0x01
                vag_data = bytes(vag_data)

            # Inject into WAD bytearray at audio_base + audio_offset
            wad_pos = audio_base + a_off
            wad_data[wad_pos : wad_pos + sz] = vag_data
            wad_modified = True
            cues_injected += 1


        if wad_modified:
            with open(wad_path, "wb") as f:
                f.write(wad_data)
            wads_updated += 1

    dt = time.time() - t_start
    print(f"\n[OK] WAD SPU Injection completed in {dt:.2f}s!")
    print(f"     -> Updated {wads_updated} WAD files.")
    print(f"     -> Injected {cues_injected} dialogue cues.")
    if cues_missing:
        print(f"     -> Note: {cues_missing} cues currently missing audio in {INGAME_DUB_DIR}/")


def main():
    parser = argparse.ArgumentParser(description="In-Game Turkish Dubbing Engine")
    parser.add_argument("--char", nargs="+", help="Specific characters to synthesize (e.g. harry ron draco)")
    parser.add_argument("--workers", type=int, default=1, help="Total parallel workers")
    parser.add_argument("--worker-id", type=int, default=0, help="Worker ID [0, workers-1]")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of lines to synthesize")
    parser.add_argument("--status", action="store_true", help="Show current dubbing progress")
    parser.add_argument("--inject", action="store_true", help="Inject synthesized audio into all 70 WAD files")
    parser.add_argument("--rebuild-iso", action="store_true", help="Rebuild final Turkish PS1 ISO")
    args = parser.parse_args()

    if args.status:
        print_status()
        return

    if args.inject:
        inject_into_wads()
        if args.rebuild_iso:
            from tools.build_turkish_iso import build_turkish_iso
            build_turkish_iso()
        return

    if args.rebuild_iso:
        from tools.build_turkish_iso import build_turkish_iso
        build_turkish_iso()
        return

    synthesize_lines(
        characters=args.char,
        worker_id=args.worker_id,
        num_workers=args.workers,
        limit=args.limit
    )


if __name__ == "__main__":
    main()
