import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.cd_patcher import encode_mode2_form1_sector
from tools.iso_fs import SECTOR_SIZE, USER_DATA_SIZE

TARGET_BIN = "Harry Potter and the Chamber of Secrets (Turkish).bin"
WAD_PATH = "extracted/T1L2M001.WAD"
START_LBA = 86655 # LBA for T1L2M001.WAD inside POTTER.DAT

def main():
    print("=" * 70)
    print("TARGETED DISC PATCHER FOR T1L2M001.WAD")
    print("=" * 70)

    with open(WAD_PATH, "rb") as f:
        wad_bytes = f.read()

    num_sectors = (len(wad_bytes) + USER_DATA_SIZE - 1) // USER_DATA_SIZE
    print(f"Patching {len(wad_bytes)} bytes ({num_sectors} sectors) starting at LBA {START_LBA}...")

    t0 = time.time()
    with open(TARGET_BIN, "r+b") as f:
        for i in range(num_sectors):
            lba = START_LBA + i
            chunk = wad_bytes[i * USER_DATA_SIZE : (i + 1) * USER_DATA_SIZE]
            if len(chunk) < USER_DATA_SIZE:
                chunk = chunk.ljust(USER_DATA_SIZE, b"\x00")
            sector = encode_mode2_form1_sector(lba, chunk)
            f.seek(lba * SECTOR_SIZE)
            f.write(sector)

    dt = time.time() - t0
    print(f"Successfully patched {num_sectors} sectors in {dt:.2f}s!")

if __name__ == "__main__":
    main()
