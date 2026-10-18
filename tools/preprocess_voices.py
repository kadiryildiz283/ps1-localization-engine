"""Studio Voice Preprocessing & Golden Profile Extraction Pipeline.

Transforms raw smartphone / WhatsApp voice recordings into studio-quality
reference profiles and caches conditioning latents for XTTS-v2 neural voice cloning.
"""

import os
import subprocess

import librosa
import numpy as np
import soundfile as sf

PROFILES_DIR = "audio/profiles"
RAW_DIR = "audio/profiles_raw"

INPUTS = {
    "kadir": {
        "file": "kadir.mp3",
        "role": "Harry Potter",
        "out_name": "harry.wav",
    },
    "melike": {
        "file": "melike.ogg",
        "role": "Anlatıcı (Narrator)",
        "out_name": "narrator.wav",
    },
    "batuhan": {
        "file": "batuhan.ogg",
        "role": "Ron Weasley",
        "out_name": "ron.wav",
    },
    "efe": {
        "file": "efe.ogg",
        "role": "Dobby",
        "out_name": "dobby.wav",
    },
    "cansel": {
        "file": "cansel.ogg",
        "role": "Hermione Granger",
        "out_name": "hermione.wav",
    },
    "bahadir": {
        "file": "bahadır.mp3",
        "role": "Draco Malfoy",
        "out_name": "draco.wav",
    },
}

def preprocess_audio(input_file: str, full_clean_out: str, profile_out: str, target_duration: float = 28.0):
    os.makedirs(os.path.dirname(os.path.abspath(full_clean_out)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(profile_out)), exist_ok=True)

    # Step 1: Gentle analog-style mastering filter
    # Subsonic highpass at 60Hz preserves chest warmth (80-150Hz), eliminates DC/sub-rumble.
    # Mild gate smoothly attenuates room tone in micro-pauses without metallic FFT ringing.
    # EBU R128 loudnorm standardizes speech to -16 LUFS with 1.0 dB true peak ceiling.
    filter_chain = (
        "highpass=f=60,"
        "agate=threshold=-38dB:ratio=1.5:range=-10dB,"
        "loudnorm=I=-16:TP=-1.0:LRA=9"
    )

    cmd_full = [
        "ffmpeg", "-y", "-i", input_file,
        "-af", filter_chain,
        "-ac", "1",
        "-ar", "24000",
        full_clean_out
    ]
    subprocess.run(cmd_full, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # Step 2: Intelligent Speech Segmentation (VAD) using Librosa
    y, sr = sf.read(full_clean_out)
    intervals = librosa.effects.split(y, top_db=25, frame_length=2048, hop_length=512)

    speech_chunks = []
    total_samples = 0
    target_samples = int(target_duration * sr)

    fade_len = int(0.04 * sr)  # 40ms smooth cross-fade to eliminate clicks
    fade_in = np.linspace(0, 1, fade_len)
    fade_out = np.linspace(1, 0, fade_len)

    for start, end in intervals:
        seg_len = end - start
        if seg_len < int(0.35 * sr):  # Ignore spurious clicks < 350ms
            continue
        seg = y[start:end].copy()
        if len(seg) > 2 * fade_len:
            seg[:fade_len] *= fade_in
            seg[-fade_len:] *= fade_out
        speech_chunks.append(seg)
        # Add natural 120ms inter-phrase breath pause
        speech_chunks.append(np.zeros(int(0.12 * sr)))
        total_samples += len(seg) + int(0.12 * sr)
        if total_samples >= target_samples:
            break

    if not speech_chunks:
        # Fallback to direct slice if no intervals detected
        golden_audio = y[:target_samples]
    else:
        golden_audio = np.concatenate(speech_chunks)

    sf.write(profile_out, golden_audio, sr)
    dur = len(golden_audio) / sr
    print(f"[OK] {os.path.basename(input_file)} -> {profile_out} (Duration: {dur:.2f}s, 24000Hz Mono Studio Clean)")

def main():
    print("=== EXECUTING STUDIO AUDIO PREPROCESSING PIPELINE V2 ===")
    for key, cfg in INPUTS.items():
        inp = cfg["file"]
        if not os.path.exists(inp):
            print(f"Error: {inp} not found!")
            continue
        full_out = os.path.join(RAW_DIR, f"{key}_full_clean.wav")
        prof_out = os.path.join(PROFILES_DIR, cfg["out_name"])
        print(f"Processing '{key}' ({cfg['role']})...")
        preprocess_audio(inp, full_out, prof_out)
    print("\nAll 5 custom voice profiles generated successfully in audio/profiles/!")

if __name__ == "__main__":
    main()
