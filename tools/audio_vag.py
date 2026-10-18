"""PS1 VAG / ADPCM Audio Decoder and Encoder for Harry Potter Streaming Voice Tracks.

Enables extracting voice lines to standard 16-bit 22050Hz/11025Hz WAV files
and encoding custom Turkish voice recordings back into Sony PS1 ADPCM blocks.
"""

import math
import os
import struct
import wave
from typing import List, Tuple

IK0 = [0.0, 0.9375, 1.796875, 1.53125, 1.90625]
IK1 = [0.0, 0.0, -0.8125, -0.859375, -0.9375]

def decode_vag_block(block: bytes, hist1: float, hist2: float) -> Tuple[List[int], float, float]:
    shift = block[0] & 0x0F
    filter_idx = (block[0] >> 4) & 0x07
    f0 = IK0[filter_idx] if filter_idx < len(IK0) else 0.0
    f1 = IK1[filter_idx] if filter_idx < len(IK1) else 0.0

    samples = []
    for b in block[2:16]:
        s_low = b & 0x0F
        if s_low >= 8:
            s_low -= 16
        s_high = (b >> 4) & 0x0F
        if s_high >= 8:
            s_high -= 16

        for nib in (s_low, s_high):
            val = (nib << 12) >> shift
            sample = val + f0 * hist1 + f1 * hist2
            hist2 = hist1
            hist1 = sample
            clamped = int(max(-32768, min(32767, round(sample))))
            samples.append(clamped)

    return samples, hist1, hist2

def decode_adpcm_to_wav(adpcm_data: bytes, wav_path: str, sample_rate: int = 22050):
    hist1 = 0.0
    hist2 = 0.0
    all_samples = []

    for i in range(0, len(adpcm_data) - 15, 16):
        block = adpcm_data[i : i + 16]
        flag = block[1]
        samples, hist1, hist2 = decode_vag_block(block, hist1, hist2)
        all_samples.extend(samples)

    pcm_bytes = struct.pack(f"<{len(all_samples)}h", *all_samples)
    os.makedirs(os.path.dirname(os.path.abspath(wav_path)), exist_ok=True)
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)

    return len(all_samples)


_fast_lib = None
try:
    import ctypes
    _so_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vag_fast.so")
    if os.path.exists(_so_path):
        _fast_lib = ctypes.CDLL(_so_path)
        _fast_lib.encode_vag_fast.argtypes = [
            ctypes.POINTER(ctypes.c_int16),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_int
        ]
        _fast_lib.encode_vag_fast.restype = ctypes.c_int
except Exception:
    _fast_lib = None


def encode_pcm_to_vag(pcm_samples, loop: bool = False) -> bytes:
    """Encode a sequence of 16-bit PCM samples into Sony PS1 SPU ADPCM byte stream."""
    if _fast_lib is not None:
        try:
            import numpy as np
            samples_arr = np.ascontiguousarray(pcm_samples, dtype=np.int16)
            n = len(samples_arr)
            pad = (28 - (n % 28)) % 28
            out_sz = ((n + pad) // 28) * 16
            out_buf = (ctypes.c_uint8 * out_sz)()
            samples_p = samples_arr.ctypes.data_as(ctypes.POINTER(ctypes.c_int16))
            ret = _fast_lib.encode_vag_fast(samples_p, n, out_buf, 1 if loop else 0)
            return bytes(out_buf[:ret])
        except Exception:
            pass

    blocks = bytearray()
    hist1 = 0.0
    hist2 = 0.0

    num_samples = len(pcm_samples)
    pad_needed = (28 - (num_samples % 28)) % 28
    padded_samples = list(pcm_samples) + [0] * pad_needed
    num_blocks = len(padded_samples) // 28

    for b_idx in range(num_blocks):
        block_samples = padded_samples[b_idx * 28 : (b_idx + 1) * 28]
        is_last = (b_idx == num_blocks - 1)
        flag = 0x01 if is_last and not loop else 0x00

        best_err = float("inf")
        best_filter = 0
        best_shift = 0
        best_nibbles = []
        best_h1 = hist1
        best_h2 = hist2

        for f_idx in range(5):
            f0 = IK0[f_idx]
            f1 = IK1[f_idx]

            max_delta = 0
            temp_h1 = hist1
            temp_h2 = hist2
            deltas = []
            for s in block_samples:
                pred = f0 * temp_h1 + f1 * temp_h2
                d = s - pred
                deltas.append((s, pred, d))
                temp_h2 = temp_h1
                temp_h1 = s
                max_delta = max(max_delta, abs(d))

            min_shift = 0
            while min_shift < 12 and (max_delta / (1 << (12 - min_shift))) > 7:
                min_shift += 1

            for shift in range(min_shift, min(13, min_shift + 3)):
                scale = 1 << (12 - shift)
                curr_h1 = hist1
                curr_h2 = hist2
                curr_err = 0.0
                nibbles = []

                for s, pred, _ in deltas:
                    pred_val = f0 * curr_h1 + f1 * curr_h2
                    diff = s - pred_val
                    nib = int(round(diff / scale))
                    nib = max(-8, min(7, nib))
                    recon = (nib << 12) >> shift
                    sample = recon + pred_val
                    curr_h2 = curr_h1
                    curr_h1 = sample
                    curr_err += (s - sample) ** 2
                    nibbles.append(nib & 0x0F)

                if curr_err < best_err:
                    best_err = curr_err
                    best_filter = f_idx
                    best_shift = shift
                    best_nibbles = nibbles
                    best_h1 = curr_h1
                    best_h2 = curr_h2

        byte0 = (best_filter << 4) | (best_shift & 0x0F)
        block = bytearray([byte0, flag])
        for n in range(0, 28, 2):
            low = best_nibbles[n]
            high = best_nibbles[n + 1]
            block.append(low | (high << 4))

        blocks.extend(block)
        hist1 = best_h1
        hist2 = best_h2

    return bytes(blocks)

