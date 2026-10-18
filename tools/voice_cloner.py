"""Neural Cross-Lingual Voice Cloning for Harry Potter PS1 (Argonaut Engine).

Uses Coqui XTTS-v2 to perform zero-shot voice cloning from original 2002 PS1 English voice
actor samples into authentic Turkish speech, matching SPU sector budgets.
"""

import argparse
import json
import os
import subprocess
import wave
from pathlib import Path

# PyTorch 2.6+ defaults weights_only=True which breaks legacy TTS checkpoints.
# Monkey patch torch.load to default weights_only=False for trusted local models.
import torch
_orig_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    kwargs["weights_only"] = False
    return _orig_torch_load(*args, **kwargs)
torch.load = _patched_torch_load

# Patch torchaudio to use soundfile instead of torchcodec (avoiding CUDA dependencies on CPU)
import soundfile as sf
import torchaudio
def _patched_audio_load(filepath, *args, **kwargs):
    data, sr = sf.read(filepath)
    t = torch.from_numpy(data).float()
    if t.ndim == 1:
        t = t.unsqueeze(0)
    else:
        t = t.t()
    return t, sr

def _patched_audio_save(filepath, src, sample_rate, *args, **kwargs):
    data = src.detach().cpu().numpy()
    if data.ndim == 2:
        data = data.T
    sf.write(filepath, data, sample_rate)

torchaudio.load = _patched_audio_load
torchaudio.save = _patched_audio_save

# Character profile map to reference WAV files
CHARACTER_PROFILES = {
    "dobby": "audio/profiles/dobby.wav",
    "harry": "audio/profiles/harry.wav",
    "narrator": "audio/profiles/narrator.wav",
    "ron": "audio/profiles/ron.wav",
    "hermione": "audio/profiles/hermione.wav",
    "snape": "audio/profiles/snape.wav",
    "draco": "audio/profiles/draco.wav",
    "dumbledore": "audio/profiles/dumbledore.wav",
    "riddle": "audio/profiles/riddle.wav",
    "hagrid": "audio/profiles/hagrid.wav",
    "mrs_weasley": "audio/profiles/mrs_weasley.wav",
    "sorting_hat": "audio/profiles/sorting_hat.wav",
}

# Line index to character mapping for storybook cutscenes
# Lines not explicitly mapped default to "narrator"
LINE_CHARACTER_MAP = {
    5: "dobby",          # Efe
    9: "harry",          # Kadir
    15: "snape",         # Lucius
    20: "narrator",      # Lockhart
    25: "snape",         # Lucius
    27: "harry",         # Kadir
    30: "ron",           # Batuhan
    31: "harry",         # Kadir
    38: "draco",         # Draco
    39: "hermione",      # Cansel (Ginny)
    40: "draco",         # Draco
    45: "snape",         # Snape
    47: "snape",         # Snape
    55: "narrator",      # Filch
    57: "draco",         # Draco
    61: "harry",         # Kadir
    64: "narrator",      # Lockhart
    69: "hermione",      # Cansel
    75: "narrator",      # Justin
    77: "ron",           # Batuhan
    79: "ron",           # Batuhan
    80: "hermione",      # Cansel
    83: "sorting_hat",   # Sorting Hat
    86: "dumbledore",    # Dumbledore
    88: "dumbledore",    # Dumbledore
    94: "riddle",        # Tom Riddle
    95: "riddle",        # Tom Riddle
    100: "hagrid",       # Young Hagrid
    102: "riddle",       # Tom Riddle
    104: "hagrid",       # Young Hagrid
    107: "harry",        # Kadir ("Hayııııııır!")
    112: "ron",          # Batuhan ("Ne var?")
    114: "harry",        # Kadir ("Acele et Ron!")
    117: "harry",        # Kadir ("O ölen kız...")
    118: "ron",          # Batuhan ("Ron nefesini tuttu.")
    119: "ron",          # Batuhan ("Yoksa... Mızmız Myrtle olmasın?")
    122: "hermione",     # Cansel (Ginny: "Bendimm, Harry...")
    124: "harry",        # Kadir ("Hadi Ginny, gidelim buradan.")
    130: "ron",          # Batuhan ("Hadi Harry, gidelim.")
    133: "hagrid",       # Hagrid ("Ben gidip Çatlak Kazan'da...")
    137: "harry",        # Kadir ("Hagrid'miş Ron...")
    138: "mrs_weasley",  # Mrs. Weasley (Howler!)
    142: "ron",          # Batuhan ("Oraya gitmenin ne anlamı vardı?...")
    143: "harry",        # Kadir ("Hagrid'in Sırlar Odası'nı asla açmadığını...")
}

def clean_text_for_tts(text: str) -> str:
    """Clean control tags, hex markers, and weird punctuation for smooth TTS synthesis."""
    import re
    # Remove leading tags like #0# or #1A# and optional color code $001
    text = re.sub(r"^#[0-9A-Fa-f]+#(\$[0-9]+)?\s*", "", text)
    # Remove remaining controller codes like { }, [, ], >, <, @, $
    text = re.sub(r"[\{\}\[\]><@\$]", "", text)
    # Replace special dashes or typos
    text = text.replace("`", "'").replace("·", "'").replace("µ", "...").replace("¸", "'")
    text = text.strip()
    return text

def resample_audio(input_wav: str, output_wav: str, target_rate: int = 22050, max_duration: float = None):
    """Resample to 22050Hz Mono 16-bit PCM with PS1 SPU Broadcast Pre-Emphasis and tempo-adjust if needed."""
    os.makedirs(os.path.dirname(os.path.abspath(output_wav)), exist_ok=True)
    
    # Check input duration
    with wave.open(input_wav, "rb") as wf:
        orig_dur = wf.getnframes() / wf.getframerate()

    # PS1 SPU Pre-Emphasis Filter Chain:
    # 1. High-pass @ 80Hz: cuts subwoofer rumble, gives SPU DAC dynamic headroom.
    # 2. High-shelf boost (+3.0 dB @ 4.5 kHz): counters the high-frequency muffling of 4-bit ADPCM.
    # 3. Limiter: prevents digital clipping.
    # 4. Standard 22050Hz mono format.
    filter_chain = [
        "highpass=f=80",
        "highshelf=f=4500:gain=3.0",
        "alimiter=limit=-1dB",
        "aformat=sample_fmts=s16:sample_rates=22050:channel_layouts=mono"
    ]
    
    if max_duration is not None and orig_dur > max_duration:
        speed_ratio = orig_dur / max_duration
        print(f"Applying tempo adjustment: {speed_ratio:.2f}x (orig={orig_dur:.2f}s, target_max={max_duration:.2f}s)")
        if speed_ratio > 2.0:
            filter_chain.insert(0, f"atempo=2.0,atempo={speed_ratio/2.0:.4f}")
        else:
            filter_chain.insert(0, f"atempo={speed_ratio:.4f}")

    filter_str = ",".join(filter_chain)

    cmd = [
        "ffmpeg", "-y", "-i", input_wav,
        "-af", filter_str,
        "-ac", "1",
        "-ar", str(target_rate),
        output_wav
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

class NeuralVoiceEngine:
    def __init__(self):
        print("Loading Coqui XTTS-v2 Neural Voice Cloning Model...")
        import torch
        num_threads = int(os.environ.get("TORCH_NUM_THREADS", "6"))
        torch.set_num_threads(num_threads)
        os.environ["COQUI_TOS_AGREED"] = "1"
        from TTS.api import TTS
        self.tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)
        self.model = self.tts.synthesizer.tts_model
        self.latents_cache = {}
        print("XTTS-v2 Neural Engine loaded successfully!")

    def get_latents(self, character: str):
        if character in self.latents_cache:
            return self.latents_cache[character]

        cache_pt = f"audio/profiles/{character}_latents.pt"
        if os.path.exists(cache_pt):
            lat = torch.load(cache_pt)
            self.latents_cache[character] = lat
            return lat

        speaker_wav = CHARACTER_PROFILES.get(character, CHARACTER_PROFILES["narrator"])
        print(f"Computing golden conditioning latents for '{character}' from {speaker_wav}...")
        gpt_lat, spk_emb = self.model.get_conditioning_latents(
            audio_path=speaker_wav,
            max_ref_length=30,
            gpt_cond_len=30,
            gpt_cond_chunk_len=6,
            sound_norm_refs=True
        )
        lat = (gpt_lat, spk_emb)
        torch.save(lat, cache_pt)
        self.latents_cache[character] = lat
        return lat

    def synthesize_line(self, text_tr: str, character: str, output_wav: str, max_duration: float = None):
        os.makedirs(os.path.dirname(os.path.abspath(output_wav)), exist_ok=True)
        temp_raw = output_wav + ".raw.wav"
        cleaned = clean_text_for_tts(text_tr)
        gpt_lat, spk_emb = self.get_latents(character)

        print(f"Synthesizing ({character.upper()}): \"{cleaned}\"")
        out = self.model.inference(
            text=cleaned,
            language="tr",
            gpt_cond_latent=gpt_lat,
            speaker_embedding=spk_emb,
            temperature=0.42,
            repetition_penalty=2.5,
            top_p=0.85,
            enable_text_splitting=True
        )
        sf.write(temp_raw, out["wav"], 24000)

        # Resample and conform to PS1 SPU budget
        resample_audio(temp_raw, output_wav, target_rate=22050, max_duration=max_duration)
        if os.path.exists(temp_raw):
            os.remove(temp_raw)

        # Also create high-quality MP3 preview
        mp3_out = output_wav.replace(".wav", ".mp3")
        subprocess.run(
            ["ffmpeg", "-y", "-i", output_wav, "-q:a", "2", mp3_out],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        with wave.open(output_wav, "rb") as wf:
            final_dur = wf.getnframes() / wf.getframerate()
        print(f"Saved: {output_wav} ({final_dur:.2f}s) & {os.path.basename(mp3_out)}")

def main():
    parser = argparse.ArgumentParser(description="Harry Potter PS1 Voice Cloning Engine")
    parser.add_argument("--prototype", action="store_true", help="Generate prototypes for custom cast")
    parser.add_argument("--line", type=int, default=None, help="Generate a specific line index (0-144)")
    parser.add_argument("--range", nargs=2, type=int, metavar=("START", "END"), help="Generate a range of lines [start, end)")
    parser.add_argument("--all", action="store_true", help="Generate all lines in manifest")
    args = parser.parse_args()

    with open("audio/dubbing_manifest.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)

    engine = NeuralVoiceEngine()

    if args.prototype:
        print("=== GENERATING HIGH-FIDELITY CUSTOM CAST PROTOTYPES V2 ===")
        # 1. Melike (Narrator, Line 0)
        item_0 = manifest[0]
        engine.synthesize_line(
            text_tr=item_0["tr"],
            character="narrator",
            output_wav="audio/cloned_test/melike_narrator_line_000.wav",
            max_duration=item_0["duration_seconds"]
        )

        # 2. Efe (Dobby, Line 5)
        dobby_item = manifest[5]
        engine.synthesize_line(
            text_tr=dobby_item["tr"],
            character="dobby",
            output_wav="audio/cloned_test/efe_dobby_line_005.wav",
            max_duration=dobby_item["duration_seconds"]
        )

        # 3. Kadir (Harry, Line 31)
        harry_item_31 = manifest[31]
        engine.synthesize_line(
            text_tr=harry_item_31["tr"],
            character="harry",
            output_wav="audio/cloned_test/kadir_harry_line_031.wav",
            max_duration=harry_item_31["duration_seconds"]
        )

        # 4. Batuhan (Ron, Line 79)
        ron_item_79 = manifest[79]
        engine.synthesize_line(
            text_tr=ron_item_79["tr"],
            character="ron",
            output_wav="audio/cloned_test/batuhan_ron_line_079.wav",
            max_duration=ron_item_79["duration_seconds"]
        )

        # 5. Kadir (Harry, Line 137)
        harry_item_137 = manifest[137]
        engine.synthesize_line(
            text_tr=harry_item_137["tr"],
            character="harry",
            output_wav="audio/cloned_test/kadir_harry_line_137.wav",
            max_duration=harry_item_137["duration_seconds"]
        )

        # 6. Cansel (Hermione, Line 69)
        hermione_item_69 = manifest[69]
        engine.synthesize_line(
            text_tr=hermione_item_69["tr"],
            character="hermione",
            output_wav="audio/cloned_test/cansel_hermione_line_069.wav",
            max_duration=hermione_item_69["duration_seconds"]
        )

        # 7. Cansel (Hermione, Line 80)
        hermione_item_80 = manifest[80]
        engine.synthesize_line(
            text_tr=hermione_item_80["tr"],
            character="hermione",
            output_wav="audio/cloned_test/cansel_hermione_line_080.wav",
            max_duration=hermione_item_80["duration_seconds"]
        )

        print("\nAll 5 custom cast prototypes V2 generated successfully in audio/cloned_test/!")

    elif args.all:
        print(f"=== SYNTHESIZING ALL {len(manifest)} LINES WITH NEURAL CAST ===")
        out_dir = "audio/turkish_dub"
        os.makedirs(out_dir, exist_ok=True)
        import shutil
        for idx, item in enumerate(manifest):
            char = LINE_CHARACTER_MAP.get(idx, "narrator")
            actor_id = item["actor_id"]
            out_wav = os.path.join(out_dir, f"line_{actor_id:03d}.wav")
            out_wav_idx = os.path.join(out_dir, f"line_{idx:03d}.wav")
            
            # Check if already synthesized
            if os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000:
                print(f"[{idx+1}/{len(manifest)}] Line {idx} (actor {actor_id:3d}) -> Already exists, skipping.")
                if not os.path.exists(out_wav_idx):
                    shutil.copyfile(out_wav, out_wav_idx)
                continue

            # Check if prototype already exists in cloned_test
            proto_map = {
                0: "audio/cloned_test/melike_narrator_line_000.wav",
                5: "audio/cloned_test/efe_dobby_line_005.wav",
                31: "audio/cloned_test/kadir_harry_line_031.wav",
                69: "audio/cloned_test/cansel_hermione_line_069.wav",
                79: "audio/cloned_test/batuhan_ron_line_079.wav",
                80: "audio/cloned_test/cansel_hermione_line_080.wav",
                137: "audio/cloned_test/kadir_harry_line_137.wav",
            }
            proto = proto_map.get(idx)
            if proto and os.path.exists(proto):
                print(f"\n[{idx+1}/{len(manifest)}] Line {idx} (actor {actor_id:3d}) -> Reusing validated prototype: {os.path.basename(proto)}")
                shutil.copyfile(proto, out_wav)
                shutil.copyfile(proto, out_wav_idx)
                continue

            print(f"\n[{idx+1}/{len(manifest)}] Line {idx} (actor {actor_id:3d}) -> Actor: {char.upper()}")
            engine.synthesize_line(
                text_tr=item["tr"],
                character=char,
                output_wav=out_wav,
                max_duration=item["duration_seconds"]
            )
            if out_wav != out_wav_idx:
                shutil.copyfile(out_wav, out_wav_idx)
        print(f"\n[SUCCESS] All {len(manifest)} lines synthesized with custom neural cast!")

    elif args.range is not None:
        start_idx, end_idx = args.range
        print(f"=== SYNTHESIZING LINES [{start_idx}:{end_idx}] WITH NEURAL CAST ===")
        out_dir = "audio/turkish_dub"
        os.makedirs(out_dir, exist_ok=True)
        import shutil
        for idx in range(start_idx, min(end_idx, len(manifest))):
            item = manifest[idx]
            char = LINE_CHARACTER_MAP.get(idx, "narrator")
            actor_id = item["actor_id"]
            out_wav = os.path.join(out_dir, f"line_{actor_id:03d}.wav")
            out_wav_idx = os.path.join(out_dir, f"line_{idx:03d}.wav")

            # Check if already synthesized
            if os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000:
                print(f"[{idx+1}/{len(manifest)}] Line {idx} (actor {actor_id:3d}) -> Already exists, skipping.")
                if not os.path.exists(out_wav_idx):
                    shutil.copyfile(out_wav, out_wav_idx)
                continue

            # Check if prototype already exists in cloned_test
            proto_map = {
                0: "audio/cloned_test/melike_narrator_line_000.wav",
                5: "audio/cloned_test/efe_dobby_line_005.wav",
                31: "audio/cloned_test/kadir_harry_line_031.wav",
                69: "audio/cloned_test/cansel_hermione_line_069.wav",
                79: "audio/cloned_test/batuhan_ron_line_079.wav",
                80: "audio/cloned_test/cansel_hermione_line_080.wav",
                137: "audio/cloned_test/kadir_harry_line_137.wav",
            }
            proto = proto_map.get(idx)
            if proto and os.path.exists(proto):
                print(f"\n[{idx+1}/{len(manifest)}] Line {idx} (actor {actor_id:3d}) -> Reusing validated prototype: {os.path.basename(proto)}")
                shutil.copyfile(proto, out_wav)
                shutil.copyfile(proto, out_wav_idx)
                continue

            print(f"\n[{idx+1}/{len(manifest)}] Line {idx} (actor {actor_id:3d}) -> Actor: {char.upper()}")
            engine.synthesize_line(
                text_tr=item["tr"],
                character=char,
                output_wav=out_wav,
                max_duration=item["duration_seconds"]
            )
            if out_wav != out_wav_idx:
                shutil.copyfile(out_wav, out_wav_idx)
        print(f"\n[SUCCESS] Range [{start_idx}:{end_idx}] synthesized successfully!")

    elif args.line is not None:
        idx = args.line
        item = manifest[idx]
        char = LINE_CHARACTER_MAP.get(idx, "narrator")
        actor_id = item["actor_id"]
        out_wav = f"audio/turkish_dub/line_{actor_id:03d}.wav"
        engine.synthesize_line(
            text_tr=item["tr"],
            character=char,
            output_wav=out_wav,
            max_duration=item["duration_seconds"]
        )

if __name__ == "__main__":
    main()
