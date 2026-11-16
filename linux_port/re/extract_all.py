#!/usr/bin/env python3
"""HP2 PS1: TÜM oyun assetlerini statik dosyalara çıkar (motor bunlardan çağırır).

Üretilen düzen (build_assets/):
  textures/WAD/<stem>/tpsx.bin   ham TPSX doku bankası (motor tpsx_load ile okur)
  textures/IMG/*.png             IMG çizimleri (textures.py)
  levels/<stem>/dpsx.bin         ham DPSX seviye verisi (motor dpsx_load ile okur)
  levels/<stem>/mesh.obj         okunabilir 3B map (level_geom.py)
  dialogues/<stem>/lpsx.bin      ham LPSX diyalog tablosu (motor lpsx_load ile okur)
  dialogues/<stem>.json          okunabilir EN/FR/DE diyalog metni
  audio/WAD/<stem>/<n>.wav       SPSX ses/müzik (audio.py)
  audio/XA/*.wav                 EA.STR XA müzik (audio.py)
  video/EA_frame_*.png           STR video kareleri (str_video.py)
  animations/<stem>.json         DEM replay/kamera animasyonu (dem.py)
  wads.txt                       seviye WAD kök adları (motor listesi)

Kullanım: python re/extract_all.py   (idempotent; dump/potter'dan okur)
"""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POTTER = ROOT / "dump" / "potter"
OUT = ROOT / "build_assets"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import level_geom
import dem
import str_video


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def decode_str(pool, off):
    """lpsx.c decode_str ile birebir: Caesar -1 (0x60..0x79 -> +1)."""
    if off >= len(pool):
        return ""
    cur, out = off, []
    while cur + 2 <= len(pool):
        v = u16(pool, cur)
        cur += 2
        if v == 0:
            break
        if 0x60 <= v <= 0x79:
            out.append(chr(v + 1))
        elif 32 <= v < 127:
            out.append(chr(v))
        else:
            out.append(" ")
    return "".join(out)


def lpsx_json(buf):
    n = u32(buf, 4)
    pool = buf[12 + n * 16:]
    recs = []
    for i in range(n):
        b = 12 + i * 16
        recs.append({"en": decode_str(pool, u32(buf, b)),
                     "fr": decode_str(pool, u32(buf, b + 4)),
                     "de": decode_str(pool, u32(buf, b + 8))})
    return recs


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wads = []
    stats = {"tpsx": 0, "dpsx": 0, "lpsx": 0, "obj": 0, "dem": 0}
    for p in sorted(POTTER.glob("*.WAD")):
        stem = p.stem
        data = p.read_bytes()
        chunks = {t: (o, n) for t, o, n in level_geom.wad_chunks(data)}
        if "TPSX" in chunks:
            o, n = chunks["TPSX"]
            d = OUT / "textures" / "WAD" / stem
            d.mkdir(parents=True, exist_ok=True)
            (d / "tpsx.bin").write_bytes(data[o:o + n])
            stats["tpsx"] += 1
        if "DPSX" in chunks:
            o, n = chunks["DPSX"]
            d = OUT / "levels" / stem
            d.mkdir(parents=True, exist_ok=True)
            (d / "dpsx.bin").write_bytes(data[o:o + n])
            stats["dpsx"] += 1
            wads.append(stem)
            try:
                sec = level_geom.parse_dpsx(data[o:o + n])
                V, T, meta = level_geom.build_mesh(sec)
                level_geom.write_obj(d / "mesh.obj", V, T, meta)
                stats["obj"] += 1
            except Exception as e:  # noqa: BLE001 - mesh optional, bin primary
                print(f"  ! {stem} mesh: {e}", file=sys.stderr)
        if "LPSX" in chunks:
            o, n = chunks["LPSX"]
            buf = data[o:o + n]
            d = OUT / "dialogues" / stem
            d.mkdir(parents=True, exist_ok=True)
            (d / "lpsx.bin").write_bytes(buf)
            (OUT / "dialogues" / f"{stem}.json").write_text(
                json.dumps(lpsx_json(buf), indent=1, ensure_ascii=False))
            stats["lpsx"] += 1
    for p in sorted(POTTER.glob("*.DEM")):
        d = OUT / "animations"
        d.mkdir(parents=True, exist_ok=True)
        frames = dem.decode(p.read_bytes())
        (d / f"{p.stem}.json").write_text(json.dumps(
            {"file": p.name, "summary": dem.summary(frames), "frames": frames}, indent=1))
        # motorun attract kamerası için ikili cam_yaw pisti
        (d / f"{p.stem}.bin").write_bytes(
            struct.pack("<I", len(frames)) + b"".join(struct.pack("<H", f["cam_yaw"]) for f in frames))
        stats["dem"] += 1
    # STR video: ham RGB kareler (motor PNG çözücü olmadan çağırır) + manifest
    raw = ROOT / "dump" / "disc" / "EA.STR.raw2352"
    if raw.exists():
        vd = OUT / "video"
        vd.mkdir(parents=True, exist_ok=True)
        d, n = str_video.read_sectors(str(raw))
        frames = str_video.assemble_frames(str_video.classify(d, n))
        names = []
        for no in sorted(frames):
            rgb, ok, _ = str_video.decode_frame(frames[no])
            h, w, _ = rgb.shape
            (vd / f"EA_frame_{no:04d}.rgb").write_bytes(struct.pack("<HH", w, h) + rgb.tobytes())
            names.append(f"EA_frame_{no:04d}.rgb")
        (vd / "frames.txt").write_text("\n".join(names) + "\n")
        stats["video"] = len(names)
    (OUT / "wads.txt").write_text("\n".join(wads) + "\n")
    print(json.dumps({"levels": len(wads), **stats}, indent=1))


if __name__ == "__main__":
    main()
