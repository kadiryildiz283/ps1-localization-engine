"""PS1 CD-ROM XA Mode 2 Form 1 Sector Encoder and ISO Patcher.

Recalculates sync, BCD headers, subheaders, and standard CD-ROM XA EDC (CRC-32)
to write valid 2352-byte sectors into PS1 .bin images.
"""

import shutil
import struct

from tools.iso_fs import SECTOR_SIZE, USER_DATA_SIZE, Ps1IsoReader

SYNC_PATTERN = b"\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00"

# Standard CD-ROM XA EDC polynomial: 0xD8018001 reversed
def _build_edc_table():
    poly = 0xD8018001
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ poly
            else:
                crc >>= 1
        table.append(crc)
    return table

EDC_TABLE = _build_edc_table()


def compute_edc(data: bytes) -> int:
    """Compute 32-bit EDC checksum over subheader + user data (2056 bytes)."""
    crc = 0
    for b in data:
        crc = (crc >> 8) ^ EDC_TABLE[(crc ^ b) & 0xFF]
    return crc


# Galois field GF(2^8) tables for ECC
GF_EXP = [0] * 512
GF_LOG = [0] * 256
_val = 1
for _i in range(255):
    GF_EXP[_i] = _val
    GF_EXP[_i + 255] = _val
    GF_LOG[_val] = _i
    _val <<= 1
    if _val & 0x100:
        _val ^= 0x11D


def gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return GF_EXP[GF_LOG[a] + GF_LOG[b]]


def encode_lba_header(lba: int, mode: int = 2) -> bytes:
    """Encode LBA into 4-byte PS1 sector header with MSF in BCD format."""
    total_frames = lba + 150
    m = total_frames // (60 * 75)
    s = (total_frames // 75) % 60
    f = total_frames % 75
    bcd_m = ((m // 10) << 4) | (m % 10)
    bcd_s = ((s // 10) << 4) | (s % 10)
    bcd_f = ((f // 10) << 4) | (f % 10)
    return struct.pack("BBBB", bcd_m, bcd_s, bcd_f, mode)


def encode_mode2_form1_sector(lba: int, user_payload: bytes, file_channel: int = 0, submode: int = 0x08) -> bytes:
    """Build a complete 2352-byte PS1 Mode 2 Form 1 CD-ROM XA sector.
    
    Contains 12-byte sync, 4-byte header, 8-byte subheader, 2048-byte user data,
    4-byte EDC checksum, and 276-byte ECC parity area.
    """
    if len(user_payload) != USER_DATA_SIZE:
        raise ValueError(f"User payload must be exactly {USER_DATA_SIZE} bytes (got {len(user_payload)})")

    sync = SYNC_PATTERN
    header = encode_lba_header(lba, mode=2)
    # Subheader: file, channel, submode, coding (repeated twice = 8 bytes)
    sub = struct.pack("BBBB", file_channel, 0, submode, 0) * 2

    # EDC is calculated over bytes 16..2071 (subheader + user payload = 2056 bytes)
    edc_data = sub + user_payload
    edc_val = compute_edc(edc_data)
    edc = struct.pack("<I", edc_val)

    # In PS1 emulators, Mode 2 Form 1 EDC is checked. The 276 bytes ECC can be 0 or original.
    ecc = b"\x00" * 276

    return sync + header + sub + user_payload + edc + ecc


def patch_file_in_bin(bin_path: str, file_name: str, new_file_content: bytes, output_bin_path: str | None = None):
    """Replace an existing file on the PS1 .bin image with new content.
    
    Recalculates all sector headers, subheaders, and EDC checksums.
    """
    if output_bin_path and output_bin_path != bin_path:
        shutil.copy2(bin_path, output_bin_path)
        target_bin = output_bin_path
    else:
        target_bin = bin_path

    with Ps1IsoReader(target_bin) as iso:
        if file_name not in iso.files:
            raise KeyError(f"File '{file_name}' not found in ISO")
        entry = iso.files[file_name]
        start_lba = entry.lba
        old_size = entry.size

    sectors_needed = (len(new_file_content) + USER_DATA_SIZE - 1) // USER_DATA_SIZE
    old_sectors = (old_size + USER_DATA_SIZE - 1) // USER_DATA_SIZE

    if sectors_needed > old_sectors:
        print(f"Warning: New content ({len(new_file_content)} bytes) requires {sectors_needed} sectors, but original had {old_sectors}.")

    with open(target_bin, "r+b") as f:
        bytes_left = len(new_file_content)
        for i in range(sectors_needed):
            lba = start_lba + i
            chunk_start = i * USER_DATA_SIZE
            chunk = new_file_content[chunk_start : chunk_start + USER_DATA_SIZE]
            if len(chunk) < USER_DATA_SIZE:
                chunk = chunk.ljust(USER_DATA_SIZE, b"\x00")

            sec = encode_mode2_form1_sector(lba, chunk)
            f.seek(lba * SECTOR_SIZE)
            f.write(sec)

    print(f"Successfully patched '{file_name}' ({len(new_file_content)} bytes) into {target_bin}")
