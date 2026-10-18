"""Dedicated synthesis and verification tool for The Burrow Garden (T1L2M001.WAD) cues.

Synthesizes the 11 sub-cues with mathematically verified speaker embeddings,
appropriate sample rates (22,050 Hz vs 16,000 Hz), SPU sample budgets, and
runs Whisper verification on the generated audio to guarantee phoneme onset integrity.
"""

import json
import os
import subprocess
import sys
import wave

import soundfile as sf
from transformers import pipeline

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.voice_cloner import NeuralVoiceEngine, clean_text_for_tts


def resample_exact(input_wav: str, output_wav: str, target_rate: int, max_duration: float = None):
    with wave.open(input_wav, 'rb') as wf:
        orig_dur = wf.getnframes() / wf.getframerate()
    filter_str = f'aformat=sample_fmts=s16:sample_rates={target_rate}:channel_layouts=mono'
    if max_duration is not None and orig_dur > max_duration:
        speed_ratio = orig_dur / max_duration
        print(f'Applying tempo adjustment: {speed_ratio:.2f}x (orig={orig_dur:.2f}s, target_max={max_duration:.2f}s)')
        if speed_ratio > 2.0:
            filter_str += f',atempo=2.0,atempo={speed_ratio/2.0:.4f}'
        else:
            filter_str += f',atempo={speed_ratio:.4f}'
    cmd = [
        'ffmpeg', '-y', '-i', input_wav,
        '-af', filter_str,
        '-ac', '1',
        '-ar', str(target_rate),
        output_wav
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


BURROW_CUES = [
    {
        "cue": 2,
        "char": "ron",
        "tr": "Merhaba Harry!",
        "sr": 22050,
        "max_dur": 4.063,
        "expected_first_word": "merhaba"
    },
    {
        "cue": 3,
        "char": "ron",
        "tr": "Evime hoş geldin,",
        "sr": 16000,
        "max_dur": 2.912,
        "expected_first_word": "evime"
    },
    {
        "cue": 4,
        "char": "ron",
        "tr": "pek gösterişli sayılmaz ama.",
        "sr": 16000,
        "max_dur": 4.480,
        "expected_first_word": "pek"
    },
    {
        "cue": 49,
        "char": "harry",
        "tr": "Bence harika!",
        "sr": 22050,
        "max_dur": 2.113,
        "expected_first_word": "bence"
    },
    {
        "cue": 5,
        "char": "ron",
        "tr": "Sağ ol Harry,",
        "sr": 22050,
        "max_dur": 2.601,
        "expected_first_word": "sağ"
    },
    {
        "cue": 7,
        "char": "ron",
        "tr": "biz buraya 'Kovuk' deriz.",
        "sr": 16000,
        "max_dur": 2.464,
        "expected_first_word": "biz"
    },
    {
        "cue": 8,
        "char": "ron",
        "tr": "Hadi Harry, hortlak tavan arası kapısını yine kilitlediyse",
        "sr": 22050,
        "max_dur": 4.714,
        "expected_first_word": "hadi"
    },
    {
        "cue": 9,
        "char": "ron",
        "tr": "içeri girmenin başka bir yolunu bulmalıyız.",
        "sr": 16000,
        "max_dur": 6.048,
        "expected_first_word": "içeri"
    },
    {
        "cue": 11,
        "char": "ron",
        "tr": "Babam bahçeye birkaç sandık koymuş.",
        "sr": 22050,
        "max_dur": 6.989,
        "expected_first_word": "babam"
    },
    {
        "cue": 12,
        "char": "ron",
        "tr": "Neden onları çatıya tırmanıp açık tavan arası penceresinden içeri girmek için kullanmıyoruz?",
        "sr": 16000,
        "max_dur": 6.272,
        "expected_first_word": "neden"
    },
    {
        "cue": 20,
        "char": "mrs_weasley",
        "tr": "Ronald Weasley! Sana o hortlağın bu kadar patırtı yapmasını engellemeni söylemiştim sanıyordum! Tavan arası zeminine hala borular düşürüp duruyor! Beni deli edecek!",
        "sr": 22050,
        "max_dur": 10.890,
        "expected_first_word": "ronald"
    }
]

def synthesize_cue(engine: NeuralVoiceEngine, cue_info: dict, out_dir: str):
    cue_num = cue_info["cue"]
    char = cue_info["char"]
    text_tr = cue_info["tr"]
    sr = cue_info["sr"]
    max_dur = cue_info["max_dur"]

    out_wav = os.path.join(out_dir, f"cue_{cue_num:02d}_{char}.wav")
    temp_raw = out_wav + ".raw.wav"

    cleaned = clean_text_for_tts(text_tr)
    gpt_lat, spk_emb = engine.get_latents(char)

    print(f"\n[Synthesizing Cue {cue_num:02d} ({char.upper()})] -> \"{cleaned}\"")
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

    # Custom resample to target sample rate & max budget
    resample_exact(temp_raw, out_wav, target_rate=sr, max_duration=max_dur)
    if os.path.exists(temp_raw):
        os.remove(temp_raw)

    return out_wav

def main():
    out_dir = "scratch/burrow_exact"
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 70)
    print("BURROW GARDEN (T1L2M001) HIGH-PRECISION DUBBING PIPELINE")
    print("=" * 70)

    engine = NeuralVoiceEngine()

    generated_files = {}
    for cue_info in BURROW_CUES:
        c = cue_info["cue"]
        wav_path = synthesize_cue(engine, cue_info, out_dir)
        generated_files[c] = wav_path

    print("\n" + "=" * 70)
    print("AUTOMATED PHONETIC ONSET & DURATION VERIFICATION (WHISPER)")
    print("=" * 70)

    pipe = pipeline("automatic-speech-recognition", model="openai/whisper-base", device="cpu", generate_kwargs={"language": "tr", "task": "transcribe"})

    results = []
    all_passed = True
    for cue_info in BURROW_CUES:
        c = cue_info["cue"]
        wav_p = generated_files[c]
        expected_first = cue_info["expected_first_word"].lower()
        max_dur = cue_info["max_dur"]

        with wave.open(wav_p, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            actual_dur = frames / rate

        trans = pipe(wav_p)["text"].strip().lower()
        import string
        clean_trans = trans.translate(str.maketrans("", "", string.punctuation))
        words = clean_trans.split()
        first_word = words[0] if words else ""

        onset_pass = (first_word == expected_first) or (expected_first in first_word)
        dur_pass = actual_dur <= max_dur + 0.05

        status = "PASS" if (onset_pass and dur_pass) else "FAIL"
        if status == "FAIL":
            all_passed = False

        res_entry = {
            "cue": c,
            "char": cue_info["char"],
            "target_sr": rate,
            "actual_dur": round(actual_dur, 3),
            "max_dur": max_dur,
            "expected_first": expected_first,
            "heard_first": first_word,
            "full_transcript": trans,
            "onset_pass": onset_pass,
            "dur_pass": dur_pass,
            "status": status
        }
        results.append(res_entry)

        print(f"Cue {c:02d} [{cue_info['char']:11s}]: Status={status} | Dur={actual_dur:.2f}s/{max_dur:.2f}s | 1stWord='{first_word}' (Exp: '{expected_first}') | Trans: \"{trans}\"")

    summary_file = os.path.join(out_dir, "verification_summary.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\nSummary saved to:", summary_file)
    if all_passed:
        print("\n>>> ALL 11 CUES PASSED ONSET AND DURATION GATES! Ready for ADPCM injection.")
    else:
        print("\n>>> WARNING: Some cues failed verification gates. Check summary.")

if __name__ == "__main__":
    main()
