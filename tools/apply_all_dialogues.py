"""Master Dialogue Compiler & Integrator for Harry Potter PS1 Turkish Localization.

Applies literary Turkish translations from the 5 validated batches to all 74 level
dialogue JSON files and recompiles all 74 .WAD files with dynamic pointer repointing.
"""

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.wad_lpsx import WadLpsxHandler


def main():
    print("=" * 60)
    print("HARRY POTTER PS1 - TURKISH LOCALIZATION INJECTION PIPELINE")
    print("=" * 60)

    # 1. Load batches
    batches = [f"translations/batches/batch_{i}_tr.json" for i in range(5)]
    master_dict = {}
    for b in batches:
        if not os.path.exists(b):
            print(f"Error: Missing batch file {b}")
            sys.exit(1)
        data = json.load(open(b, encoding="utf-8"))
        for item in data:
            master_dict[item["en"]] = item["tr"]
            # Also store stripped version
            master_dict[item["en"].strip()] = item["tr"]

    print(f"[OK] Loaded {len(master_dict)} translation pairs from 5 batches.")

    # 2. Update dialogue JSON files
    dialogue_files = sorted(glob.glob("translations/dialogue_*.json"))
    print(f"\nProcessing {len(dialogue_files)} level dialogue files...")

    total_records = 0
    translated_records = 0
    missing_records = 0

    for fpath in dialogue_files:
        data = json.load(open(fpath, encoding="utf-8"))
        changed = False
        for r in data:
            total_records += 1
            en = r.get("en", "").strip()
            if not en:
                continue
            if r["en"] in master_dict:
                r["tr"] = master_dict[r["en"]]
                translated_records += 1
                changed = True
            elif en in master_dict:
                r["tr"] = master_dict[en]
                translated_records += 1
                changed = True
            else:
                missing_records += 1

        if changed:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[OK] Updated all dialogue JSONs: {translated_records}/{total_records} records translated (missing: {missing_records}).")

    # 3. Recompile all 74 WAD files from pristine original ISO with dynamic repointing & sector preservation
    print("\nRecompiling all 74 WAD files with dynamic pointer repointing and sector preservation...")
    wad_count = 0
    extracted_dir = "extracted"
    os.makedirs(extracted_dir, exist_ok=True)
    orig_iso_path = "Harry Potter and the Chamber of Secrets (Europe) (En,Fr,De).bin"

    from tools.dirdat import DirDatArchive
    from tools.iso_fs import Ps1IsoReader

    with Ps1IsoReader(orig_iso_path) as iso:
        archive = DirDatArchive.from_iso(iso)
        for fpath in dialogue_files:
            stem = os.path.basename(fpath).replace("dialogue_", "").replace(".json", "")
            if stem == "T1L1M007":
                # Preserve existing fully-dubbed cutscene WAD
                continue
            wad_name = f"{stem}.WAD"

            if wad_name not in archive.entry_map:
                print(f"Warning: {wad_name} not found in original archive, skipping.")
                continue

            entry = archive.entry_map[wad_name]
            raw_bytes = iso.read_file_bytes("POTTER.DAT", entry.offset, entry.size)

            handler = WadLpsxHandler(raw_bytes)
            if not handler.records:
                continue

            records = json.load(open(fpath, encoding="utf-8"))
            out_wad_path = os.path.join(extracted_dir, wad_name)
            handler.compile_wad_with_translations(records, out_wad_path, target_lang="tr")
            new_len = os.path.getsize(out_wad_path)
            wad_count += 1
            if wad_count % 10 == 0 or wad_count == len(dialogue_files):
                print(f"  [{wad_count}/{len(dialogue_files)}] Rebuilt {wad_name:12s} ({entry.size} -> {new_len} bytes)")

    print(f"\n[OK] Successfully rebuilt {wad_count} WAD files with Turkish dialogues and repointed pointers.")

if __name__ == "__main__":
    main()
