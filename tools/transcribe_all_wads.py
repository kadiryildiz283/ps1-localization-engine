"""High-Speed Multi-Worker Whisper Transcription Engine for all PS1 Harry Potter WADs.

Extracts every audio cue from every level WAD in the untouched European disc,
transcribes it with Whisper, and detects exact spoken English lines and timestamps.
"""

import concurrent.futures
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.audio_vag import decode_adpcm_to_wav
from tools.dirdat import DirDatArchive
from tools.iso_fs import Ps1IsoReader

ORIGINAL_BIN = "Harry Potter and the Chamber of Secrets (Europe) (En,Fr,De).bin"
BASES_PATH = "audio/ground_truth_bases.json"
CACHE_DIR = "scratch/transcriptions"


def transcribe_wad_worker(args):
    wad_name, base_off = args
    stem = wad_name.replace(".WAD", "")
    cache_file = os.path.join(CACHE_DIR, f"{stem}.json")

    cached_entries = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, encoding="utf-8") as f:
                c_list = json.load(f)
                cached_entries = {c["cue"]: c for c in c_list}
        except Exception:
            cached_entries = {}

    with Ps1IsoReader(ORIGINAL_BIN) as iso:
        archive = DirDatArchive.from_iso(iso)
        if wad_name not in archive.entry_map:
            return wad_name, list(cached_entries.values())
        entry = archive.entry_map[wad_name]
        wad_bytes = iso.read_file_bytes("POTTER.DAT", entry.offset, entry.size)

    dne_pos = wad_bytes.find(b" DNE")
    if dne_pos == -1:
        return wad_name, list(cached_entries.values())
    audio_base = (dne_pos + 2047) // 2048 * 2048

    spsx = wad_bytes.find(b"XSPS")
    if spsx == -1:
        return wad_name, list(cached_entries.values())
    spsx_sz = struct.unpack("<I", wad_bytes[spsx+4:spsx+8])[0]
    spsx_data = wad_bytes[spsx+8 : spsx+8+spsx_sz]

    # Find total valid audio entries in SPSX table
    valid_cues_meta = []
    for c in range(2000):
        e_off = base_off + c * 16
        if e_off + 16 > len(spsx_data):
            break
        a_off, p2, p3, a_sz = struct.unpack("<IIII", spsx_data[e_off:e_off+16])
        if a_off == 0xffffffff or a_sz < 32 or audio_base + a_off + a_sz > len(wad_bytes):
            break
        hw = (p2 >> 16) & 0xffff
        dur = round((a_sz // 16 * 28) / 22050.0, 2)
        valid_cues_meta.append((c, e_off, a_off, hw, a_sz, dur))

    # If all cues are already cached, return immediately!
    if len(valid_cues_meta) <= len(cached_entries) and all(c[0] in cached_entries for c in valid_cues_meta):
        return wad_name, [cached_entries[c[0]] for c in valid_cues_meta]

    import torch
    torch.set_num_threads(2)
    from transformers import pipeline

    pipe = pipeline("automatic-speech-recognition", model="openai/whisper-tiny", device="cpu")
    wav_tmp_dir = os.path.join("scratch/tmp_wavs", stem)
    os.makedirs(wav_tmp_dir, exist_ok=True)

    results = []
    for c, e_off, a_off, hw, a_sz, dur in valid_cues_meta:
        if c in cached_entries:
            results.append(cached_entries[c])
            continue

        if hw != 2:
            results.append({
                "cue": c,
                "hw": hw,
                "audio_offset": a_off,
                "size_bytes": a_sz,
                "duration": dur,
                "table_entry_offset": e_off,
                "text": ""
            })
            continue

        chunk = wad_bytes[audio_base + a_off : audio_base + a_off + a_sz]
        wav_path = os.path.join(wav_tmp_dir, f"cue_{c}.wav")
        decode_adpcm_to_wav(chunk, wav_path)

        try:
            res = pipe(wav_path, generate_kwargs={"task": "transcribe"})
            txt = res.get("text", "").strip()
        except Exception as err:
            txt = f"ERR: {err}"

        try:
            os.remove(wav_path)
        except OSError:
            pass

        results.append({
            "cue": c,
            "hw": hw,
            "audio_offset": a_off,
            "size_bytes": a_sz,
            "duration": dur,
            "table_entry_offset": e_off,
            "text": txt
        })

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return wad_name, results


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs("scratch/tmp_wavs", exist_ok=True)

    with open(BASES_PATH, encoding="utf-8") as f:
        bases = json.load(f)

    # Skip cutscene WAD (T1L1M007 is already 100% completed)
    tasks = []
    for stem, info in sorted(bases.items()):
        if stem == "T1L1M007":
            continue
        wad_name = f"{stem}.WAD"
        base_off = info["base_offset"]
        tasks.append((wad_name, base_off))

    print(f"[*] Starting parallel Whisper transcription for {len(tasks)} level WADs with 8 workers...")
    t0 = time.time()
    completed = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(transcribe_wad_worker, t): t[0] for t in tasks}
        for future in concurrent.futures.as_completed(futures):
            wad_name = futures[future]
            try:
                w_name, res = future.result()
                completed += 1
                dt = time.time() - t0
                print(f"[{completed:2d}/{len(tasks)}] {wad_name:15s} total {len(res):3d} cues ({dt:.1f}s elapsed)")
            except Exception as e:
                print(f"[!] Error on {wad_name}: {e}")

    total_time = time.time() - t0
    print(f"\n[OK] All {completed} WADs fully transcribed and cached to {CACHE_DIR}/ in {total_time:.1f}s!")


if __name__ == "__main__":
    main()
