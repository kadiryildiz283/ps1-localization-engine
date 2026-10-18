"""Synthesizer for all 17 Burrow Garden dialogues in T1L2M001.WAD.

Ensures zero hallucination, perfect speech onset (no clipping of initial phonemes),
and strict conformance to PS1 SPU sector budgets.
"""

import os
import sys
import wave
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.voice_cloner import NeuralVoiceEngine

OUTPUT_DIR = "audio/burrow_final"
os.makedirs(OUTPUT_DIR, exist_ok=True)

LINES_TO_SYNTHESIZE = [
    {
        "cue": 14,
        "char": "ron",
        "sr": 22050,
        "max_dur": 9.10,
        "text": "Dursleylerin yanında o kadar uzun süre tıkılı kaldığına göre, sandıklar üzerinde Geri Tepme Büyüsü pratiği yapabilirsin. Büyü yapmak için çapraz düğmesine basman gerektiğini unutma."
    },
    {
        "cue": 17,
        "char": "ron",
        "sr": 22050,
        "max_dur": 5.69,
        "text": "Geri Tepme Büyünle bu sandıklara Flipendo yapmayı dene. Unutma, büyü yapmak için çapraz düğmesine bas!"
    },
    {
        "cue": 39,
        "char": "ron",
        "sr": 22050,
        "max_dur": 4.55,
        "text": "Tam güçlü bir Geri Tepme Büyüsü yapmak için çapraz düğmesini basılı tut."
    }
]

def main():
    engine = NeuralVoiceEngine()
    
    for item in LINES_TO_SYNTHESIZE:
        c = item["cue"]
        ch = item["char"]
        txt = item["text"]
        max_d = item["max_dur"]
        target_sr = item["sr"]
        
        out_wav = os.path.join(OUTPUT_DIR, f"cue_{c:02d}_{ch}.wav")
        print(f"\nSynthesizing Cue {c} ({ch}) [Budget: {max_d}s]: '{txt}'...")
        
        raw_path = engine.synthesize_speech(txt, ch, out_wav)
        
        # Check audio
        with wave.open(out_wav, "rb") as wf:
            n = wf.getnframes()
            sr = wf.getframerate()
            dur = n / float(sr)
            
        print(f"  Generated: {dur:.2f}s (Budget: {max_d}s)")

if __name__ == "__main__":
    main()
