import sys

"""Targeted bit-exact injector for The Burrow Garden (T1L2M001.WAD) cues.

Takes extracted_text_only/T1L2M001.WAD (which contains the clean Turkish font & text),
restores all ambient audio to pristine European state, and injects the 11 verified
Turkish dialogue sub-cues with exact SPU ADPCM block alignment.
"""

import os
import shutil
import struct
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.audio_vag import encode_pcm_to_vag

BURROW_INJECTIONS = [
    {
        "cue": 2,
        "char": "ron",
        "wav": "scratch/burrow_exact/cue_02_ron.wav",
        "sr": 22050,
        "sr_raw": 0x0800,
        "sz": 51200,
        "a_off": 0x04F000,
        "e_off": 1048
    },
    {
        "cue": 3,
        "char": "ron",
        "wav": "scratch/burrow_exact/cue_03_ron.wav",
        "sr": 16000,
        "sr_raw": 0x05CE,
        "sz": 26624,
        "a_off": 0x05B800,
        "e_off": 1064
    },
    {
        "cue": 4,
        "char": "ron",
        "wav": "scratch/burrow_exact/cue_04_ron.wav",
        "sr": 16000,
        "sr_raw": 0x05CE,
        "sz": 40960,
        "a_off": 0x062000,
        "e_off": 1080
    },
    {
        "cue": 49,
        "char": "harry",
        "wav": "scratch/burrow_exact/cue_49_harry.wav",
        "sr": 22050,
        "sr_raw": 0x0800,
        "sz": 26624,
        "a_off": 0x664800,
        "e_off": 1800
    },
    {
        "cue": 5,
        "char": "ron",
        "wav": "scratch/burrow_exact/cue_05_ron.wav",
        "sr": 22050,
        "sr_raw": 0x0800,
        "sz": 32768,
        "a_off": 0x06C000,
        "e_off": 1096
    },
    {
        "cue": 7,
        "char": "ron",
        "wav": "scratch/burrow_exact/cue_07_ron.wav",
        "sr": 16000,
        "sr_raw": 0x05CE,
        "sz": 22528,
        "a_off": 0x079000,
        "e_off": 1128
    },
    {
        "cue": 8,
        "char": "ron",
        "wav": "scratch/burrow_exact/cue_08_ron.wav",
        "sr": 22050,
        "sr_raw": 0x0800,
        "sz": 59392,
        "a_off": 0x07E800,
        "e_off": 1144
    },
    {
        "cue": 9,
        "char": "ron",
        "wav": "scratch/burrow_exact/cue_09_ron.wav",
        "sr": 16000,
        "sr_raw": 0x05CE,
        "sz": 55296,
        "a_off": 0x08D000,
        "e_off": 1160
    },
    {
        "cue": 11,
        "char": "ron",
        "wav": "scratch/burrow_exact/cue_11_ron.wav",
        "sr": 22050,
        "sr_raw": 0x0800,
        "sz": 88064,
        "a_off": 0x0A6000,
        "e_off": 1192
    },
    {
        "cue": 12,
        "char": "ron",
        "wav": "scratch/burrow_exact/cue_12_ron.wav",
        "sr": 16000,
        "sr_raw": 0x05CE,
        "sz": 57344,
        "a_off": 0x0BB800,
        "e_off": 1208
    },
    {
        "cue": 20,
        "char": "mrs_weasley",
        "wav": "scratch/burrow_exact/cue_20_mrs_weasley.wav",
        "sr": 22050,
        "sr_raw": 0x0800,
        "sz": 137216,
        "a_off": 0x140000,
        "e_off": 1336
    }
]

def main():
    print("=" * 70)
    print("TARGETED BIT-EXACT INJECTION FOR THE BURROW GARDEN (T1L2M001.WAD)")
    print("=" * 70)

    src_wad = "extracted_text_only/T1L2M001.WAD"
    dst_wad = "extracted/T1L2M001.WAD"

    if not os.path.exists(src_wad):
        raise FileNotFoundError(f"Source text-only WAD not found: {src_wad}")

    print(f"Step 1: Cloning pristine audio + Turkish text base: {src_wad} -> {dst_wad}...")
    shutil.copy2(src_wad, dst_wad)

    with open(dst_wad, "rb") as f:
        wad_data = bytearray(f.read())

    dne_pos = wad_data.find(b" DNE")
    audio_base = (dne_pos + 2047) // 2048 * 2048

    spsx_pos = wad_data.find(b"XSPS")
    spsx_sz = struct.unpack("<I", wad_data[spsx_pos+4 : spsx_pos+8])[0]
    spsx_base = spsx_pos + 8

    print(f"  audio_base: 0x{audio_base:X} ({audio_base})")
    print(f"  spsx_pos:   0x{spsx_pos:X} ({spsx_pos}), size: {spsx_sz}")

    silence_mid_block  = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    silence_mute_block = b"\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

    print("\nStep 2: Encoding and Injecting 11 Cues:")
    for item in BURROW_INJECTIONS:
        c = item["cue"]
        char = item["char"]
        wav_p = item["wav"]
        target_sr = item["sr"]
        sr_raw = item["sr_raw"]
        sz = item["sz"]
        a_off = item["a_off"]
        e_off = item["e_off"]

        with wave.open(wav_p, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            pcm = np.frombuffer(frames, dtype=np.int16)
            actual_sr = wf.getframerate()

        assert actual_sr == target_sr, f"Cue {c} SR mismatch: {actual_sr} != {target_sr}"

        max_samples = (sz // 16) * 28
        if len(pcm) > max_samples:
            print(f"  [!] Truncating Cue {c} from {len(pcm)} to {max_samples} samples")
            pcm = pcm[:max_samples]

        # SPU ADPCM encode
        vag_data = encode_pcm_to_vag(pcm, loop=True)

        # Pad with silence and terminal 0x01 block
        pad_bytes = sz - len(vag_data)
        num_pad_blocks = pad_bytes // 16
        if num_pad_blocks > 0:
            vag_data = vag_data + (silence_mid_block * (num_pad_blocks - 1)) + silence_mute_block
        else:
            vag_data = bytearray(vag_data[:sz])
            vag_data[-15] = 0x01
            vag_data = bytes(vag_data)

        assert len(vag_data) == sz, f"Cue {c} length error: {len(vag_data)} != {sz}"

        # Write to audio area
        abs_audio = audio_base + a_off
        wad_data[abs_audio : abs_audio + sz] = vag_data

        # Update SPSX descriptor table entry
        # Entry layout: struct <IIII (a_off, p2, p3, a_sz)
        # p2 = (hw << 16) | sr_raw
        new_p2 = (2 << 16) | (sr_raw & 0xFFFF)
        abs_table = spsx_base + e_off
        wad_data[abs_table + 4 : abs_table + 8] = struct.pack("<I", new_p2)

        print(f"  [Cue {c:02d}] Injected {sz:6d} bytes at 0x{abs_audio:X} | SPU Reg p2=0x{new_p2:08X} ({target_sr}Hz) | {char}")

    # Write back to extracted/T1L2M001.WAD
    with open(dst_wad, "wb") as f:
        f.write(wad_data)

    print(f"\nSuccessfully wrote {len(wad_data)} bytes to {dst_wad}!")

if __name__ == "__main__":
    main()
