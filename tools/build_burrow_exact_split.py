"""Master Exact Split-Engine Audio Injector for The Burrow Garden (T1L2M001.WAD).

Solves the multi-language audio architecture of Argonaut's PS1 Harry Potter engine:
1. For cues with 0xA800 split offset (Cues 2, 8, 11, 14, 17, 20, 23, 26, 29, 42, 45):
   - Writes silence from 0x0000 to 0xA7F0 with 0x01 terminal mute block at block 2687.
   - Writes the complete Turkish voice dialogue starting at offset 0xA800 (block 2688).
   - Pads with silence and terminates with 0x01 mute block.
2. For unsplit cues (Cues 5, 32, 35, 39, 49, 52):
   - Writes the complete Turkish voice dialogue starting at offset 0x0000.
   - Pads with silence and terminates with 0x01 mute block.
3. Completely mutes all 34 foreign language slots.
4. Preserves Category A SFX and BGM (Cues 0, 1, 38, 48) 100% bit-exact.
5. Sets SPSX descriptors to 22,050 Hz (pitch 0x0800) on voice channel 2.
"""

import os
import shutil
import struct
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.audio_vag import encode_pcm_to_vag

SRC_WAD = "extracted_text_only/T1L2M001.WAD"
DST_WAD = "extracted/T1L2M001.WAD"

SPLIT_CUES = [
    {"cue": 2,  "char": "ron",         "wav": "audio/burrow_clean/cue_02_ron.wav",         "sz": 51200,  "a_off": 0x04F000, "e_off": 1048, "max_span": 0x06C000 - 0x04F000},
    {"cue": 8,  "char": "ron",         "wav": "audio/burrow_clean/cue_08_ron.wav",         "sz": 59392,  "a_off": 0x07E800, "e_off": 1144, "max_span": 0x0A6000 - 0x07E800},
    {"cue": 11, "char": "ron",         "wav": "audio/burrow_clean/cue_11_ron.wav",         "sz": 88064,  "a_off": 0x0A6000, "e_off": 1192, "max_span": 0x0D9800 - 0x0A6000},
    {"cue": 14, "char": "ron",         "wav": "audio/burrow_clean/cue_14_ron.wav",         "sz": 114688, "a_off": 0x0D9800, "e_off": 1240, "max_span": 0x119000 - 0x0D9800},
    {"cue": 17, "char": "ron",         "wav": "audio/burrow_clean/cue_17_ron.wav",         "sz": 71680,  "a_off": 0x119000, "e_off": 1288, "max_span": 0x140000 - 0x119000},
    {"cue": 20, "char": "mrs_weasley", "wav": "audio/burrow_clean/cue_20_mrs_weasley.wav", "sz": 137216, "a_off": 0x140000, "e_off": 1336, "max_span": 0x187800 - 0x140000},
    {"cue": 23, "char": "ron",         "wav": "audio/burrow_clean/cue_23_ron.wav",         "sz": 94208,  "a_off": 0x187800, "e_off": 1384, "max_span": 0x1BC000 - 0x187800},
    {"cue": 26, "char": "ron",         "wav": "audio/burrow_clean/cue_26_ron.wav",         "sz": 75776,  "a_off": 0x1BC000, "e_off": 1432, "max_span": 0x1ED800 - 0x1BC000},
    {"cue": 29, "char": "ron",         "wav": "audio/burrow_clean/cue_29_ron.wav",         "sz": 102400, "a_off": 0x1ED800, "e_off": 1480, "max_span": 0x222800 - 0x1ED800},
    {"cue": 42, "char": "ron",         "wav": "audio/burrow_clean/cue_42_ron.wav",         "sz": 114688, "a_off": 0x324800, "e_off": 1688, "max_span": 0x36A000 - 0x324800},
    {"cue": 45, "char": "ron",         "wav": "audio/burrow_clean/cue_45_ron.wav",         "sz": 45056,  "a_off": 0x36A000, "e_off": 1736, "max_span": 0x381000 - 0x36A000},
]

UNSPLIT_CUES = [
    {"cue": 5,  "char": "ron",         "wav": "audio/burrow_clean/cue_05_ron.wav",         "sz": 32768,  "a_off": 0x06C000, "e_off": 1096, "max_span": 0x07E800 - 0x06C000},
    {"cue": 32, "char": "ron",         "wav": "audio/burrow_clean/cue_32_ron.wav",         "sz": 22528,  "a_off": 0x222800, "e_off": 1528, "max_span": 0x22F000 - 0x222800},
    {"cue": 35, "char": "ron",         "wav": "audio/burrow_clean/cue_35_ron.wav",         "sz": 34816,  "a_off": 0x22F000, "e_off": 1576, "max_span": 0x249000 - 0x22F000},
    {"cue": 39, "char": "ron",         "wav": "audio/burrow_clean/cue_39_ron.wav",         "sz": 57344,  "a_off": 0x300800, "e_off": 1640, "max_span": 0x324800 - 0x300800},
    {"cue": 49, "char": "harry",       "wav": "audio/burrow_clean/cue_49_harry.wav",       "sz": 26624,  "a_off": 0x664800, "e_off": 1800, "max_span": 0x670800 - 0x664800},
    {"cue": 52, "char": "ron",         "wav": "audio/burrow_clean/cue_52_ron.wav",         "sz": 30720,  "a_off": 0x670800, "e_off": 1848, "max_span": 0x683000 - 0x670800},
]

FOREIGN_SLOTS_TO_MUTE = [
    {"cue": 3,  "sz": 26624, "a_off": 0x05B800, "e_off": 1064},
    {"cue": 4,  "sz": 40960, "a_off": 0x062000, "e_off": 1080},
    {"cue": 6,  "sz": 20480, "a_off": 0x074000, "e_off": 1112},
    {"cue": 7,  "sz": 22528, "a_off": 0x079000, "e_off": 1128},
    {"cue": 9,  "sz": 55296, "a_off": 0x08D000, "e_off": 1160},
    {"cue": 10, "sz": 47104, "a_off": 0x09A800, "e_off": 1176},
    {"cue": 12, "sz": 57344, "a_off": 0x0BB800, "e_off": 1208},
    {"cue": 13, "sz": 65536, "a_off": 0x0C9800, "e_off": 1224},
    {"cue": 15, "sz": 67584, "a_off": 0x0F5800, "e_off": 1256},
    {"cue": 16, "sz": 77824, "a_off": 0x106000, "e_off": 1272},
    {"cue": 18, "sz": 38912, "a_off": 0x12A800, "e_off": 1304},
    {"cue": 19, "sz": 49152, "a_off": 0x134000, "e_off": 1320},
    {"cue": 21, "sz": 81920, "a_off": 0x161800, "e_off": 1352},
    {"cue": 22, "sz": 73728, "a_off": 0x175800, "e_off": 1368},
    {"cue": 24, "sz": 61440, "a_off": 0x19E800, "e_off": 1400},
    {"cue": 25, "sz": 59392, "a_off": 0x1AD800, "e_off": 1416},
    {"cue": 27, "sz": 67584, "a_off": 0x1CE800, "e_off": 1448},
    {"cue": 28, "sz": 59392, "a_off": 0x1DF000, "e_off": 1464},
    {"cue": 30, "sz": 49152, "a_off": 0x206800, "e_off": 1496},
    {"cue": 31, "sz": 65536, "a_off": 0x212800, "e_off": 1512},
    {"cue": 33, "sz": 14336, "a_off": 0x228000, "e_off": 1544},
    {"cue": 34, "sz": 14336, "a_off": 0x22B800, "e_off": 1560},
    {"cue": 36, "sz": 26624, "a_off": 0x237800, "e_off": 1592},
    {"cue": 37, "sz": 45056, "a_off": 0x23E000, "e_off": 1608},
    {"cue": 40, "sz": 40960, "a_off": 0x30E800, "e_off": 1656},
    {"cue": 41, "sz": 49152, "a_off": 0x318800, "e_off": 1672},
    {"cue": 43, "sz": 75776, "a_off": 0x340800, "e_off": 1704},
    {"cue": 44, "sz": 94208, "a_off": 0x353000, "e_off": 1720},
    {"cue": 46, "sz": 22528, "a_off": 0x375000, "e_off": 1752},
    {"cue": 47, "sz": 26624, "a_off": 0x37A800, "e_off": 1768},
    {"cue": 50, "sz": 12288, "a_off": 0x66B000, "e_off": 1816},
    {"cue": 51, "sz": 10240, "a_off": 0x66E000, "e_off": 1832},
    {"cue": 53, "sz": 20480, "a_off": 0x678000, "e_off": 1864},
    {"cue": 54, "sz": 22528, "a_off": 0x67D000, "e_off": 1880},
]

CATEGORY_A_PRESERVATION_CUES = [0, 1, 38, 48]

SILENCE_MID = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
SILENCE_END = b"\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

def make_silence(num_bytes: int, end_with_flag1: bool = True) -> bytes:
    assert num_bytes % 16 == 0
    num_blocks = num_bytes // 16
    if num_blocks == 0:
        return b""
    if end_with_flag1:
        return (SILENCE_MID * (num_blocks - 1)) + SILENCE_END
    else:
        return SILENCE_MID * num_blocks

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

def main():
    print("=" * 80)
    print("MASTER EXACT SPLIT-ENGINE TURKISH INJECTOR FOR THE BURROW (T1L2M001.WAD)")
    print("=" * 80)

    if not os.path.exists(SRC_WAD):
        raise FileNotFoundError(f"Source WAD not found: {SRC_WAD}")

    print(f"Step 1: Cloning clean base {SRC_WAD} -> {DST_WAD}...")
    shutil.copy2(SRC_WAD, DST_WAD)

    with open(DST_WAD, "rb") as f:
        wad_data = bytearray(f.read())

    dne_pos = wad_data.find(b" DNE")
    audio_base = (dne_pos + 2047) // 2048 * 2048
    spsx_pos = wad_data.find(b"XSPS")
    spsx_base = spsx_pos + 8

    print(f"  audio_base: 0x{audio_base:X} ({audio_base})")
    print(f"  spsx_base:  0x{spsx_base:X} ({spsx_base})")

    # Store Category A reference chunks
    base_e_off = 1016
    cat_a_refs = {}
    for c in CATEGORY_A_PRESERVATION_CUES:
        e_off = base_e_off + c * 16
        a_off, _p2, _p3, a_sz = struct.unpack("<IIII", wad_data[spsx_base + e_off : spsx_base + e_off + 16])
        cat_a_refs[c] = bytes(wad_data[audio_base + a_off : audio_base + a_off + a_sz])

    # Step 2: Inject all 11 Split Cues (Turkish line starting at a_off + 0xA800)
    print("\nStep 2: Injecting 11 Split Cues (0xA800 architecture):")
    for item in SPLIT_CUES:
        c = item["cue"]
        char = item["char"]
        wav_p = item["wav"]
        sz = item["sz"]
        a_off = item["a_off"]
        e_off = item["e_off"]
        max_span = item["max_span"]

        # 1. First 0xA800 bytes: silence ending with terminal block at block 2687 (0xA7F0)
        prefix_silence = make_silence(0xA800, end_with_flag1=True)
        assert len(prefix_silence) == 0xA800
        assert prefix_silence[0xA7F1] == 0x01, f"Cue {c} prefix mute flag missing!"

        # 2. Turkish dialogue audio starting at 0xA800, exactly sz bytes
        turkish_vag = encode_audio_file(wav_p, sz)
        assert turkish_vag[-15] == 0x01, f"Cue {c} turkish audio terminal flag missing!"

        # 3. Write prefix silence and Turkish dialogue
        abs_start = audio_base + a_off
        wad_data[abs_start : abs_start + 0xA800] = prefix_silence
        wad_data[abs_start + 0xA800 : abs_start + 0xA800 + sz] = turkish_vag

        # 4. Fill any remaining space up to max_span with silence
        remain_start = abs_start + 0xA800 + sz
        span_end = abs_start + max_span
        if span_end > remain_start:
            wad_data[remain_start : span_end] = make_silence(span_end - remain_start, end_with_flag1=False)

        # 5. Set SPSX descriptor
        p2 = (2 << 16) | 0x0800  # voice channel 2, 22,050 Hz
        abs_table = spsx_base + e_off
        wad_data[abs_table + 4 : abs_table + 8] = struct.pack("<I", p2)
        wad_data[abs_table + 12 : abs_table + 16] = struct.pack("<I", sz)

        print(f"  [Cue {c:02d}] SPLIT: Prefix silence (0x0000..0xA800) | TR Audio at 0x{a_off+0xA800:06X} ({sz:6d}B) | SPU p2=0x{p2:08X} | {char.upper()}")

    # Step 3: Inject all 6 Unsplit Cues (Turkish line starting at a_off + 0x0000)
    print("\nStep 3: Injecting 6 Unsplit Cues (0x0000 direct start):")
    for item in UNSPLIT_CUES:
        c = item["cue"]
        char = item["char"]
        wav_p = item["wav"]
        sz = item["sz"]
        a_off = item["a_off"]
        e_off = item["e_off"]
        max_span = item["max_span"]

        turkish_vag = encode_audio_file(wav_p, sz)
        assert turkish_vag[-15] == 0x01, f"Cue {c} turkish audio terminal flag missing!"

        abs_start = audio_base + a_off
        wad_data[abs_start : abs_start + sz] = turkish_vag

        # Fill remainder of slot up to max_span with silence
        remain_start = abs_start + sz
        span_end = abs_start + max_span
        if span_end > remain_start:
            wad_data[remain_start : span_end] = make_silence(span_end - remain_start, end_with_flag1=False)

        # Set SPSX descriptor
        p2 = (2 << 16) | 0x0800  # voice channel 2, 22,050 Hz
        abs_table = spsx_base + e_off
        wad_data[abs_table + 4 : abs_table + 8] = struct.pack("<I", p2)
        wad_data[abs_table + 12 : abs_table + 16] = struct.pack("<I", sz)

        print(f"  [Cue {c:02d}] UNSPLIT: TR Audio at 0x{a_off:06X} ({sz:6d}B) | SPU p2=0x{p2:08X} | {char.upper()}")

    # Step 4: Configure all 34 foreign language slots
    print("\nStep 4: Muting and configuring all 34 foreign language descriptors:")
    for item in FOREIGN_SLOTS_TO_MUTE:
        c = item["cue"]
        e_off = item["e_off"]
        p2 = (2 << 16) | 0x05CE
        abs_table = spsx_base + e_off
        wad_data[abs_table + 4 : abs_table + 8] = struct.pack("<I", p2)
    print("  Configured all 34 foreign cue descriptors to channel 2 / muted.")

    # Step 5: Verify Category A preservation 100% bit-exact
    print("\nStep 5: Verifying Category A Sound Effects & BGM Preservation:")
    for c in CATEGORY_A_PRESERVATION_CUES:
        e_off = base_e_off + c * 16
        a_off, _p2, _p3, a_sz = struct.unpack("<IIII", wad_data[spsx_base + e_off : spsx_base + e_off + 16])
        current_data = bytes(wad_data[audio_base + a_off : audio_base + a_off + a_sz])
        assert current_data == cat_a_refs[c], f"Category A corruption detected in Cue {c}!"
        print(f"  [Cue {c:02d}] Preserved 100% bit-exact ({a_sz} bytes)")

    # Step 6: Write output WAD
    with open(DST_WAD, "wb") as f:
        f.write(wad_data)
    print(f"\nSuccessfully wrote {len(wad_data)} bytes to {DST_WAD}!")

if __name__ == "__main__":
    main()
