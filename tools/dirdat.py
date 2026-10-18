"""Argonaut Games POTTER.DIR / POTTER.DAT Unpacker and Repacker.

Used in PS1 games like Harry Potter and the Chamber of Secrets.
Handles unpacking 357 files, updating individual files, and repacking
with 2048-byte sector alignment and updated pointer table.
"""

import os
import struct

from tools.iso_fs import USER_DATA_SIZE, Ps1IsoReader

DIR_ENTRY_SIZE = 20


class DatEntry:
    def __init__(self, name: str, size: int, offset: int, data: bytes | None = None):
        self.name = name
        self.size = size
        self.offset = offset
        self.data = data

    def __repr__(self) -> str:
        return f"<DatEntry {self.name}: Size={self.size}, Offset={self.offset}>"


class DirDatArchive:
    def __init__(self):
        self.entries: list[DatEntry] = []
        self.entry_map: dict[str, DatEntry] = {}

    @classmethod
    def from_iso(cls, iso_reader: Ps1IsoReader) -> "DirDatArchive":
        """Read DIR table and DAT entries directly from ISO reader."""
        archive = cls()
        dir_bytes = iso_reader.read_file_bytes("POTTER.DIR")
        num_files = struct.unpack("<I", dir_bytes[:4])[0]

        for i in range(num_files):
            chunk = dir_bytes[4 + i * DIR_ENTRY_SIZE : 4 + (i + 1) * DIR_ENTRY_SIZE]
            raw_name, size, offset = struct.unpack("<12sII", chunk)
            name = raw_name.rstrip(b"\x00").decode("ascii", errors="ignore")
            entry = DatEntry(name, size, offset)
            archive.entries.append(entry)
            archive.entry_map[name] = entry

        return archive

    @classmethod
    def from_files(cls, dir_path: str, dat_path: str) -> "DirDatArchive":
        """Read DIR and DAT from standalone disk files."""
        archive = cls()
        with open(dir_path, "rb") as f:
            dir_bytes = f.read()

        num_files = struct.unpack("<I", dir_bytes[:4])[0]
        for i in range(num_files):
            chunk = dir_bytes[4 + i * DIR_ENTRY_SIZE : 4 + (i + 1) * DIR_ENTRY_SIZE]
            raw_name, size, offset = struct.unpack("<12sII", chunk)
            name = raw_name.rstrip(b"\x00").decode("ascii", errors="ignore")
            entry = DatEntry(name, size, offset)
            archive.entries.append(entry)
            archive.entry_map[name] = entry

        return archive

    def extract_entry_from_iso(self, iso_reader: Ps1IsoReader, name: str, output_path: str):
        """Extract a single entry from POTTER.DAT on the ISO without extracting the whole 578MB archive."""
        if name not in self.entry_map:
            raise KeyError(f"File '{name}' not found in archive")

        entry = self.entry_map[name]
        data = iso_reader.read_file_bytes("POTTER.DAT", entry.offset, entry.size)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(data)

    def extract_all_from_iso(self, iso_reader: Ps1IsoReader, output_dir: str):
        """Extract all 357 files from the ISO's POTTER.DAT into an output directory."""
        os.makedirs(output_dir, exist_ok=True)
        print(f"Extracting {len(self.entries)} files from POTTER.DAT...")
        for i, entry in enumerate(self.entries):
            out_file = os.path.join(output_dir, entry.name)
            data = iso_reader.read_file_bytes("POTTER.DAT", entry.offset, entry.size)
            with open(out_file, "wb") as f:
                f.write(data)
            if (i + 1) % 50 == 0 or (i + 1) == len(self.entries):
                print(f"  [{i + 1}/{len(self.entries)}] Extracted {entry.name} ({entry.size} bytes)")
        print("All files extracted successfully.")

    @staticmethod
    def repack_from_directory(input_dir: str, output_dir_file: str, output_dat_file: str, file_order: list[str] | None = None):
        """Repack a directory of files into new POTTER.DIR and POTTER.DAT files.
        
        Ensures 2048-byte sector padding between each file and builds the updated index table.
        """
        if file_order is None:
            # Sort naturally or preserve order
            file_order = sorted([f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))])

        dir_entries = bytearray()
        dir_entries.extend(struct.pack("<I", len(file_order)))

        os.makedirs(os.path.dirname(os.path.abspath(output_dir_file)), exist_ok=True)
        os.makedirs(os.path.dirname(os.path.abspath(output_dat_file)), exist_ok=True)

        with open(output_dat_file, "wb") as dat_f:
            for name in file_order:
                file_path = os.path.join(input_dir, name)
                with open(file_path, "rb") as in_f:
                    content = in_f.read()

                offset = dat_f.tell()
                size = len(content)

                dat_f.write(content)

                # Pad out to next 2048-byte sector boundary
                padding_needed = (USER_DATA_SIZE - (dat_f.tell() % USER_DATA_SIZE)) % USER_DATA_SIZE
                if padding_needed > 0:
                    dat_f.write(b"\x00" * padding_needed)

                # 12 bytes filename null-padded
                raw_name = name.encode("ascii")[:12].ljust(12, b"\x00")
                dir_entries.extend(struct.pack("<12sII", raw_name, size, offset))

        with open(output_dir_file, "wb") as dir_f:
            dir_f.write(dir_entries)

        print(f"Repacked {len(file_order)} files into:")
        print(f"  DIR: {output_dir_file} ({len(dir_entries)} bytes)")
        print(f"  DAT: {output_dat_file} ({os.path.getsize(output_dat_file)} bytes)")
