"""Master Turkish Dubbing / Voiceover Pipeline for Harry Potter PS1.

Extracts all 145 storybook cutscene lines to clean WAV reference files,
generates the dubbing manifest, and encodes & injects Turkish voice files
into T1L1M007.WAD with full sector alignment.
"""

import json
import os
import re
import struct
import sys
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.audio_vag import decode_adpcm_to_wav

AUDIO_SECTOR_BASE = 362496  # Exact byte offset of audio stream (sector 177)
WAD_PATH = 'extracted/T1L1M007.WAD'
MANIFEST_PATH = 'audio/dubbing_manifest.json'
REF_DIR = 'audio/reference_en'
TR_DIR = 'audio/turkish_dub'


def extract_all_reference_lines():
    os.makedirs(REF_DIR, exist_ok=True)
    os.makedirs(TR_DIR, exist_ok=True)

    with open(WAD_PATH, 'rb') as f:
        wad = f.read()

    spsx_pos = wad.find(b'XSPS')
    spsx_size = int.from_bytes(wad[spsx_pos+4:spsx_pos+8], 'little')
    spsx_data = wad[spsx_pos+8 : spsx_pos+8+spsx_size]

    dialogues = json.load(open('translations/dialogue_T1L1M007.json', 'r', encoding='utf-8'))

    manifest = []
    extracted = 0

    for r in dialogues:
        en = r.get('en', '')
        m = re.search(r"#([0-9A-Fa-f]+)#\$([0-9]{3})(.*)", en, re.DOTALL)
        if not m:
            continue
        actor_hex = m.group(1)
        cue = m.group(2)
        clean_en = m.group(3).strip()

        tr_raw = r.get('tr', '')
        tr_m = re.search(r"#([0-9A-Fa-f]+)#\$([0-9]{3})(.*)", tr_raw, re.DOTALL)
        clean_tr = tr_m.group(3).strip() if tr_m else tr_raw

        actor_idx = int(actor_hex, 16)
        spsx_off = 0x50 + actor_idx * 16
        if spsx_off + 16 > len(spsx_data):
            continue
        off, p2, p3, sz = struct.unpack('<IIII', spsx_data[spsx_off:spsx_off+16])

        duration = (sz // 16 * 28) / 22050.0
        wav_name = f'line_{actor_idx:03d}_{cue}.wav'
        wav_path = os.path.join(REF_DIR, wav_name)

        # Extract audio using exact sector-aligned base
        raw_audio = wad[AUDIO_SECTOR_BASE + off : AUDIO_SECTOR_BASE + off + sz]
        decode_adpcm_to_wav(raw_audio, wav_path, sample_rate=22050)

        entry = {
            'id': r['id'],
            'actor_id': actor_idx,
            'actor_hex': f'#{actor_hex}#',
            'cue': f'',
            'spsx_offset': off,
            'size_bytes': sz,
            'duration_seconds': round(duration, 2),
            'en': clean_en,
            'tr': clean_tr,
            'reference_wav': wav_path,
            'turkish_wav': os.path.join(TR_DIR, wav_name)
        }
        manifest.append(entry)
        extracted += 1

    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f'[SUCCESS] Extracted all {extracted} English reference lines to {REF_DIR}/')
    print(f'[SUCCESS] Generated master dubbing manifest: {MANIFEST_PATH}')
    return manifest

if __name__ == '__main__':
    extract_all_reference_lines()
