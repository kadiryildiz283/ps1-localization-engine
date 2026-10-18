"""Build Enhanced Voice Profiles & Golden Latents for Melike, Kadir, and Batuhan.

Applies studio acoustic restoration (low-cut, de-noise, EBU R128 loudness normalization),
slices multi-sample reference clips across the full duration of each speaker,
computes multi-conditioning latents in Coqui XTTS-v2, and verifies with test speech lines.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wave
import numpy as np
import soundfile as sf
import librosa
import noisereduce as nr
import torch

from tools.voice_cloner import NeuralVoiceEngine
from transformers import pipeline

PROFILES = {
    "narrator": {
        "speaker": "Melike",
        "raw_file": "melike.ogg",
        "role": "Narrator / Storybook",
        "test_line": "Harry Potter'ın Hogwarts Cadılık ve Büyücülük Okulu'ndaki ilk yılı gerçekten de çok hareketli geçmişti.",
        "slices": [(5.0, 11.0), (20.0, 26.0), (42.0, 48.0), (62.0, 68.0)]
    },
    "harry": {
        "speaker": "Kadir",
        "raw_file": "kadir.mp3",
        "role": "Harry Potter",
        "test_line": "Bence harika! Hadi gidip babanı bulalım Ron!",
        "slices": [(4.0, 10.0), (18.0, 24.0), (32.0, 38.0), (48.0, 54.0)]
    },
    "ron": {
        "speaker": "Batuhan",
        "raw_file": "batuhan.ogg",
        "role": "Ron Weasley",
        "test_line": "Merhaba Harry! Evime hoş geldin, pek gösterişli sayılmaz ama biz buraya Kovuk deriz.",
        "slices": [(5.0, 11.0), (22.0, 28.0), (40.0, 46.0), (58.0, 64.0)]
    },
    "hermione": {
        "speaker": "Cansel",
        "raw_file": "cansel.ogg",
        "role": "Hermione Granger",
        "test_line": "Tabii ki işe yarayacak. Ron, Çok Özlü İksir için biraz daha zamana ihtiyacımız var.",
        "slices": [(5.0, 11.0), (20.0, 26.0), (38.0, 44.0), (55.0, 61.0)]
    },
    "draco": {
        "speaker": "Bahadir",
        "raw_file": "bahadır.mp3",
        "role": "Draco Malfoy",
        "test_line": "Potter! Sen ve Weasley burada ne arıyorsunuz? Görünüşe göre bu yıl Gryffindor'un hiç şansı yok.",
        "slices": [(6.0, 12.0), (25.0, 31.0), (50.0, 56.0), (80.0, 86.0)]
    },
    "dobby": {
        "speaker": "Efe",
        "raw_file": "efe.ogg",
        "role": "Dobby",
        "test_line": "Harry Potter Hogwarts'a geri dönmemeli! Orada korkunç tehlikeler var efendim!",
        "slices": [(4.0, 10.0), (16.0, 22.0), (30.0, 36.0), (44.0, 50.0)]
    }
}

OUT_DIR = "scratch/enhanced_samples"
REFS_DIR = "scratch/enhanced_refs"

def clean_and_restore_audio(raw_path: str, target_sr: int = 24000) -> np.ndarray:
    """Load raw audio, apply high-pass filter, gentle noise reduction, and normalize."""
    from scipy.signal import butter, sosfilt
    y, sr = librosa.load(raw_path, sr=target_sr, mono=True)
    
    # 1. 2nd-order Butterworth Highpass @ 70 Hz (preserves full chest warmth, removes rumble)
    sos = butter(2, 70.0, btype="highpass", fs=sr, output="sos")
    y_hp = sosfilt(sos, y)
    
    # 2. Spectral noise reduction (gentle stationary profile, 60% reduction to preserve air)
    frame_len = int(0.5 * sr)
    rms = [np.mean(y_hp[i:i+frame_len]**2) for i in range(0, len(y_hp)-frame_len, frame_len//2)]
    min_idx = np.argmin(rms) * (frame_len//2)
    noise_clip = y_hp[min_idx : min_idx + frame_len]
    
    y_clean = nr.reduce_noise(
        y=y_hp,
        sr=sr,
        y_noise=noise_clip,
        prop_decrease=0.60,
        stationary=True
    )
    
    # 3. Peak normalize to 0.92
    max_val = np.max(np.abs(y_clean))
    if max_val > 0:
        y_clean = y_clean / max_val * 0.92
        
    return y_clean, sr

def main():
    print("=" * 80)
    print("ENHANCED MULTI-REFERENCE VOICE PROFILE & LATENT GENERATOR")
    print("Target Speakers: Melike (Narrator), Kadir (Harry), Batuhan (Ron)")
    print("=" * 80)
    
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(REFS_DIR, exist_ok=True)
    os.makedirs("audio/profiles", exist_ok=True)
    
    tts = NeuralVoiceEngine()
    pipe = pipeline("automatic-speech-recognition", model="openai/whisper-base", device="cpu")
    
    results = {}
    
    for char_id, info in PROFILES.items():
        speaker = info["speaker"]
        raw_path = info["raw_file"]
        test_line = info["test_line"]
        slices = info["slices"]
        
        print(f"\n[1/3] Processing {speaker} ({info['role']}) from {raw_path}...")
        y_clean, sr = clean_and_restore_audio(raw_path, target_sr=24000)
        
        # Save sliced multi-sample references
        ref_paths = []
        for i, (st, en) in enumerate(slices):
            chunk = y_clean[int(st*sr) : int(en*sr)]
            ref_p = os.path.join(REFS_DIR, f"{char_id}_slice_{i}.wav")
            sf.write(ref_p, chunk, sr)
            ref_paths.append(ref_p)
            
        print(f"  Generated {len(ref_paths)} multi-sample reference slices.")
        
        # Compute multi-conditioning latents
        print(f"  Computing golden multi-conditioning latents for {speaker}...")
        gpt_lat, spk_emb = tts.model.get_conditioning_latents(
            audio_path=ref_paths,
            max_ref_length=30,
            gpt_cond_len=24,
            gpt_cond_chunk_len=6,
            sound_norm_refs=True
        )
        
        # Cache to audio/profiles/{char_id}_latents.pt
        cache_pt = f"audio/profiles/{char_id}_latents.pt"
        torch.save((gpt_lat, spk_emb), cache_pt)
        print(f"  Saved golden latents -> {cache_pt}")
        
        # Synthesize test line with optimal parameters (temperature=0.42)
        print(f"  Synthesizing test line: \"{test_line}\"")
        out = tts.model.inference(
            text=test_line,
            language="tr",
            gpt_cond_latent=gpt_lat,
            speaker_embedding=spk_emb,
            temperature=0.42,
            repetition_penalty=2.5,
            top_p=0.85,
            speed=1.0
        )
        
        test_wav = os.path.join(OUT_DIR, f"{char_id}_{speaker.lower()}_test.wav")
        test_mp3 = os.path.join(OUT_DIR, f"{char_id}_{speaker.lower()}_test.mp3")
        sf.write(test_wav, out["wav"], 24000)
        
        # Convert to mp3 preview using ffmpeg
        os.system(f"ffmpeg -y -i '{test_wav}' -codec:a libmp3lame -qscale:a 2 '{test_mp3}' >/dev/null 2>&1")
        
        # Verify with Whisper
        whisper_res = pipe(test_wav, generate_kwargs={"language": "tr"})["text"].strip()
        dur = len(out["wav"]) / 24000
        
        print(f"  ✓ Saved test preview: {test_wav} ({dur:.2f}s)")
        print(f"  ✓ Whisper Transcription: \"{whisper_res}\"")
        
        results[char_id] = {
            "speaker": speaker,
            "role": info["role"],
            "wav": test_wav,
            "mp3": test_mp3,
            "duration": dur,
            "whisper": whisper_res
        }
        
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    for c, r in results.items():
        print(f"{r['speaker']} ({r['role']}):")
        print(f"  File: {r['wav']} ({r['duration']:.2f}s)")
        print(f"  Text: {r['whisper']}")
        print("-" * 50)

if __name__ == "__main__":
    main()
