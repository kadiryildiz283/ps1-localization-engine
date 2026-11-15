#!/usr/bin/env python3
"""HP2 playthrough level-transition logger.

Maps live CD-ROM sector reads (TCP `cdrom_sector_history`) to POTTER.DAT
entries via the dump manifest, derives the active level code (T1Lx) and
logs each transition with frame + wall time. Run alongside a visible game
session to build docs/GAMEPLAY_COVERAGE.md evidence automatically.

Usage:
  python3 hp2recomp/tools/level_monitor.py [--port 4731] [--interval 0.5]
      [--manifest linux_port/dump/manifest.json] [--out hp2recomp/coverage_log.jsonl]

The sector LBA is ground truth (no BCD conversion); each WAD's LBA range is
base_lba(POTTER.DAT) + offset/2048. The most frequent WAD in the recent
sector window is the active file; its T1Lx prefix is the active level.
"""
import argparse
import json
import pathlib
import socket
import sys
import time
from collections import Counter


def load_wad_map(manifest_path):
    m = json.load(open(manifest_path))
    pd = next(f for f in m["files"] if "POTTER.DAT" in f["name"])
    base = pd["lba"]
    entries = []
    for p in m["potter"]:
        lba0 = base + p["offset"] // 2048
        lba1 = base + (p["offset"] + p["size"] + 2047) // 2048
        entries.append((lba0, lba1, p["name"]))
    entries.sort()
    return entries


def lookup(entries, lba):
    for lba0, lba1, name in entries:
        if lba0 <= lba <= lba1:
            return name
        if lba0 > lba:
            break
    return None


def level_of(name):
    if not name:
        return None
    if name.startswith("T1L"):
        return name[:4]
    if name.startswith("T1I"):
        return "INTRO"
    if name.startswith("T0"):
        return "TITLE"
    if name.startswith("FE"):
        return "SPECIAL"
    return "OTHER"


def cmd(port, c, timeout=3):
    s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    s.sendall((json.dumps(c) + "\n").encode())
    data = b""
    while not data.endswith(b"\n"):
        chunk = s.recv(1 << 20)
        if not chunk:
            break
        data += chunk
    s.close()
    return json.loads(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=4731)
    ap.add_argument("--interval", type=float, default=0.5)
    ap.add_argument("--manifest", default="linux_port/dump/manifest.json")
    ap.add_argument("--out", default="hp2recomp/coverage_log.jsonl")
    ap.add_argument("--window", type=int, default=150)
    args = ap.parse_args()

    entries = load_wad_map(args.manifest)
    print(f"{len(entries)} POTTER.DAT girdisi yüklendi; TCP {args.port}", flush=True)

    last_level = None
    last_wad = None
    fails = 0
    out = open(args.out, "a")
    while True:
        try:
            fr = cmd(args.port, {"cmd": "frame"}).get("frame")
            sh = cmd(args.port, {"cmd": "cdrom_sector_history", "count": args.window})
            names = [lookup(entries, e["lba"]) for e in sh.get("entries", [])]
            names = [n for n in names if n]
            top = Counter(names).most_common(3)
            wad = top[0][0] if top else None
            level = level_of(wad)
            fails = 0
            if level != last_level or wad != last_wad:
                rec = {
                    "t": round(time.time(), 2),
                    "frame": fr,
                    "level": level,
                    "wad": wad,
                    "top": top,
                }
                out.write(json.dumps(rec) + "\n")
                out.flush()
                print(f"f={fr} level={level} wad={wad} top={top}", flush=True)
                last_level, last_wad = level, wad
        except Exception as e:
            fails += 1
            if fails in (1, 10, 50):
                print(f"TCP erişilemiyor ({e}); wedge olabilir, frame donmuş olabilir", flush=True)
            if fails >= 200:
                print("200 ardışık hata — çıkılıyor", flush=True)
                break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
