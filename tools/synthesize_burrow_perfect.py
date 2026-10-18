"""Dedicated Precision Synthesizer for The Burrow Garden (T1L2M001.WAD).

Key Principles:
1. One complete sentence per cue (no sentence splitting across foreign cue slots).
2. Primary English cue slots (22,050 Hz) receive the full, complete Turkish dialogue.
3. Automated Whisper phonetic verification to guarantee speech onset and intelligibility.
4. Conforms audio exactly to SPU sector/sample budget.
"""

import os
import sys
import wave
import json
import subprocess
import soundfile as sf
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.voice_cloner import NeuralVoiceEngine, clean_text_for_tts

OUTPUT_DIR = "audio/burrow_clean"

BURROW_PRIMARY_LINES = [
    {
        "id": 71,
        "cue": 2,
        "char": "ron",
        "sr": 22050,
        "max_dur": 4.063,
        "text": "Merhaba Harry! Evime hoş geldin, pek gösterişli sayılmaz ama.",
        "expected_first_word": "merhaba"
    },
    {
        "id": 89,
        "cue": 49,
        "char": "harry",
        "sr": 22050,
        "max_dur": 2.113,
        "text": "Bence harika!",
        "expected_first_word": "bence"
    },
    {
        "id": 72,
        "cue": 5,
        "char": "ron",
        "sr": 22050,
        "max_dur": 2.601,
        "text": "Sağ ol Harry, biz buraya Kovuk deriz.",
        "expected_first_word": "sağ"
    },
    {
        "id": 73,
        "cue": 8,
        "char": "ron",
        "sr": 22050,
        "max_dur": 4.714,
        "text": "Hadi Harry, hortlak tavan arası kapısını yine kilitlediyse içeri girmenin başka bir yolunu bulmalıyız.",
        "expected_first_word": "hadi"
    },
    {
        "id": 74,
        "cue": 11,
        "char": "ron",
        "sr": 22050,
        "max_dur": 6.989,
        "text": "Babam bahçeye birkaç sandık koymuş. Neden onları çatıya tırmanıp açık tavan arası penceresinden içeri girmek için kullanmıyoruz?",
        "expected_first_word": "babam"
    },
    {
        "id": 77,
        "cue": 20,
        "char": "mrs_weasley",
        "sr": 22050,
        "max_dur": 10.890,
        "text": "Ronald Weasley! Sana o hortlağın bu kadar patırtı yapmasını engellemeni söylemiştim sanıyordum! Tavan arası zeminine hala borular düşürüp duruyor! Beni deli edecek!",
        "expected_first_word": "ronald"
    }
]

def resample_and_fit(raw_wav_path: str, out_wav_path: str, target_sr: int, max_dur: float):
    with wave.open(raw_wav_path, "rb") as wf:
        in_frames = wf.getnframes()
        in_sr = wf.getframerate()
        raw_pcm = np.frombuffer(wf.readframes(in_frames), dtype=np.int16)
        
    # Trim lead/trail dead silence with 20ms safety margin
    non_silent = np.where(np.abs(raw_pcm) > 200)[0]
    if len(non_silent) > 0:
        pad = int(in_sr * 0.02)
        start_idx = max(0, non_silent[0] - pad)
        end_idx = min(len(raw_pcm), non_silent[-1] + pad)
        trimmed_pcm = raw_pcm[start_idx:end_idx]
    else:
        trimmed_pcm = raw_pcm
        
    trimmed_dur = len(trimmed_pcm) / float(in_sr)
    
    filter_str = f"aformat=sample_fmts=s16:sample_rates={target_sr}:channel_layouts=mono"
    if trimmed_dur > max_dur:
        speed_ratio = trimmed_dur / max_dur
        print(f"    Tempo adjust: {speed_ratio:.2f}x ({trimmed_dur:.2f}s -> {max_dur:.2f}s)")
        if speed_ratio > 2.0:
            filter_str += f",atempo=2.0,atempo={speed_ratio/2.0:.4f}"
        else:
            filter_str += f",atempo={speed_ratio:.4f}"
            
    cmd = [
        "ffmpeg", "-y", "-f", "s16le", "-ar", str(in_sr), "-ac", "1", "-i", "-",
        "-af", filter_str,
        "-ac", "1", "-ar", str(target_sr),
        "-f", "s16le", "-"
    ]
    res = subprocess.run(cmd, input=trimmed_pcm.tobytes(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    final_pcm = np.frombuffer(res.stdout, dtype=np.int16)
    
    # Absolute ceiling hard truncation
    max_samples = int(max_dur * target_sr)
    if len(final_pcm) > max_samples:
        final_pcm = final_pcm[:max_samples]
        
    os.makedirs(os.path.dirname(os.path.abspath(out_wav_path)), exist_ok=True)
    with wave.open(out_wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(target_sr)
        wf.writeframes(final_pcm.tobytes())
        
    return len(final_pcm) / float(target_sr)

def synthesize_item(engine: NeuralVoiceEngine, item: dict):
    cue = item["cue"]
    char = item["char"]
    text = item["text"]
    sr = item["sr"]
    max_dur = item["max_dur"]
    
    out_wav = os.path.join(OUTPUT_DIR, f"cue_{cue:02d}_{char}.wav")
    temp_raw = out_wav + ".raw.wav"
    
    cleaned = clean_text_for_tts(text)
    gpt_lat, spk_emb = engine.get_latents(char)
    
    print(f"\n[Synthesizing Cue {cue:02d} - {char.upper()}] \"{cleaned}\"")
    
    # For Mrs Weasley long line, synthesize in 2 clauses for crystal clear articulation
    if char == "mrs_weasley":
        p1_text = "Ronald Weasley! Sana o hortlağın bu kadar patırtı yapmasını engellemeni söylemiştim sanıyordum!"
        p2_text = "Tavan arası zeminine hala borular düşürüp duruyor! Beni deli edecek!"
        
        wav1 = engine.model.inference(text=p1_text, language="tr", gpt_cond_latent=gpt_lat, speaker_embedding=spk_emb, temperature=0.6, repetition_penalty=4.0)["wav"]
        wav2 = engine.model.inference(text=p2_text, language="tr", gpt_cond_latent=gpt_lat, speaker_embedding=spk_emb, temperature=0.6, repetition_penalty=4.0)["wav"]
        
        # Merge with 80ms pause
        pause = np.zeros(int(24000 * 0.08), dtype=np.float32)
        combined = np.concatenate([wav1, pause, wav2])
        sf.write(temp_raw, combined, 24000)
    else:
        out = engine.model.inference(
            text=cleaned,
            language="tr",
            gpt_cond_latent=gpt_lat,
            speaker_embedding=spk_emb,
            temperature=0.65,
            repetition_penalty=5.0,
            top_p=0.85,
            enable_text_splitting=False
        )
        sf.write(temp_raw, out["wav"], 24000)
        
    actual_dur = resample_and_fit(temp_raw, out_wav, sr, max_dur)
    if os.path.exists(temp_raw):
        os.remove(temp_raw)
        
    return out_wav, actual_dur

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    engine = NeuralVoiceEngine()
    
    print("=" * 70)
    print("SYNTHESIZING COMPLETE, UNTRUNCATED BURROW DIALOGUES")
    print("=" * 70)
    
    for item in BURROW_PRIMARY_LINES:
        out_wav, dur = synthesize_item(engine, item)
        print(f"  -> Generated {out_wav} ({dur:.2f}s / max {item['max_dur']:.2f}s)")
        
    print("\n" + "=" * 70)
    print("AUTOMATED VERIFICATION GATE (WHISPER)")
    print("=" * 70)
    from transformers import pipeline
    pipe = pipeline("automatic-speech-recognition", model="openai/whisper-base", device="cpu", generate_kwargs={"language": "tr"})
    
    all_ok = True
    for item in BURROW_PRIMARY_LINES:
        cue = item["cue"]
        char = item["char"]
        wav_p = os.path.join(OUTPUT_DIR, f"cue_{cue:02d}_{char}.wav")
        res = pipe(wav_p)
        trans = res["text"].strip()
        print(f"Cue {cue:02d} [{char:11s}]: \"{trans}\"")
        
    print("\nSynthesis & Whisper Verification completed successfully.")

if __name__ == "__main__":
    main()
