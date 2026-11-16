#!/usr/bin/env python3
"""DEM (EURO1.GAM demo/replay girdi kaydı) çözücü + JSON döküm.

Biçim (bkz. docs/formats/DEM.md): u32 sayı, sonra sayı × 8 bayt kayıt:
    u16 buttons   PSX pad maskesi (aktif-yüksek, ~padword)
    u16 cam_yaw   kamera yönü; 16-bit sarılmamış açı, kullanımda &0xFFF (4096 = 360°)
    u16 dt        kare süresi: 128 = 1 VSync, 256 = 1 mantık adımı
    s8  stick_x   (+127 = sol, -128 = sağ)
    s8  stick_y   (+127 = yukarı, -128 = aşağı)

Kullanım:
    dem.py dump/potter/T1L1M002.DEM              # özet + ilk kareler (stdout)
    dem.py dump/potter/T1L1M002.DEM --json       # tüm kareler JSON (stdout)
    dem.py dump/potter/*.DEM --check             # tüm dosyalarda doğrulama
    dem.py dump/potter/*.DEM --json --outdir D   # her dosya için D/<ad>.json
"""
import argparse
import json
import struct
import sys
from pathlib import Path

REC = struct.Struct("<HHHbb")
BUTTONS = ["SELECT", "L3", "R3", "START", "UP", "RIGHT", "DOWN", "LEFT",
           "L2", "R2", "L1", "R1", "TRIANGLE", "CIRCLE", "CROSS", "SQUARE"]
PLAY_STOP_REMAINING = 30  # EURO1.GAM 0x800267bc: kalan < 0x1e ise demo biter
VSYNC_HZ = 50  # Avrupa (PAL) diski


def names(mask):
    return [n for i, n in enumerate(BUTTONS) if mask >> i & 1]


def decode(data):
    if len(data) < 4:
        raise ValueError("DEM çok kısa")
    (count,) = struct.unpack_from("<I", data)
    if len(data) != 4 + 8 * count:
        raise ValueError(f"boyut {len(data)} != 4+8*{count}")
    frames = []
    for i in range(count):
        b, yaw, dt, sx, sy = REC.unpack_from(data, 4 + 8 * i)
        frames.append({"i": i, "buttons": b, "names": names(b), "cam_yaw": yaw,
                       "cam_yaw12": yaw & 0xFFF, "dt": dt, "stick_x": sx, "stick_y": sy})
    return frames


def check(frames):
    """Kod yolundaki (0x80013600) D-pad→stick eşlemesi ve dt değerleri. Hata listesi döner."""
    err = []
    for f in frames:
        b = f["buttons"]
        ex = 127 if b & 0x80 else -128 if b & 0x20 else 0   # sol / sağ
        ey = 127 if b & 0x10 else -128 if b & 0x40 else 0   # yukarı / aşağı
        if (f["stick_x"], f["stick_y"]) != (ex, ey):
            err.append((f["i"], "stick≠dpad"))
        if f["dt"] not in (128 * k for k in range(1, 17)):
            err.append((f["i"], "dt?"))
    return err


def summary(frames):
    dt = sum(f["dt"] for f in frames)
    played = max(len(frames) - PLAY_STOP_REMAINING, 0)
    pressed = sorted({n for f in frames for n in f["names"]}, key=BUTTONS.index)
    return {"frames": len(frames), "played_frames": played,
            "total_dt": dt, "total_vsync": dt / 128, "ticks": dt / 256,
            "seconds_pal_all": dt / 128 / VSYNC_HZ,
            "seconds_pal_played": sum(f["dt"] for f in frames[:played]) / 128 / VSYNC_HZ,
            "buttons_used": pressed,
            "dt_values": sorted({f["dt"] for f in frames})}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", action="store_true", help="tüm kareleri JSON olarak yaz")
    ap.add_argument("--check", action="store_true", help="doğrulama özeti (dosya başına)")
    ap.add_argument("--outdir", help="--json ile: her dosya için <outdir>/<ad>.json")
    ap.add_argument("-n", type=int, default=12, help="özet modunda gösterilecek kare sayısı")
    a = ap.parse_args()
    rc = 0
    for p in map(Path, a.files):
        frames = decode(p.read_bytes())
        err = check(frames)
        rc |= bool(err)
        doc = {"file": p.name, "summary": summary(frames), "check_errors": err[:20], "frames": frames}
        if a.json:
            txt = json.dumps(doc, indent=1)
            if a.outdir:
                out = Path(a.outdir)
                out.mkdir(parents=True, exist_ok=True)
                (out / (p.stem + ".json")).write_text(txt)
            else:
                print(txt)
        elif a.check:
            s = doc["summary"]
            print(f"{p.name}: kare={s['frames']} hata={len(err)} dt={s['dt_values']} "
                  f"süre(PAL, oynanan)={s['seconds_pal_played']:.1f}s tuşlar={','.join(s['buttons_used']) or '-'}")
        else:
            print(p.name, json.dumps(doc["summary"]))
            for f in frames[:a.n]:
                print(f"  #{f['i']:3d} btn=0x{f['buttons']:04x} {'+'.join(f['names']) or '-':<12} "
                      f"yaw={f['cam_yaw']:5d}({f['cam_yaw12']:4d}) dt={f['dt']:4d} stick=({f['stick_x']:4d},{f['stick_y']:4d})")
    return rc


if __name__ == "__main__":
    sys.exit(main())
