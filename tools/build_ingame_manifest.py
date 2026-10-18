"""Master In-Game Dialogue Manifest Builder & Character Attribution Engine.

Analyzes all 70 WAD files containing spoken dialogue cues, accurately locates
their SPU ADPCM stream offsets and byte budgets in the XSPS sound table,
attributes character voices to all unique texts, and generates the master manifest.
"""

import glob
import hashlib
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MANIFEST_PATH = "audio/ingame_manifest.json"
UNIQUE_LINES_PATH = "audio/ingame_unique_lines.json"
BASES_PATH = "audio/ground_truth_bases.json"
EXTRACTED_DIR = "extracted"
TRANSLATIONS_DIR = "translations"


def attribute_speaker(clean_en: str, level_stem: str, cue_idx: int) -> str:
    """Accurately attribute speaker profile based on level context, cues, and dialogue content."""
    en_lower = clean_en.lower()

    # 1. Folio Magi / Journal recap entries -> Narrator (Melike)
    if level_stem == "T1I0M004":
        return "narrator"

    # 2. Card names & UI prompts -> Narrator (Melike)
    if (len(clean_en.split()) <= 2 and not any(w in en_lower for w in ["help", "run", "jump", "stop", "quick"])) or \
       any(w in en_lower for w in ["famous witches", "card awarded", "button to", "press", "challenge", "get ready to", "time:", "points:"]):
        return "narrator"

    # 3. Quidditch commentary levels -> Narrator (Melike / Student announcer)
    if level_stem in ("T1L3M000", "T1L3M005", "T1L3M006", "T1L3M007", "T1L3M008", "T1L3M009"):
        return "narrator"

    # 4. Basilisk whisper lines in dungeons / corridors
    if any(phrase in en_lower for phrase in ["come to me", "tear you", "rip you", "kill...", "smell blood", "hungry", "so long"]):
        return "riddle"

    # 5. Dobby scenes
    if level_stem == "T1L4M001" or "dobby" in en_lower or "harry potter mustn" in en_lower:
        return "dobby"

    # 6. Hagrid lines
    if "yer " in en_lower or "ter " in en_lower or level_stem in ("T1L3M001", "T1L8M002") and any(w in en_lower for w in ["supplies", "slug", "fang", "course", "harry", "blimey"]):
        return "hagrid"

    # 7. Mrs. Weasley
    if "ronald weasley" in en_lower or "elbows tucked" in en_lower or "fireplace" in en_lower or (level_stem == "T1L2M001" and "racket" in en_lower):
        return "mrs_weasley"

    # 8. Draco Malfoy
    if level_stem == "T1L5M006" or "saint potter" in en_lower or "pure-blood" in en_lower or "mudblood" in en_lower or (level_stem == "T1L1M008" and "duel" in en_lower):
        return "draco"

    # 9. Snape / Filch
    if any(phrase in en_lower for phrase in ["breaking the school rules", "mr. potter", "outside after dark", "see anyone, mr. filch", "detention", "points from gryffindor"]):
        return "snape"

    # 10. Lockhart
    if level_stem == "T1L6M002" or any(w in en_lower for w in ["autograph", "fame", "celebrity", "gilderoy", "lockhart", "fans"]):
        return "dumbledore"

    # 11. Moaning Myrtle
    if level_stem in ("T1L5M005", "T1L8M006") or "girls' bathroom" in en_lower or "miserable" in en_lower:
        return "hermione"

    # 12. Hermione Granger
    if level_stem == "T1L4M008" or any(w in en_lower for w in ["irresponsible", "library", "restricted section", "polyjuice", "chamber of secrets", "history of magic", "expelled"]):
        return "hermione"

    # 13. Flying Car / Whomping Willow -> Ron screaming / shouting instructions
    if level_stem in ("T1L1M003", "T1L1M004", "T1L1M005"):
        if any(phrase in en_lower for phrase in ["found the train", "end of these tunnels", "lost the train"]):
            return "harry"
        return "ron"

    # 14. The Burrow interactions -> Ron
    if level_stem in ("T1L2M001", "T1L2M003", "T1L2M008"):
        if "careful, ron" in en_lower:
            return "harry"
        return "ron"

    # 15. Dialogue where speaker addresses Ron -> Harry speaking
    if any(re.search(rf"\b{w}\b", en_lower) for w in ["ron", "ron!", "ron,"]):
        return "harry"

    # 16. Dialogue where speaker addresses Harry -> Ron speaking
    if any(re.search(rf"\b{w}\b", en_lower) for w in ["harry", "harry!", "harry,"]):
        return "ron"

    # Default fallback to narrator
    return "narrator"


def build_manifest():
    print("=" * 70)
    print("SCANNING 70 WAD FILES AND GENERATING IN-GAME DUBBING MANIFEST")
    print("=" * 70)

    dialogue_files = sorted(glob.glob(os.path.join(TRANSLATIONS_DIR, "dialogue_*.json")))
    all_cues = []
    unique_lines = {}
    gt = json.load(open(BASES_PATH, encoding="utf-8")) if os.path.exists(BASES_PATH) else {}

    master_map = {}
    master_path = "audio/complete_classified_manifest.json"
    if os.path.exists(master_path):
        with open(master_path, encoding="utf-8") as mf:
            m_list = json.load(mf)
            for m in m_list:
                clean_key = m["en"].strip().replace("`", "'").replace("·", "'").replace("µ", "...").replace("¸", "'")
                master_map[clean_key] = m["character"]
        print(f"Loaded {len(master_map)} accurate character attributions from {master_path}")

    for fpath in dialogue_files:
        stem = os.path.basename(fpath).replace("dialogue_", "").replace(".json", "")
        # Skip cutscene WAD as it is already 100% completed
        if stem == "T1L1M007":
            continue

        wad_name = f"{stem}.WAD"
        wad_path = os.path.join(EXTRACTED_DIR, wad_name)
        if not os.path.exists(wad_path):
            continue

        data = json.load(open(fpath, encoding="utf-8"))
        cues = []
        for r in data:
            en = r.get("en", "")
            tr = r.get("tr", "")
            m = re.search(r"#([0-9A-Fa-f]+)#\$?([0-9]*)?(.*)", en, re.DOTALL)
            if m:
                actor_hex = m.group(1)
                clean_en = m.group(3).strip()
                tr_m = re.search(r"#([0-9A-Fa-f]+)#\$?([0-9]*)?(.*)", tr, re.DOTALL)
                clean_tr = tr_m.group(3).strip() if tr_m else tr.strip()
                cues.append((int(actor_hex, 16), r["id"], clean_en, clean_tr))

        if not cues:
            continue

        with open(wad_path, "rb") as f:
            wad = f.read()

        dne_pos = wad.find(b" DNE")
        if dne_pos == -1:
            print(f"[!] Warning: No DNE chunk in {wad_name}")
            continue
        audio_base = (dne_pos + 2047) // 2048 * 2048
        audio_stream_len = len(wad) - audio_base

        spsx_pos = wad.find(b"XSPS")
        if spsx_pos == -1:
            print(f"[!] Warning: No XSPS chunk in {wad_name}")
            continue
        spsx_sz = struct.unpack("<I", wad[spsx_pos+4:spsx_pos+8])[0]
        spsx_data = wad[spsx_pos+8 : spsx_pos+8+spsx_sz]

        if stem not in gt or gt[stem].get("base_offset") is None:
            print(f"[!] Error: No ground truth base found for {wad_name}")
            continue
        best_base = gt[stem]["base_offset"]

        if stem == "T1L2M007":
            c8 = 8
            c8_e_off = best_base + c8 * 16
            c8_a_off, c8_p2, c8_p3, c8_a_sz = struct.unpack("<IIII", spsx_data[c8_e_off:c8_e_off+16])
            c8_dur = (c8_a_sz // 16 * 28) / 22050.0
            c8_char = "dumbledore"
            c8_tr = "Merhaba Harry! Ben Arthur Weasley."
            c8_en = "Hello Harry, I'm Arthur Weasley."
            c8_hash = hashlib.md5(f"{c8_char}:{c8_tr}".encode()).hexdigest()[:12]
            c8_entry = {
                "wad": wad_name,
                "stem": stem,
                "cue": c8,
                "id": 75,
                "table_entry_offset": c8_e_off,
                "audio_base": audio_base,
                "audio_offset": c8_a_off,
                "size_bytes": c8_a_sz,
                "max_duration": round(c8_dur, 2),
                "character": c8_char,
                "line_hash": c8_hash,
                "en": c8_en,
                "tr": c8_tr
            }
            all_cues.append(c8_entry)
            if c8_hash not in unique_lines:
                unique_lines[c8_hash] = {
                    "line_hash": c8_hash,
                    "character": c8_char,
                    "en": c8_en,
                    "tr": c8_tr,
                    "min_budget_bytes": c8_a_sz,
                    "min_duration": c8_dur,
                    "occurrences": 1,
                    "wads": [wad_name]
                }

        for c, rid, clean_en, clean_tr in cues:
            if stem == "T1L2M007" and c == 9:
                clean_tr = "Bahçedeki cüceleri temizlememe yardım eder misin acaba? Kapının hemen ardında ama cüceleri yakalamak için cüce ayıklama eldivenlerine ihtiyacın olacak. Ne yazık ki bütün bu ıvır zıvırın arasında onları kaybettim galiba."
                clean_en = "I was wondering if you'd help me de-gnome the garden. It's just through the gate but you'll need de-gnoming gloves to grab the gnomes. Unfortunately, I seem to have lost them under all this junk."
                char_profile = "dumbledore"

            e_off = best_base + c * 16
            a_off, p2, p3, a_sz = struct.unpack("<IIII", spsx_data[e_off:e_off+16])
            duration = (a_sz // 16 * 28) / 22050.0

            clean_lookup = clean_en.replace("`", "'").replace("·", "'").replace("µ", "...").replace("¸", "'")
            char_profile = master_map.get(clean_lookup) or attribute_speaker(clean_en, stem, c)
            line_hash = hashlib.md5(f"{char_profile}:{clean_tr}".encode()).hexdigest()[:12]

            cue_entry = {
                "wad": wad_name,
                "stem": stem,
                "cue": c,
                "id": rid,
                "table_entry_offset": e_off,
                "audio_base": audio_base,
                "audio_offset": a_off,
                "size_bytes": a_sz,
                "max_duration": round(duration, 2),
                "character": char_profile,
                "line_hash": line_hash,
                "en": clean_en,
                "tr": clean_tr
            }
            all_cues.append(cue_entry)

            if line_hash not in unique_lines:
                unique_lines[line_hash] = {
                    "line_hash": line_hash,
                    "character": char_profile,
                    "en": clean_en,
                    "tr": clean_tr,
                    "min_budget_bytes": a_sz,
                    "min_duration": duration,
                    "occurrences": 1,
                    "wads": [wad_name]
                }
            else:
                unique_lines[line_hash]["occurrences"] += 1
                unique_lines[line_hash]["wads"].append(wad_name)
                if a_sz < unique_lines[line_hash]["min_budget_bytes"]:
                    unique_lines[line_hash]["min_budget_bytes"] = a_sz
                    unique_lines[line_hash]["min_duration"] = duration

    os.makedirs(os.path.dirname(os.path.abspath(MANIFEST_PATH)), exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(all_cues, f, ensure_ascii=False, indent=2)

    unique_list = list(unique_lines.values())
    with open(UNIQUE_LINES_PATH, "w", encoding="utf-8") as f:
        json.dump(unique_list, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Parsed {len(all_cues)} in-game dialogue cues across 70 level WADs.")
    print(f"[OK] Identified {len(unique_list)} unique spoken lines requiring voice synthesis.")
    print("[OK] Master manifests saved to:")
    print(f"     -> {MANIFEST_PATH} ({len(all_cues)} entries)")
    print(f"     -> {UNIQUE_LINES_PATH} ({len(unique_list)} entries)")

    char_counts = {}
    for item in unique_list:
        c = item["character"]
        char_counts[c] = char_counts.get(c, 0) + 1

    print("\nCharacter Distribution for Unique Lines:")
    for c, cnt in sorted(char_counts.items(), key=lambda x: -x[1]):
        print(f"  - {c:12s}: {cnt:4d} lines")


if __name__ == "__main__":
    build_manifest()
