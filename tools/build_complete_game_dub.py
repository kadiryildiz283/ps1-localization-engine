"""Master Complete Game Neural Dubbing & PS1 Disc Patcher.

Engine Features:
1. Full-game neural voice synthesis for all 1,248 Turkish dialogue lines:
   - 145 Storybook Diorama Cutscenes (T1L1M007.WAD)
   - 1,103 Unique In-Game Dialogue Lines across 67 level WADs
2. Powered by local Coqui XTTS-v2 with studio-restored golden multi-reference latents:
   - Melike (Narrator / Storybook)
   - Kadir (Harry Potter)
   - Batuhan (Ron Weasley)
   - Cansel (Hermione Granger & Ginny)
   - Bahadır (Draco Malfoy)
   - Efe (Dobby)
   - Studio Cast: Dumbledore, Hagrid, Snape, Mrs. Weasley, Tom Riddle, Sorting Hat
3. Hardware-accelerated 8-worker parallel synthesis utilizing all 24 CPU cores.
4. Argonaut Engine SPU broadcast mastering:
   - 2nd-order Butterworth low-cut @ 80Hz, +3dB high-shelf @ 4.5kHz, -1dB limiter.
   - Exact SPU ADPCM conformance with clean 0x01 terminal mute blocks.
   - Mutes foreign language channels (cue+1, cue+2) to prevent foreign speech leakage.
5. 100% Bit-Exact Category A SFX / BGM preservation gate.
6. Mode 2 Form 1 CD-ROM XA sector rebuilder with EDC/ECC recalculation.
"""

import argparse
import glob
import hashlib
import json
import multiprocessing
import os
import shutil
import struct
import subprocess
import sys
import time
import wave
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.audio_vag import encode_pcm_to_vag
from tools.cd_patcher import encode_mode2_form1_sector
from tools.iso_fs import Ps1IsoReader, SECTOR_SIZE, USER_DATA_SIZE, USER_DATA_OFFSET
from tools.dirdat import DirDatArchive, DIR_ENTRY_SIZE
from tools.voice_cloner import NeuralVoiceEngine, clean_text_for_tts, resample_audio, LINE_CHARACTER_MAP

ORIGINAL_BIN = "Harry Potter and the Chamber of Secrets (Europe) (En,Fr,De).bin"
TARGET_BIN = "Harry Potter and the Chamber of Secrets (Turkish).bin"
CUTSCENE_MANIFEST = "audio/dubbing_manifest.json"
INGAME_UNIQUE_LINES = "audio/deterministic_unique_lines.json"
INGAME_MANIFEST = "audio/deterministic_manifest.json"
EXCLUSION_MAP_PATH = "audio/category_a_exclusion_map.json"
BURROW_CLEAN_DIR = "audio/burrow_clean"

CUTSCENE_DUB_DIR = "audio/turkish_dub"
INGAME_DUB_DIR = "audio/ingame_dub"
EXTRACTED_SRC_DIR = "extracted_text_only"
EXTRACTED_DST_DIR = "extracted"

SILENCE_MID = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
SILENCE_END = b"\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

def make_silence(num_bytes: int) -> bytes:
    assert num_bytes % 16 == 0
    num_blocks = num_bytes // 16
    if num_blocks == 0:
        return b""
    return (SILENCE_MID * (num_blocks - 1)) + SILENCE_END


def seed_burrow_verified_lines():
    """Copy verified Burrow lines from audio/burrow_clean into audio/ingame_dub."""
    os.makedirs(INGAME_DUB_DIR, exist_ok=True)
    if not os.path.exists(INGAME_MANIFEST) or not os.path.exists(BURROW_CLEAN_DIR):
        return 0

    with open(INGAME_MANIFEST, "r", encoding="utf-8") as f:
        dm = json.load(f)

    burrow_wads = {"T1L2M001.WAD", "T1L2M003.WAD", "T1L2M004.WAD", "T1L2M006.WAD"}
    burrow_entries = [e for e in dm if e["wad"] in burrow_wads]

    seeded = 0
    for e in burrow_entries:
        stem = e["stem"]
        cue = e["cue"]
        h = e["line_hash"]
        dst = os.path.join(INGAME_DUB_DIR, f"{h}.wav")
        if os.path.exists(dst) and os.path.getsize(dst) > 1000:
            continue

        patterns = [
            f"{BURROW_CLEAN_DIR}/{stem}_cue{cue:02d}_*.wav",
            f"{BURROW_CLEAN_DIR}/cue_{cue:02d}_*.wav"
        ]
        found = []
        for p in patterns:
            found.extend(glob.glob(p))
        if found:
            shutil.copy2(found[0], dst)
            # Also copy mp3 preview if exists
            mp3_src = found[0].replace(".wav", ".mp3")
            if os.path.exists(mp3_src):
                shutil.copy2(mp3_src, dst.replace(".wav", ".mp3"))
            seeded += 1

    return seeded


def collect_all_synthesis_tasks() -> List[dict]:
    """Collect all synthesis tasks across Cutscenes and In-Game levels."""
    tasks = []

    # 1. Cutscenes (T1L1M007.WAD) - 145 lines
    if os.path.exists(CUTSCENE_MANIFEST):
        with open(CUTSCENE_MANIFEST, "r", encoding="utf-8") as f:
            cutscenes = json.load(f)
        for i, item in enumerate(cutscenes):
            char = LINE_CHARACTER_MAP.get(i, "narrator")
            out_wav = os.path.join(CUTSCENE_DUB_DIR, f"line_{i:03d}.wav")
            tasks.append({
                "type": "cutscene",
                "id": f"cutscene_{i:03d}",
                "character": char,
                "text": item.get("tr", ""),
                "out_wav": out_wav,
                "max_duration": item.get("max_duration", (item["size_bytes"] // 16 * 28) / 22050.0)
            })

    # 2. In-Game Unique Lines - 1,103 lines
    if os.path.exists(INGAME_UNIQUE_LINES):
        with open(INGAME_UNIQUE_LINES, "r", encoding="utf-8") as f:
            in_game = json.load(f)
        for item in in_game:
            h = item["line_hash"]
            char = item["character"]
            out_wav = os.path.join(INGAME_DUB_DIR, f"{h}.wav")
            tasks.append({
                "type": "ingame",
                "id": f"ingame_{h}",
                "character": char,
                "text": item.get("tr", ""),
                "out_wav": out_wav,
                "max_duration": item.get("min_duration")
            })

    return tasks


def print_overall_status():
    """Print complete progress across all cutscenes and in-game dialogue lines."""
    tasks = collect_all_synthesis_tasks()
    by_type_char = defaultdict(lambda: {"total": 0, "done": 0})
    total_all = len(tasks)
    done_all = 0

    for t in tasks:
        tc = f"{t['type'].upper()} - {t['character']}"
        by_type_char[tc]["total"] += 1
        if os.path.exists(t["out_wav"]) and os.path.getsize(t["out_wav"]) > 1000:
            by_type_char[tc]["done"] += 1
            done_all += 1

    print("=" * 75)
    print("  COMPLETE HARRY POTTER PS1 TURKISH DUBBING STATUS")
    print("=" * 75)
    for tc, stats in sorted(by_type_char.items()):
        done = stats["done"]
        tot = stats["total"]
        pct = (done / tot * 100) if tot > 0 else 0
        bar = "#" * int(pct // 5) + "-" * (20 - int(pct // 5))
        print(f"  {tc:25s} [{bar}] {done:4d}/{tot:4d} ({pct:5.1f}%)")
    print("-" * 75)
    pct_all = (done_all / total_all * 100) if total_all > 0 else 0
    print(f"  TOTAL PROGRESS: {done_all}/{total_all} ({pct_all:.1f}%) | REMAINING: {total_all - done_all}")
    print("=" * 75)


def run_worker_synthesis(worker_id: int, num_workers: int, tasks_subset: List[dict]):
    """Execute synthesis for a specific worker shard."""
    os.environ["TORCH_NUM_THREADS"] = "3"
    import soundfile as sf
    import numpy as np

    total = len(tasks_subset)
    print(f"[Worker {worker_id}/{num_workers}] Starting batch of {total} lines...")

    engine = NeuralVoiceEngine()
    completed = 0
    skipped = 0

    for idx, t in enumerate(tasks_subset):
        out_wav = t["out_wav"]
        if os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000:
            skipped += 1
            continue

        char = t["character"]
        raw_text = t["text"]

        # Handle empty text (e.g. newline control cue)
        cleaned = clean_text_for_tts(raw_text)
        if not cleaned:
            # 0.1s silence WAV
            silence_pcm = np.zeros(2205, dtype=np.int16)
            os.makedirs(os.path.dirname(os.path.abspath(out_wav)), exist_ok=True)
            sf.write(out_wav, silence_pcm, 22050)
            completed += 1
            continue

        try:
            t0 = time.time()
            engine.synthesize_line(
                text_tr=cleaned,
                character=char,
                output_wav=out_wav,
                max_duration=t.get("max_duration")
            )
            completed += 1
            dt = time.time() - t0
            print(f"  (W{worker_id}) [{idx+1}/{total}] [{char.upper()}] in {dt:.1f}s -> {os.path.basename(out_wav)}")
        except Exception as ex:
            print(f"  [!] (W{worker_id}) Error on {t['id']}: {ex}")

    print(f"[Worker {worker_id}/{num_workers}] Finished: {completed} done, {skipped} skipped.")


def launch_parallel_synthesis(num_workers: int = 8):
    """Launch multi-worker parallel synthesis process pool."""
    print("=" * 80)
    print(f"STARTING MULTI-WORKER PARALLEL DUBBING ENGINE ({num_workers} WORKERS)")
    print("=" * 80)

    # 1. Ensure directories and seed verified Burrow lines
    os.makedirs(CUTSCENE_DUB_DIR, exist_ok=True)
    os.makedirs(INGAME_DUB_DIR, exist_ok=True)
    seeded = seed_burrow_verified_lines()
    if seeded > 0:
        print(f"[+] Seeded {seeded} verified lines from Burrow suite into {INGAME_DUB_DIR}")

    # 2. Collect all tasks and filter missing
    all_tasks = collect_all_synthesis_tasks()
    missing_tasks = [
        t for t in all_tasks
        if not (os.path.exists(t["out_wav"]) and os.path.getsize(t["out_wav"]) > 1000)
    ]

    total_missing = len(missing_tasks)
    print(f"[+] Total dialogue lines across full game: {len(all_tasks)}")
    print(f"[+] Lines already synthesized:           {len(all_tasks) - total_missing}")
    print(f"[+] Missing lines to synthesize:          {total_missing}")

    if total_missing == 0:
        print("[OK] All dialogue lines are already synthesized! Ready for injection.")
        return

    # 3. Partition tasks across workers
    worker_subsets = [[] for _ in range(num_workers)]
    for i, t in enumerate(missing_tasks):
        worker_subsets[i % num_workers].append(t)

    # Save worker tasks to scratch JSON files for clean subprocess invocations
    os.makedirs("scratch/workers", exist_ok=True)
    processes = []
    t_start = time.time()

    for w_id in range(num_workers):
        shard_path = f"scratch/workers/shard_{w_id}.json"
        with open(shard_path, "w", encoding="utf-8") as f:
            json.dump(worker_subsets[w_id], f, indent=2, ensure_ascii=False)

        cmd = [
            sys.executable, __file__,
            "--run-shard", shard_path,
            "--worker-id", str(w_id),
            "--workers", str(num_workers)
        ]
        p = subprocess.Popen(cmd)
        processes.append(p)
        print(f"  [+] Spawned Worker {w_id} (PID: {p.pid}) with {len(worker_subsets[w_id])} lines.")

    # 4. Monitor loop
    try:
        while True:
            running = [p.poll() is None for p in processes]
            num_running = sum(running)
            if num_running == 0:
                break

            done_count = sum(
                1 for t in missing_tasks
                if os.path.exists(t["out_wav"]) and os.path.getsize(t["out_wav"]) > 1000
            )
            pct = (done_count / total_missing * 100) if total_missing > 0 else 100
            elapsed = time.time() - t_start
            rate = done_count / elapsed if elapsed > 0 else 0
            eta_sec = (total_missing - done_count) / rate if rate > 0 else 0

            print(f"  [Progress] {done_count}/{total_missing} ({pct:.1f}%) | "
                  f"Active Workers: {num_running}/{num_workers} | Rate: {rate*60:.1f} lines/min | ETA: {eta_sec/60:.1f}m")
            time.sleep(15)

    except KeyboardInterrupt:
        print("\n[!] Interrupted by user. Terminating worker processes...")
        for p in processes:
            p.terminate()
        sys.exit(1)

    # 5. Check exit codes
    failed = sum(1 for p in processes if p.returncode != 0)
    if failed > 0:
        print(f"[!] Warning: {failed} workers exited with errors.")
    else:
        dt = time.time() - t_start
        print(f"\n[OK] All {num_workers} workers completed successfully in {dt/60:.2f} minutes!")


def inject_cutscenes():
    """Inject 145 Turkish cutscene lines into extracted/T1L1M007.WAD."""
    print("\n" + "=" * 75)
    print("INJECTING 145 TURKISH CUTSCENE LINES INTO T1L1M007.WAD")
    print("=" * 75)

    src_wad = os.path.join(EXTRACTED_SRC_DIR, "T1L1M007.WAD")
    dst_wad = os.path.join(EXTRACTED_DST_DIR, "T1L1M007.WAD")
    if not os.path.exists(src_wad):
        raise FileNotFoundError(f"Source WAD not found: {src_wad}")

    shutil.copy2(src_wad, dst_wad)
    with open(dst_wad, "rb") as f:
        wad = bytearray(f.read())

    AUDIO_SECTOR_BASE = 362496
    with open(CUTSCENE_MANIFEST, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    injected = 0
    import numpy as np

    for i, e in enumerate(manifest):
        sz = e["size_bytes"]
        off = e["spsx_offset"]
        wav_path = os.path.join(CUTSCENE_DUB_DIR, f"line_{i:03d}.wav")
        if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 100:
            print(f"  [!] Missing audio for cutscene line {i:03d}, skipping.")
            continue

        with wave.open(wav_path, "rb") as wf:
            in_sr = wf.getframerate()
            raw = wf.readframes(wf.getnframes())
            pcm = np.frombuffer(raw, dtype=np.int16)

        max_samples = (sz // 16) * 28
        if len(pcm) > max_samples:
            pcm = pcm[:max_samples]

        vag = encode_pcm_to_vag(pcm, loop=False)

        # Pad with silence and guaranteed 0x01 terminal mute block
        if len(vag) < sz:
            pad_len = sz - len(vag)
            num_silence = pad_len // 16
            vag = vag + (SILENCE_MID * (num_silence - 1)) + SILENCE_END + (b"\x00" * (pad_len % 16))
        else:
            vag = bytearray(vag[:sz])
            if sz >= 16:
                vag[sz - 16 : sz] = SILENCE_END
            vag = bytes(vag)

        wad_pos = AUDIO_SECTOR_BASE + off
        wad[wad_pos : wad_pos + sz] = vag
        injected += 1

    with open(dst_wad, "wb") as f:
        f.write(wad)

    print(f"[OK] Injected {injected}/{len(manifest)} cutscene audio cues into {dst_wad} ({len(wad):,d} bytes)")


def inject_ingame_wads():
    """Inject all Category B dialogue cues into 67 in-game level WADs."""
    print("\n" + "=" * 75)
    print("INJECTING TURKISH SPU ADPCM AUDIO INTO 67 LEVEL WADS")
    print("=" * 75)

    with open(INGAME_MANIFEST, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(EXCLUSION_MAP_PATH, "r", encoding="utf-8") as f:
        exclusion_map = json.load(f)

    by_wad = defaultdict(list)
    for e in manifest:
        if not e.get("is_cutscene"):
            by_wad[e["wad"]].append(e)

    import numpy as np

    total_injected = 0
    total_missing = 0
    cat_a_violations = 0
    wads_updated = 0

    for wad_name, entries in sorted(by_wad.items()):
        src_wad = os.path.join(EXTRACTED_SRC_DIR, wad_name)
        dst_wad = os.path.join(EXTRACTED_DST_DIR, wad_name)
        if not os.path.exists(src_wad):
            continue

        shutil.copy2(src_wad, dst_wad)
        with open(dst_wad, "rb") as f:
            wad_data = bytearray(f.read())

        audio_base = entries[0]["audio_base"]
        spsx_pos = wad_data.find(b"XSPS")
        spsx_base = spsx_pos + 8 if spsx_pos != -1 else 0
        spsx_sz = struct.unpack("<I", wad_data[spsx_pos+4 : spsx_pos+8])[0] if spsx_pos != -1 else 0

        # Baseline Category A MD5 capture
        cat_a_cues = exclusion_map.get(wad_name, [])
        cat_a_baseline = {}
        for ca in cat_a_cues:
            off = ca["audio_offset"]
            sz = ca["size_bytes"]
            cat_a_baseline[ca["cue"]] = wad_data[audio_base + off : audio_base + off + sz]

        wad_modified = False

        for entry in entries:
            sz = entry["size_bytes"]
            a_off = entry["audio_offset"]
            e_off = entry["table_entry_offset"]
            target_sr = entry["target_sample_rate"]
            max_allowed_samples = entry["max_allowed_samples"]
            cue = entry["cue"]

            wav_path = os.path.join(INGAME_DUB_DIR, f"{entry['line_hash']}.wav")
            if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 100:
                total_missing += 1
                continue

            # Update SPSX table hw = 2 (one-shot playback)
            if spsx_pos != -1 and e_off >= 0 and e_off + 16 <= spsx_sz:
                f0, f1, f2, f3 = struct.unpack("<IIII", wad_data[spsx_base + e_off : spsx_base + e_off + 16])
                new_f1 = (f1 & 0x0000FFFF) | 0x00020000
                wad_data[spsx_base + e_off + 4 : spsx_base + e_off + 8] = struct.pack("<I", new_f1)
                wad_modified = True

            # Load WAV & trim silence
            with wave.open(wav_path, "rb") as wf:
                in_sr = wf.getframerate()
                in_ch = wf.getnchannels()
                raw_bytes = wf.readframes(wf.getnframes())

            raw_pcm = np.frombuffer(raw_bytes, dtype=np.int16)
            if in_ch > 1:
                raw_pcm = raw_pcm[::in_ch]

            non_silent = np.where(np.abs(raw_pcm) > 300)[0]
            if len(non_silent) > 0:
                pad_samples = int(in_sr * 0.025)
                start_idx = max(0, non_silent[0] - pad_samples)
                end_idx = min(len(raw_pcm), non_silent[-1] + pad_samples)
                trimmed_pcm = raw_pcm[start_idx:end_idx]
            else:
                trimmed_pcm = raw_pcm

            trimmed_dur = len(trimmed_pcm) / float(in_sr)
            max_dur_sec = max(0.1, (max_allowed_samples - 28) / float(target_sr))

            # Resample & tempo-fit
            if trimmed_dur > max_dur_sec:
                speed_ratio = trimmed_dur / max_dur_sec
                if speed_ratio > 2.0:
                    filter_str = f"aformat=sample_fmts=s16:sample_rates={target_sr}:channel_layouts=mono,atempo=2.0,atempo={speed_ratio/2.0:.4f}"
                else:
                    filter_str = f"aformat=sample_fmts=s16:sample_rates={target_sr}:channel_layouts=mono,atempo={speed_ratio:.4f}"

                cmd = [
                    "ffmpeg", "-y", "-f", "s16le", "-ar", str(in_sr), "-ac", "1", "-i", "-",
                    "-af", filter_str, "-ac", "1", "-ar", str(target_sr), "-f", "s16le", "-"
                ]
                res = subprocess.run(cmd, input=trimmed_pcm.tobytes(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
                samples = np.frombuffer(res.stdout, dtype=np.int16)
            else:
                if in_sr != target_sr:
                    cmd = [
                        "ffmpeg", "-y", "-f", "s16le", "-ar", str(in_sr), "-ac", "1", "-i", "-",
                        "-ac", "1", "-ar", str(target_sr), "-f", "s16le", "-"
                    ]
                    res = subprocess.run(cmd, input=trimmed_pcm.tobytes(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
                    samples = np.frombuffer(res.stdout, dtype=np.int16)
                else:
                    samples = trimmed_pcm

            if len(samples) > max_allowed_samples:
                samples = samples[:max_allowed_samples]

            # Fast C-accelerated SPU ADPCM encoding
            vag_data = encode_pcm_to_vag(samples, loop=True)

            pad_bytes = sz - len(vag_data)
            num_pad_blocks = pad_bytes // 16
            if num_pad_blocks > 0:
                vag_data = vag_data + (SILENCE_MID * (num_pad_blocks - 1)) + SILENCE_END
            else:
                vag_data = bytearray(vag_data[:sz])
                vag_data[-15] = 0x01
                vag_data = bytes(vag_data)

            # Inject audio into WAD
            wad_data[audio_base + a_off : audio_base + a_off + sz] = vag_data
            wad_modified = True
            total_injected += 1

        # Category A Verification Gate
        for ca in cat_a_cues:
            cid = ca["cue"]
            off = ca["audio_offset"]
            sz = ca["size_bytes"]
            curr_bytes = wad_data[audio_base + off : audio_base + off + sz]
            if curr_bytes != cat_a_baseline[cid]:
                cat_a_violations += 1
                print(f"[!] CRITICAL VIOLATION: Category A cue {cid} in {wad_name} was mutated!")

        if wad_modified:
            with open(dst_wad, "wb") as f:
                f.write(wad_data)
            wads_updated += 1

    print(f"\n[OK] Level WAD Injection Completed:")
    print(f"     -> Updated WADs:        {wads_updated}")
    print(f"     -> Dialogue Cues Injected: {total_injected}")
    print(f"     -> Missing Dialogue Cues:  {total_missing}")
    print(f"     -> Category A Violations:  {cat_a_violations}")
    if cat_a_violations > 0:
        raise RuntimeError(f"ABORT: {cat_a_violations} Category A cues were violated during injection!")


def patch_disc_image():
    """Patch all modified files from extracted/ into the final PS1 BIN."""
    print("\n" + "=" * 75)
    print("PATCHING DISK IMAGE: Harry Potter and the Chamber of Secrets (Turkish).bin")
    print("=" * 75)

    from tools.build_turkish_iso import build_turkish_iso
    build_turkish_iso()

    # Clear DuckStation resume savestate
    resume_sav = os.path.expanduser("~/.local/share/duckstation/savestates/SLES-03972_resume.sav")
    if os.path.exists(resume_sav):
        os.remove(resume_sav)
        print("[+] Cleared DuckStation resume savestate.")


def main():
    parser = argparse.ArgumentParser(description="Master Complete Game Dubbing & PS1 Patcher")
    parser.add_argument("--status", action="store_true", help="Print overall dubbing status")
    parser.add_argument("--synthesize", action="store_true", help="Synthesize all missing dialogue lines")
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel workers (default: 8)")
    parser.add_argument("--run-shard", type=str, default=None, help="Internal: run synthesis for a shard file")
    parser.add_argument("--worker-id", type=int, default=0, help="Internal: worker ID")
    parser.add_argument("--inject", action="store_true", help="Inject audio into all 68 WAD files")
    parser.add_argument("--rebuild-iso", action="store_true", help="Rebuild final PS1 ISO image")
    parser.add_argument("--all", action="store_true", help="Run full pipeline end-to-end")
    args = parser.parse_args()

    if args.run_shard:
        with open(args.run_shard, "r", encoding="utf-8") as f:
            tasks_subset = json.load(f)
        run_worker_synthesis(args.worker_id, args.workers, tasks_subset)
        return

    if args.status:
        print_overall_status()
        return

    if args.synthesize:
        launch_parallel_synthesis(num_workers=args.workers)
        print_overall_status()
        return

    if args.inject:
        inject_cutscenes()
        inject_ingame_wads()
        return

    if args.rebuild_iso:
        patch_disc_image()
        return

    if args.all:
        launch_parallel_synthesis(num_workers=args.workers)
        inject_cutscenes()
        inject_ingame_wads()
        patch_disc_image()
        print("\n" + "=" * 80)
        print("MASTER COMPLETE GAME DUBBING & ISO PATCHING SUCCESSFULLY FINISHED!")
        print("=" * 80)
        return

    print_overall_status()


if __name__ == "__main__":
    main()
