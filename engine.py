#!/usr/bin/env python3
"""Harry Potter and the Chamber of Secrets (PS1) Localization Engine CLI.

Full reverse engineering, text extraction, dynamic repointing, and rebuilding pipeline.
"""

import argparse
import glob
import json
import os
import struct
import sys

from tools.iso_fs import Ps1IsoReader
from tools.dirdat import DirDatArchive
from tools.text_bin import export_bin_to_json, import_json_to_bin
from tools.wad_lpsx import WadLpsxHandler
from tools.cd_patcher import patch_file_in_bin

DEFAULT_BIN = "Harry Potter and the Chamber of Secrets (Europe) (En,Fr,De).bin"
EXTRACTED_DIR = "extracted"
TRANSLATIONS_DIR = "translations"


def cmd_dump_ui(args):
    bin_file = args.bin or DEFAULT_BIN
    if not os.path.exists(bin_file):
        print(f"Error: Disc image '{bin_file}' not found.")
        sys.exit(1)

    print(f"Connecting to PS1 disc image: {bin_file}")
    with Ps1IsoReader(bin_file) as iso:
        archive = DirDatArchive.from_iso(iso)
        raw_bin_path = os.path.join(EXTRACTED_DIR, "ENGLISH.BIN")
        archive.extract_entry_from_iso(iso, "ENGLISH.BIN", raw_bin_path)

    json_path = os.path.join(TRANSLATIONS_DIR, "ui_english.json")
    export_bin_to_json(raw_bin_path, json_path)
    print(f"[OK] UI text successfully dumped to: {json_path}")


def cmd_dump_dialogue(args):
    bin_file = args.bin or DEFAULT_BIN
    wad_name = args.wad.upper()
    if not wad_name.endswith(".WAD"):
        wad_name += ".WAD"

    print(f"Extracting {wad_name} from disc...")
    with Ps1IsoReader(bin_file) as iso:
        archive = DirDatArchive.from_iso(iso)
        if wad_name not in archive.entry_map:
            print(f"Error: '{wad_name}' not found in POTTER.DAT archive.")
            sys.exit(1)
        raw_wad_path = os.path.join(EXTRACTED_DIR, wad_name)
        archive.extract_entry_from_iso(iso, wad_name, raw_wad_path)

    with open(raw_wad_path, "rb") as f:
        handler = WadLpsxHandler(f.read())

    if not handler.records:
        print(f"Note: {wad_name} has no dialogue/LPSX text section.")
        return

    json_path = os.path.join(TRANSLATIONS_DIR, f"dialogue_{wad_name.replace('.WAD', '')}.json")
    handler.export_to_json(json_path)
    print(f"[OK] {len(handler.records)} dialogue/quest strings dumped to: {json_path}")


def cmd_dump_all_dialogues(args):
    bin_file = args.bin or DEFAULT_BIN
    print(f"Scanning all WAD files in disc image: {bin_file}...")
    with Ps1IsoReader(bin_file) as iso:
        archive = DirDatArchive.from_iso(iso)
        wad_entries = [e for e in archive.entries if e.name.endswith(".WAD")]
        print(f"Found {len(wad_entries)} WAD files in archive.")

        exported_count = 0
        for entry in wad_entries:
            data = iso.read_file_bytes("POTTER.DAT", entry.offset, entry.size)
            handler = WadLpsxHandler(data)
            if handler.records:
                stem = entry.name.replace(".WAD", "")
                json_path = os.path.join(TRANSLATIONS_DIR, f"dialogue_{stem}.json")
                handler.export_to_json(json_path)
                exported_count += 1
                # Save raw WAD to extracted/ as well
                raw_wad_path = os.path.join(EXTRACTED_DIR, entry.name)
                os.makedirs(EXTRACTED_DIR, exist_ok=True)
                with open(raw_wad_path, "wb") as f:
                    f.write(data)

    print(f"\n[OK] Successfully dumped dialogue from {exported_count} levels into {TRANSLATIONS_DIR}/")


def cmd_build_ui(args):
    json_path = os.path.join(TRANSLATIONS_DIR, "ui_english.json")
    if not os.path.exists(json_path):
        print(f"Error: '{json_path}' not found. Run 'dump-ui' first.")
        sys.exit(1)

    out_bin = os.path.join(EXTRACTED_DIR, "ENGLISH.BIN")
    import_json_to_bin(json_path, out_bin, use_turkish_fallback=True)
    # Also write to FRENCH.BIN and GERMAN.BIN so Turkish is active regardless of language selection
    import shutil
    for lang in ["FRENCH.BIN", "GERMAN.BIN"]:
        shutil.copy2(out_bin, os.path.join(EXTRACTED_DIR, lang))
    print(f"[OK] Rebuilt UI language files (ENGLISH.BIN, FRENCH.BIN, GERMAN.BIN)")


def cmd_build_dialogue(args):
    wad_name = args.wad.upper()
    if not wad_name.endswith(".WAD"):
        wad_name += ".WAD"
    stem = wad_name.replace(".WAD", "")
    json_path = os.path.join(TRANSLATIONS_DIR, f"dialogue_{stem}.json")
    raw_wad_path = os.path.join(EXTRACTED_DIR, wad_name)

    if not os.path.exists(json_path):
        print(f"Error: '{json_path}' not found.")
        sys.exit(1)
    if not os.path.exists(raw_wad_path):
        print(f"Error: Base WAD '{raw_wad_path}' not found in {EXTRACTED_DIR}/. Run 'dump-dialogue' first.")
        sys.exit(1)

    with open(raw_wad_path, "rb") as f:
        handler = WadLpsxHandler(f.read())

    with open(json_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    out_wad = os.path.join(EXTRACTED_DIR, wad_name)
    handler.compile_wad_with_translations(records, out_wad, target_lang="en")
    print(f"[OK] Rebuilt {wad_name} with dynamic pointer repointing.")


def cmd_patch_disc(args):
    source_bin = args.bin or DEFAULT_BIN
    output_bin = args.output or "Harry Potter and the Chamber of Secrets (Turkish).bin"
    output_cue = output_bin.rsplit(".", 1)[0] + ".cue"

    print(f"Creating clean Turkish disc image from: {source_bin}...")
    import shutil
    shutil.copy2(source_bin, output_bin)

    print(f"Patching modified files into {output_bin}...")
    from tools.cd_patcher import encode_mode2_form1_sector, compute_edc
    from tools.iso_fs import USER_DATA_SIZE, SECTOR_SIZE

    with Ps1IsoReader(source_bin) as iso:
        potter_dat_entry = iso.files.get("POTTER.DAT")
        potter_dir_entry = iso.files.get("POTTER.DIR")
        if not potter_dat_entry or not potter_dir_entry:
            print("Error: POTTER.DAT or POTTER.DIR not found on source disc image.")
            sys.exit(1)

        dat_lba = potter_dat_entry.lba
        dir_lba = potter_dir_entry.lba
        dir_bytes = bytearray(iso.read_file_bytes("POTTER.DIR"))

    num_files = struct.unpack("<I", dir_bytes[:4])[0]
    dir_entries = {}
    for i in range(num_files):
        entry_chunk = dir_bytes[4 + i * 20 : 4 + (i + 1) * 20]
        r_name, r_size, r_off = struct.unpack("<12sII", entry_chunk)
        clean_name = r_name.rstrip(b"\x00").decode("ascii", errors="ignore")
        dir_entries[clean_name] = (i, r_size, r_off)

    modified_files = []
    if os.path.exists(EXTRACTED_DIR):
        for fname in os.listdir(EXTRACTED_DIR):
            if fname in dir_entries:
                modified_files.append(fname)

    if not modified_files:
        print("No rebuilt files found in extracted/. Run build-ui or build-dialogue first.")
        return

    print(f"Found {len(modified_files)} modified file(s) to patch.")

    with open(output_bin, "r+b") as disc_f:
        patched_count = 0
        for fname in sorted(modified_files):
            file_path = os.path.join(EXTRACTED_DIR, fname)
            with open(file_path, "rb") as in_f:
                new_data = in_f.read()

            idx, old_size, old_off = dir_entries[fname]
            file_start_lba = dat_lba + (old_off // USER_DATA_SIZE)
            old_sectors = (old_size + USER_DATA_SIZE - 1) // USER_DATA_SIZE
            new_sectors = (len(new_data) + USER_DATA_SIZE - 1) // USER_DATA_SIZE

            if new_sectors <= old_sectors:
                file_start_lba = dat_lba + (old_off // USER_DATA_SIZE)
                bulk_sectors = bytearray()
                for s in range(new_sectors):
                    chunk = new_data[s * USER_DATA_SIZE : (s + 1) * USER_DATA_SIZE]
                    if len(chunk) < USER_DATA_SIZE:
                        chunk = chunk.ljust(USER_DATA_SIZE, b"\x00")
                    bulk_sectors.extend(encode_mode2_form1_sector(file_start_lba + s, chunk))

                disc_f.seek(file_start_lba * SECTOR_SIZE)
                disc_f.write(bulk_sectors)

                # Update size in POTTER.DIR
                dir_bytes[4 + idx * 20 + 12 : 4 + idx * 20 + 16] = struct.pack("<I", len(new_data))
                print(f"  [OK] Patched changed file: {fname} ({len(new_data)} bytes, {new_sectors} sectors) at LBA {file_start_lba}")
                patched_count += 1
            else:
                print(f"  [!] {fname} size expanded beyond allocated sectors ({old_size} -> {len(new_data)} bytes).")

        if patched_count > 0:
            # Write updated POTTER.DIR sectors to disc
            dir_sectors = (len(dir_bytes) + USER_DATA_SIZE - 1) // USER_DATA_SIZE
            bulk_dir_sectors = bytearray()
            for s in range(dir_sectors):
                chunk = bytes(dir_bytes[s * USER_DATA_SIZE : (s + 1) * USER_DATA_SIZE]).ljust(USER_DATA_SIZE, b"\x00")
                bulk_dir_sectors.extend(encode_mode2_form1_sector(dir_lba + s, chunk))
            disc_f.seek(dir_lba * SECTOR_SIZE)
            disc_f.write(bulk_dir_sectors)
        else:
            print("All files in extracted/ match disc image. Nothing to patch.")

    # Write CUE sheet
    with open(output_cue, "w") as cue_f:
        cue_f.write(f'FILE "{os.path.basename(output_bin)}" BINARY\n')
        cue_f.write("  TRACK 01 MODE2/2352\n")
        cue_f.write("    INDEX 01 00:00:00\n")

    print(f"\n[SUCCESS] Disc patched successfully!")
    print(f"  BIN: {output_bin}")
    print(f"  CUE: {output_cue}")
    print("Ready to play in DuckStation, PCSX-Redux, or burn to CD!")


def cmd_status(args):
    print("=== Harry Potter PS1 Turkish Localization Status ===")
    ui_json = os.path.join(TRANSLATIONS_DIR, "ui_english.json")
    if os.path.exists(ui_json):
        with open(ui_json, "r", encoding="utf-8") as f:
            ui_data = json.load(f)
        ui_tr = sum(1 for e in ui_data if e.get("translation") or e.get("tr"))
        print(f"UI / Menus: {ui_tr} / {len(ui_data)} translated ({ui_tr / len(ui_data) * 100:.1f}%)")
    else:
        print("UI / Menus: Not dumped yet (run 'python3 engine.py dump-ui')")

    dialogue_files = glob.glob(os.path.join(TRANSLATIONS_DIR, "dialogue_*.json"))
    if dialogue_files:
        total_d = 0
        total_tr = 0
        for df in dialogue_files:
            with open(df, "r", encoding="utf-8") as f:
                d_data = json.load(f)
            total_d += len(d_data)
            total_tr += sum(1 for e in d_data if e.get("tr"))
        pct = (total_tr / total_d * 100) if total_d else 0
        print(f"Dialogues ({len(dialogue_files)} levels): {total_tr} / {total_d} translated ({pct:.1f}%)")
    else:
        print("Dialogues: Not dumped yet (run 'python3 engine.py dump-all-dialogues')")


def main():
    parser = argparse.ArgumentParser(description="Harry Potter PS1 Localization Engine")
    parser.add_argument("--bin", default=DEFAULT_BIN, help="Path to input .bin disc image")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("dump-ui", help="Dump UI & system strings from ENGLISH.BIN to JSON")

    p_dump_d = sub.add_parser("dump-dialogue", help="Dump dialogue/quests from a specific WAD")
    p_dump_d.add_argument("wad", help="Name of WAD file (e.g. T1L1M000)")

    sub.add_parser("dump-all-dialogues", help="Scan and dump dialogue from all level WADs")

    sub.add_parser("build-ui", help="Compile ui_english.json back into ENGLISH.BIN")

    p_build_d = sub.add_parser("build-dialogue", help="Compile dialogue JSON back into WAD with repointing")
    p_build_d.add_argument("wad", help="Name of WAD file (e.g. T1L1M000)")

    p_patch = sub.add_parser("patch-disc", help="Patch modified files into PS1 .bin image with valid EDC")
    p_patch.add_argument("--output", help="Output .bin file path (default: Harry Potter (Turkish).bin)")

    sub.add_parser("status", help="Show translation progress")

    args = parser.parse_args()
    if args.command == "dump-ui":
        cmd_dump_ui(args)
    elif args.command == "dump-dialogue":
        cmd_dump_dialogue(args)
    elif args.command == "dump-all-dialogues":
        cmd_dump_all_dialogues(args)
    elif args.command == "build-ui":
        cmd_build_ui(args)
    elif args.command == "build-dialogue":
        cmd_build_dialogue(args)
    elif args.command == "patch-disc":
        cmd_patch_disc(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
