#!/usr/bin/env python3
"""Bayrak (dil seçim) ekranı RE: EURO1.GAM'da durum yapısı xref + kritik PC disassembly.

Kanıt (canlı write-trace, 2026-11-16):
  seçim globali u32 @ 0xD8B3C = durum yapısı 0xD8A84 + 0xB8
  seçim artışı yazan PC 0x3DD88 (ra 0x3DD6C), periyodik kopya PC 0x3B908 (ra 0x3B904)
  bayrak dokuları FE6_FL1..3 (128x384 p8), FE7_xx dil paketleri (320x96 p8)

Kullanım: python3 tools/flag_ui_re.py [xref|disasm <addr> [n]]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "linux_port" / "analysis"))
from mipsa import Exe, find_lui_refs

EURO1 = Path(__file__).resolve().parents[2] / "linux_port" / "dump" / "disc" / "EURO1.GAM"


def main():
    exe = Exe(str(EURO1))
    cmd = sys.argv[1] if len(sys.argv) > 1 else "xref"
    if cmd == "xref":
        for lo, hi, label in [(0xD8A84, 0xD8A88, "durum yapısı 0xD8A84"),
                              (0xD8B3C, 0xD8B40, "seçim 0xD8B3C"),
                              (0xD8A84, 0xD8C00, "durum yapısı geniş")]:
            refs = find_lui_refs(exe, lo, hi)
            print(f"=== {label}: {len(refs)} ref ===")
            for a, v in refs:
                print(f"  {a & 0x1FFFFFFF:08x} -> {v:08x}")
    elif cmd == "disasm":
        a = int(sys.argv[2], 0)
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 64
        for line in exe.disasm(a, n):
            print(line)


if __name__ == "__main__":
    main()
