"""PS1 ISO9660 Mode 2 Form 1 CD-ROM XA Reader and Extractor.

Handles reading the ISO9660 filesystem within 2352-byte sector PS1 .bin images
and extracting files or streaming data.
"""

import os
import struct

SECTOR_SIZE = 2352
USER_DATA_OFFSET = 24
USER_DATA_SIZE = 2048


class IsoFileEntry:
    def __init__(self, name: str, lba: int, size: int, is_dir: bool):
        self.name = name
        self.lba = lba
        self.size = size
        self.is_dir = is_dir

    def __repr__(self) -> str:
        return f"<IsoFileEntry {self.name}: LBA={self.lba}, Size={self.size}>"


class Ps1IsoReader:
    def __init__(self, bin_path: str):
        self.bin_path = bin_path
        self._file = open(bin_path, "rb")
        self.files: dict[str, IsoFileEntry] = {}
        self._parse_iso()

    def close(self):
        if self._file and not self._file.closed:
            self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def read_sector_user_data(self, lba: int) -> bytes:
        """Read 2048 bytes of user data from Mode 2 Form 1 sector at given LBA."""
        self._file.seek(lba * SECTOR_SIZE)
        raw = self._file.read(SECTOR_SIZE)
        if len(raw) < SECTOR_SIZE:
            raise EOFError(f"Unexpected end of file reading LBA {lba}")
        return raw[USER_DATA_OFFSET : USER_DATA_OFFSET + USER_DATA_SIZE]

    def _parse_iso(self):
        """Read Primary Volume Descriptor (LBA 16) and parse root directory."""
        pvd = self.read_sector_user_data(16)
        if pvd[1:6] != b"CD001":
            raise ValueError("Not a valid ISO9660 Primary Volume Descriptor")

        root_record = pvd[156 : 156 + 34]
        root_lba = struct.unpack("<I", root_record[2:6])[0]
        root_size = struct.unpack("<I", root_record[10:14])[0]

        sectors_to_read = (root_size + USER_DATA_SIZE - 1) // USER_DATA_SIZE
        dir_data = bytearray()
        for i in range(sectors_to_read):
            dir_data.extend(self.read_sector_user_data(root_lba + i))

        offset = 0
        while offset < root_size:
            length = dir_data[offset]
            if length == 0:
                # Padding to next 2048-byte sector boundary
                offset = ((offset // USER_DATA_SIZE) + 1) * USER_DATA_SIZE
                continue
            record = dir_data[offset : offset + length]
            file_lba = struct.unpack("<I", record[2:6])[0]
            file_size = struct.unpack("<I", record[10:14])[0]
            flags = record[25]
            name_len = record[32]
            raw_name = record[33 : 33 + name_len].decode("ascii", errors="ignore")
            # Remove ISO version suffix ';1'
            clean_name = raw_name.split(";")[0] if ";" in raw_name else raw_name
            is_dir = bool(flags & 2)

            if clean_name not in ("", "\x00", "\x01"):
                entry = IsoFileEntry(clean_name, file_lba, file_size, is_dir)
                self.files[clean_name] = entry
                self.files[raw_name] = entry

            offset += length

    def extract_file(self, file_name: str, output_path: str):
        """Extract a single file from the ISO to local disk."""
        if file_name not in self.files:
            raise KeyError(f"File '{file_name}' not found in ISO. Available: {list(self.files.keys())}")

        entry = self.files[file_name]
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        sectors_needed = (entry.size + USER_DATA_SIZE - 1) // USER_DATA_SIZE
        bytes_left = entry.size

        with open(output_path, "wb") as out_f:
            for i in range(sectors_needed):
                chunk = self.read_sector_user_data(entry.lba + i)
                to_write = min(bytes_left, USER_DATA_SIZE)
                out_f.write(chunk[:to_write])
                bytes_left -= to_write

    def read_file_bytes(self, file_name: str, start_offset: int = 0, length: int | None = None) -> bytes:
        """Stream a byte range from a file on the ISO without extracting the whole file."""
        if file_name not in self.files:
            raise KeyError(f"File '{file_name}' not found in ISO")

        entry = self.files[file_name]
        if length is None:
            length = entry.size - start_offset

        end_offset = min(start_offset + length, entry.size)
        if start_offset >= entry.size:
            return b""

        first_sector = start_offset // USER_DATA_SIZE
        last_sector = (end_offset - 1) // USER_DATA_SIZE
        sector_offset = start_offset % USER_DATA_SIZE

        buf = bytearray()
        for sec in range(first_sector, last_sector + 1):
            chunk = self.read_sector_user_data(entry.lba + sec)
            buf.extend(chunk)

        result = buf[sector_offset : sector_offset + (end_offset - start_offset)]
        return bytes(result)
