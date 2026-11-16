"""Orijinal PS1 imajının %100 dökümü (dosya sistemi + sektör kapsama kanıtı).

Kullanım:
    python tools/dump_disc.py "<orijinal>.bin" <çıktı_dizini>

Çıktı:
    <out>/disc/<yol>        ISO9660 dosyaları (Form1 kullanıcı verisi; Form2 sektörlü
                            dosyalar için ayrıca <ad>.raw2352 = ham 2352B sektörler)
    <out>/potter/<ad>       POTTER.DAT içindeki her girdi
    <out>/system_area.bin   LBA 0-15
    <out>/manifest.json     her dosyanın LBA/boyut/sha256 + sektör kapsama özeti
"""

import hashlib
import json
import os
import struct
import sys

SECTOR = 2352
HDR = 24


def read_sector(f, lba):
    f.seek(lba * SECTOR)
    return f.read(SECTOR)


def user_data(f, lba):
    return read_sector(f, lba)[HDR : HDR + 2048]


def read_extent(f, lba, size):
    out = bytearray()
    for i in range((size + 2047) // 2048):
        out += user_data(f, lba + i)
    return bytes(out[:size])


def walk(f, lba, size, path, files, dirs):
    data = read_extent(f, lba, size)
    off = 0
    while off < size:
        ln = data[off]
        if ln == 0:
            off = (off // 2048 + 1) * 2048
            continue
        rec = data[off : off + ln]
        flba, fsize = struct.unpack("<I", rec[2:6])[0], struct.unpack("<I", rec[10:14])[0]
        is_dir = bool(rec[25] & 2)
        name = rec[33 : 33 + rec[32]].decode("ascii", "ignore").split(";")[0]
        off += ln
        if name in ("\x00", "\x01", ""):
            continue
        full = f"{path}/{name}" if path else name
        if is_dir:
            dirs.append((full, flba, fsize))
            walk(f, flba, fsize, full, files, dirs)
        else:
            files.append((full, flba, fsize))


def main(bin_path, out):
    files, dirs = [], []
    covered = {}  # lba -> owner
    total = os.path.getsize(bin_path) // SECTOR
    with open(bin_path, "rb") as f:
        os.makedirs(out, exist_ok=True)
        with open(f"{out}/system_area.bin", "wb") as sa:
            for lba in range(16):
                sa.write(user_data(f, lba))
                covered[lba] = "system_area"
        pvd = user_data(f, 16)
        assert pvd[1:6] == b"CD001"
        root_lba, root_size = struct.unpack("<I", pvd[158:162])[0], struct.unpack("<I", pvd[166:170])[0]
        vol_sectors = struct.unpack("<I", pvd[80:84])[0]
        dirs.append(("", root_lba, root_size))
        walk(f, root_lba, root_size, "", files, dirs)
        for lba in range(16, 18):
            covered[lba] = "volume_descriptors"
        for d, dl, ds in dirs:
            for i in range((ds + 2047) // 2048):
                covered[dl + i] = f"dir:{d or '/'}"

        manifest = {"volume_sectors": vol_sectors, "image_sectors": total, "files": [], "potter": []}
        for name, lba, size in files:
            dst = os.path.join(out, "disc", name)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            n = (size + 2047) // 2048
            forms = {"f1": 0, "f2": 0}
            h = hashlib.sha256()
            left = size
            raw_needed = False
            with open(dst, "wb") as o:
                for i in range(n):
                    raw = read_sector(f, lba + i)
                    sub = raw[18]
                    if sub & 0x20:
                        forms["f2"] += 1
                        raw_needed = True
                    else:
                        forms["f1"] += 1
                    chunk = raw[HDR : HDR + 2048][: min(left, 2048)]
                    o.write(chunk)
                    h.update(chunk)
                    left -= len(chunk)
                    covered[lba + i] = name
            if raw_needed:
                with open(dst + ".raw2352", "wb") as o:
                    for i in range(n):
                        o.write(read_sector(f, lba + i))
            manifest["files"].append(
                {"name": name, "lba": lba, "size": size, "sha256": h.hexdigest(), **forms}
            )

        # POTTER.DAT
        pd = next((x for x in files if x[0] == "POTTER.DAT"), None)
        pdir = next((x for x in files if x[0] == "POTTER.DIR"), None)
        if pd and pdir:
            dir_bytes = read_extent(f, pdir[1], pdir[2])
            cnt = struct.unpack("<I", dir_bytes[:4])[0]
            os.makedirs(f"{out}/potter", exist_ok=True)
            for i in range(cnt):
                nm, sz, of = struct.unpack("<12sII", dir_bytes[4 + i * 20 : 24 + i * 20])
                nm = nm.rstrip(b"\0").decode("ascii", "ignore")
                data = read_extent(f, pd[1] + of // 2048, sz) if of % 2048 == 0 else None
                assert data is not None, f"unaligned DAT entry {nm}"
                with open(f"{out}/potter/{nm}", "wb") as o:
                    o.write(data)
                manifest["potter"].append(
                    {"name": nm, "offset": of, "size": sz, "sha256": hashlib.sha256(data).hexdigest()}
                )

    uncovered = [l for l in range(total) if l not in covered]
    manifest["uncovered_sectors"] = len(uncovered)
    manifest["uncovered_ranges"] = []
    for l in uncovered:
        if manifest["uncovered_ranges"] and manifest["uncovered_ranges"][-1][1] == l - 1:
            manifest["uncovered_ranges"][-1][1] = l
        else:
            manifest["uncovered_ranges"].append([l, l])
    with open(f"{out}/manifest.json", "w") as o:
        json.dump(manifest, o, indent=1)
    print(f"image_sectors={total} volume_sectors={vol_sectors} files={len(files)} "
          f"dirs={len(dirs)} potter_entries={len(manifest['potter'])} "
          f"uncovered_sectors={len(uncovered)} ranges={manifest['uncovered_ranges'][:8]}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
