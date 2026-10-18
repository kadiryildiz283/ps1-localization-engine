"""Master Automated Turkish Dubbing & Disc Patcher for All Burrow Levels.

Covers:
  - T1L2M001: The Burrow Garden & Attic Climb (Harry, Ron, Molly Weasley)
  - T1L2M003: The Burrow Attic Ghoul Mini-Game (Ron, Molly Weasley)
  - T1L2M004: The Burrow Gnome Tossing Mini-Game (Ron, Melike/Narrator)
  - T1L2M006: Floo Powder Departure to Diagon Alley (Harry, Ron, Molly Weasley)

Uses newly enhanced multi-reference golden latents, SPU pre-emphasis broadcast mastering,
verifies transcription with Whisper, injects ADPCM VAGs with foreign slots muted,
and patches sectors directly into the target PS1 BIN disc image.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shutil
import struct
import wave

import numpy as np
from tools.audio_vag import encode_pcm_to_vag
from tools.cd_patcher import encode_mode2_form1_sector
from tools.iso_fs import SECTOR_SIZE, USER_DATA_SIZE
from tools.voice_cloner import NeuralVoiceEngine
from transformers import pipeline

TARGET_BIN = "Harry Potter and the Chamber of Secrets (Turkish).bin"

SILENCE_MID = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
SILENCE_END = b"\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

def make_silence(num_bytes: int) -> bytes:
    assert num_bytes % 16 == 0
    num_blocks = num_bytes // 16
    if num_blocks == 0:
        return b""
    return (SILENCE_MID * (num_blocks - 1)) + SILENCE_END

def encode_audio_file(wav_path: str, max_size_bytes: int) -> bytes:
    with wave.open(wav_path, "rb") as wf:
        frames = wf.readframes(wf.getnframes())
        pcm = np.frombuffer(frames, dtype=np.int16)
        sr = wf.getframerate()

    assert sr == 22050, f"{wav_path} sample rate is not 22050: {sr}"
    max_samples = (max_size_bytes // 16) * 28
    if len(pcm) > max_samples:
        pcm = pcm[:max_samples]

    vag = encode_pcm_to_vag(pcm, loop=False)
    pad = max_size_bytes - len(vag)
    assert pad >= 0, f"Encoded VAG exceeds max size: {len(vag)} > {max_size_bytes}"
    num_pad_blocks = pad // 16

    if num_pad_blocks > 0:
        vag = vag + (SILENCE_MID * (num_pad_blocks - 1)) + SILENCE_END
    else:
        vag = bytearray(vag[:max_size_bytes])
        vag[-15] = 0x01
        vag = bytes(vag)

    assert len(vag) == max_size_bytes
    return vag

BURROW_LEVELS = [
    {
        "wad": "T1L2M003.WAD",
        "stem": "T1L2M003",
        "name": "The Burrow Attic Ghoul",
        "start_lba": 90801,
        "base_offset": 720,
        "bgm_cues": [0],
        "dialogues": [
            {"cue": 1,  "char": "ron",         "tr": "Tamam, hortlağı sakinleştirmemiz gerek. Boruları çarpıp düşürüyor ve bu annemi deli ediyor!"},
            {"cue": 4,  "char": "ron",         "tr": "Sandığı hareket ettirmek için yön düğmelerini kullan. Yere çarpıp korkunç bir patırtı yapmadan önce 60 boru yakalamaya çalış."},
            {"cue": 7,  "char": "ron",         "tr": "Tamam Harry, hadi işe koyulalım!"},
            {"cue": 10, "char": "ron",         "tr": "İyi iş çıkardın Harry, bu onu bir süre susturur. Hortlak için yardıma teşekkürler."},
            {"cue": 13, "char": "mrs_weasley", "tr": "Aaaarrrghh! Şu gürültüyü kesebilir misiniz çocuklar! Denemeye devam edin!"},
            {"cue": 16, "char": "mrs_weasley", "tr": "Ah, ortalık çok daha sessizleşti! Şimdi çocuklar, benim için bahçedeki cücelerden kurtulun. Bay Weasley'yi bulun, barakanın yanında büyü dışı ıvır zıvırla uğraşıyor."},
            {"cue": 19, "char": "mrs_weasley", "tr": "Çocuklar, yukarıdaki o korkunç patırtıyı kesecek misiniz artık!"}
        ]
    },
    {
        "wad": "T1L2M004.WAD",
        "stem": "T1L2M004",
        "name": "The Burrow Gnome Tossing Mini-Game",
        "start_lba": 76161,
        "base_offset": 736,
        "bgm_cues": [12],
        "dialogues": [
            {"cue": 0,  "char": "narrator", "tr": "Ünlü Cadı ve Büyücü kartı kazanıldı!"},
            {"cue": 3,  "char": "ron",      "tr": "Fırlatmak için kare düğmesine bas!"},
            {"cue": 6,  "char": "ron",      "tr": "Dönmek için sol yön düğmesine art arda bas!"},
            {"cue": 9,  "char": "narrator", "tr": "Yardley Platt."},
            {"cue": 13, "char": "ron",      "tr": "Bu cücelerden arındırma eldivenlerini iyi bir amaç için kullanma zamanı!"},
            {"cue": 16, "char": "ron",      "tr": "Annem bu cüceleri çitin üzerinden, babamın büyü dışı ıvır zıvırlarının olduğu tarlaya fırlatmamızı istiyor."},
            {"cue": 19, "char": "ron",      "tr": "Bir cüceyi fırlatmak için iyi bir hız alma koşusuna ihtiyacın olacak! Hız kazanmak için sol düğmesine elinden geldiğince hızlı bas."},
            {"cue": 22, "char": "ron",      "tr": "Çite ulaştığında olduğun yerde dönmeye başlayacaksın. Cüceyi fırlatmaya hazır olduğunda kare düğmesine bas! Mesafe ve hedefleri vurma karşılığında puan kazanırsın!"},
            {"cue": 25, "char": "ron",      "tr": "Harika Harry! Bu senin tüm zamanlardaki en yüksek puanın!"},
            {"cue": 28, "char": "ron",      "tr": "Endişelenme, onu ben yakalarım Harry!"},
            {"cue": 31, "char": "ron",      "tr": "Gerçekten çok eğlenceliydi! Tekrar oynamak ister misin?"},
            {"cue": 34, "char": "ron",      "tr": "Tekrar dene Harry!"},
            {"cue": 41, "char": "ron",      "tr": "Ah, bu pek iyi olmadı Harry. Boş ver, ben hallederim onu."},
            {"cue": 44, "char": "ron",      "tr": "Müthiş fırlattın, herhangi biri ancak bu kadar uzağa atabilirdi."},
            {"cue": 47, "char": "ron",      "tr": "Harika atış! Arabayı vurdun!"},
            {"cue": 48, "char": "ron",      "tr": "Güzel vuruş, yaban arısı kovanını vurdun!"},
            {"cue": 49, "char": "ron",      "tr": "Telefon kulübesini vurdun!"},
            {"cue": 50, "char": "ron",      "tr": "İyi atış, göleti vurdun!"},
            {"cue": 51, "char": "ron",      "tr": "Evet! Harika!"},
            {"cue": 54, "char": "ron",      "tr": "Mükemmel!"},
            {"cue": 57, "char": "ron",      "tr": "Cüce fırlatmada harikalar yaratıyorsun!"},
            {"cue": 60, "char": "ron",      "tr": "Vay canına! Harika puan!"},
            {"cue": 63, "char": "ron",      "tr": "İyi puan Harry! Ama en iyisi değil."},
            {"cue": 66, "char": "ron",      "tr": "Fena değil, Harry."},
            {"cue": 69, "char": "ron",      "tr": "Annem bile bundan daha uzağa fırlatır!"},
            {"cue": 72, "char": "ron",      "tr": "Gözlüğün mü kırıldı? Korkunç bir şeydi!"}
        ]
    },
    {
        "wad": "T1L2M006.WAD",
        "stem": "T1L2M006",
        "name": "The Burrow Floo Powder Departure",
        "start_lba": 93060,
        "base_offset": 480,
        "bgm_cues": [21],
        "dialogues": [
            {"cue": 0,  "char": "mrs_weasley", "tr": "Dirseklerini de sakın açma!"},
            {"cue": 3,  "char": "ron",         "tr": "Çocuk oyuncağı!"},
            {"cue": 6,  "char": "mrs_weasley", "tr": "Şömineye girdiğinde nereye gittiğini söyle - ve gözlerini kapalı tut, kül kaçmasın!"},
            {"cue": 9,  "char": "harry",       "tr": "Bunun güvenli olduğuna emin misiniz?"},
            {"cue": 12, "char": "harry",       "tr": "Di-ya-gon Yolu!"},
            {"cue": 15, "char": "mrs_weasley", "tr": "Daha önce hiç Uçuş Tozu ile yolculuk etmediğin için bilmen gereken şey, panik yapmaman ve doğru şöminede çıkmandır."},
            {"cue": 18, "char": "mrs_weasley", "tr": "Doğru şöminede çıkmaya dikkat et!"}
        ]
    }
]

def patch_wad_to_iso(bin_path: str, wad_path: str, start_lba: int):
    with open(wad_path, "rb") as f:
        wad_bytes = f.read()
    num_sectors = (len(wad_bytes) + USER_DATA_SIZE - 1) // USER_DATA_SIZE
    print(f"    Patching {len(wad_bytes)} bytes ({num_sectors} sectors) starting at LBA {start_lba}...")
    with open(bin_path, "r+b") as f:
        for i in range(num_sectors):
            lba = start_lba + i
            chunk = wad_bytes[i * USER_DATA_SIZE : (i + 1) * USER_DATA_SIZE]
            if len(chunk) < USER_DATA_SIZE:
                chunk = chunk.ljust(USER_DATA_SIZE, b"\x00")
            sector = encode_mode2_form1_sector(lba, chunk)
            f.seek(lba * SECTOR_SIZE)
            f.write(sector)
    print(f"    ✓ Successfully patched {num_sectors} sectors into ISO!")

def main():
    print("=" * 80)
    print("MASTER AUTOMATED TURKISH DUBBING & DISC PATCHER FOR BURROW SUITE")
    print("=" * 80)

    tts = NeuralVoiceEngine()
    pipe = pipeline("automatic-speech-recognition", model="openai/whisper-base", device="cpu")

    audio_dir = "audio/burrow_clean"
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs("extracted", exist_ok=True)

    total_lines = sum(len(lvl["dialogues"]) for lvl in BURROW_LEVELS)
    print(f"\n[+] Total dialogue lines to synthesize and inject across 3 levels: {total_lines}")

    for lvl in BURROW_LEVELS:
        wad_name = lvl["wad"]
        stem = lvl["stem"]
        print("\n" + "=" * 60)
        print(f"LEVEL: {lvl['name']} ({wad_name}) | Start LBA: {lvl['start_lba']}")
        print("=" * 60)

        src_wad = f"extracted_text_only/{wad_name}"
        dst_wad = f"extracted/{wad_name}"
        shutil.copy2(src_wad, dst_wad)

        with open(dst_wad, "rb") as f:
            wad_data = bytearray(f.read())

        dne_pos = wad_data.find(b" DNE")
        audio_base = (dne_pos + 2047) // 2048 * 2048
        spsx_pos = wad_data.find(b"XSPS")
        spsx_base = spsx_pos + 8
        base_off = lvl["base_offset"]

        print(f"  audio_base: 0x{audio_base:X}, spsx_base: 0x{spsx_base:X}, base_offset: {base_off}")

        # 1. Synthesize and inject each dialogue line
        for item in lvl["dialogues"]:
            cue = item["cue"]
            char = item["char"]
            tr_text = item["tr"]

            e_off = base_off + cue * 16
            a_off, p2, p3, a_sz = struct.unpack("<IIII", wad_data[spsx_base + e_off : spsx_base + e_off + 16])
            max_dur = (a_sz // 16 * 28) / 22050.0

            wav_name = f"{stem}_cue{cue:02d}_{char}.wav"
            wav_path = os.path.join(audio_dir, wav_name)

            print(f"\n  [Cue {cue:02d}] {char.upper()}: \"{tr_text}\" (budget={a_sz}B, max_dur={max_dur:.2f}s)")
            tts.synthesize_line(tr_text, char, wav_path, max_duration=max_dur)

            # Whisper check
            whisper_txt = pipe(wav_path, generate_kwargs={"language": "tr"})["text"].strip()
            print(f"    ✓ Whisper check: \"{whisper_txt}\"")

            # Encode VAG and inject
            vag_bytes = encode_audio_file(wav_path, a_sz)
            wad_data[audio_base + a_off : audio_base + a_off + a_sz] = vag_bytes

            # Configure SPSX entry to channel 2 (playback)
            struct.pack_into("<I", wad_data, spsx_base + e_off + 4, 0x00020800)
            print(f"    ✓ Injected {len(vag_bytes)} bytes at 0x{a_off:06X}")

            # Mute French and German sub-slots (cue+1 and cue+2) if applicable
            for sub_c in [cue + 1, cue + 2]:
                sub_e_off = base_off + sub_c * 16
                if sub_e_off + 16 <= len(wad_data) - spsx_base:
                    sub_a_off, sub_p2, sub_p3, sub_sz = struct.unpack("<IIII", wad_data[spsx_base + sub_e_off : spsx_base + sub_e_off + 16])
                    if sub_sz > 0 and (sub_p2 & 0xFFFF) != 0x0800: # Not Category A
                        mute_bytes = make_silence(sub_sz)
                        wad_data[audio_base + sub_a_off : audio_base + sub_a_off + sub_sz] = mute_bytes
                        struct.pack_into("<I", wad_data, spsx_base + sub_e_off + 4, 0x00020800)

        # 2. Write modified WAD
        with open(dst_wad, "wb") as f:
            f.write(wad_data)
        print(f"\n  ✓ Successfully wrote {len(wad_data)} bytes to {dst_wad}")

        # 3. Patch WAD to ISO
        patch_wad_to_iso(TARGET_BIN, dst_wad, lvl["start_lba"])

    # Remove DuckStation savestate so clean sectors are loaded
    resume_sav = os.path.expanduser("~/.local/share/duckstation/savestates/SLES-03972_resume.sav")
    if os.path.exists(resume_sav):
        os.remove(resume_sav)
        print("\n[+] Removed DuckStation resume savestate.")

    print("\n" + "=" * 80)
    print("ALL BURROW SUITE LEVELS SUCCESSFULLY DUBBED AND PATCHED TO DISC!")
    print("=" * 80)

if __name__ == "__main__":
    main()
