#!/usr/bin/env python3
"""HP2 PS1 doku çözücü: dump/potter/*.IMG ve WAD içindeki TPSX chunk'ları → PNG.

Kullanım:
  python re/textures.py                 # tüm IMG + tüm WAD/TPSX → build_assets/textures/
  python re/textures.py --img BADGES    # tek IMG
  python re/textures.py --wad T1L1M000  # tek WAD
Format ayrıntısı: docs/formats/TEXTURES.md
"""
import argparse
import json
import struct
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
POTTER = ROOT / "dump" / "potter"
OUT = ROOT / "build_assets" / "textures"

# EURO1.GAM 0x8007CCDC: TPSX sayfalarının yüklendiği 4 VRAM dikdörtgeni (x,y; 256x256 halfword)
VRAM_SLOTS = [(512, 0), (512, 256), (768, 0), (768, 256)]

# ---------------------------------------------------------------- renk yardımcıları


def rgb555(px):
    """uint16 dizisi → (R,G,B) uint8 dizileri (5→8 bit, yüksek bitleri çoğalt)."""
    px = px.astype(np.uint16)
    r = (px & 31).astype(np.uint8)
    g = ((px >> 5) & 31).astype(np.uint8)
    b = ((px >> 10) & 31).astype(np.uint8)
    return (r << 3 | r >> 2), (g << 3 | g >> 2), (b << 3 | b >> 2)


def to_rgba(px16, opaque=False):
    """PS1 16-bit renk → RGBA. 0x0000 = şeffaf (GPU kuralı); opaque=True ise hepsi opak."""
    r, g, b = rgb555(px16)
    a = np.full(px16.shape, 255, np.uint8)
    if not opaque:
        a[px16 == 0] = 0
    return np.stack([r, g, b, a], -1)


def unpack4(raw, w, h):
    """4-bit paketli (düşük nibble = soldaki piksel) → (h,w) indeks."""
    a = np.frombuffer(raw, np.uint8, w * h // 2).reshape(h, w // 2)
    out = np.empty((h, w), np.uint8)
    out[:, 0::2] = a & 15
    out[:, 1::2] = a >> 4
    return out


def u16(raw, n=None, off=0):
    return np.frombuffer(raw, "<u2", n, off)


# ---------------------------------------------------------------- .IMG
# EURO1.GAM yükleyicileri (0x800119d0, 0x8001240c, 0x80032d18) başlıksız ham veri okur:
# [CLUT (16 veya 256 x u16)] + piksel (8/4-bit) ya da doğrudan 16-bit piksel. Boyut koddan/dosya boyutundan.
# ad → (tür, w, h) özel durumlar; geri kalanı dosya boyutundan.
SIZE_RULES = {
    # boyut: (tür, w, h)         tür: raw16 | p8 (CLUT256+8bit) | p4 (CLUT16+4bit)
    262144: ("raw16", 512, 256),  # LOAD*/GAMEOVER/HOGWARTS/LEGAL/QUID (0x800119d0: 16-bit 512x256)
    215040: ("raw16", 448, 240),  # BADGES (kod 448x256 ister, dosya 240 satır)
    123392: ("p8", 512, 240),  # STORY*, FE5_TTL1/2 (0x8001240c: 512x240)
    131584: ("p8", 512, 256),  # SKY*, SYNOPSIS
    42804: ("p8", 218, 194),  # FE5_TTL3 (kod 218 genişlik; yükseklik dosya boyutundan)
    31232: ("p8", 320, 96),  # FE7_* (0x80027820: 320x96)
    49664: ("p8", 128, 384),  # FE6_FL1..3 (0x80027c00: 128x384, mod 3)
    9728: ("p8", 96, 96),  # FE5_SAVE (0x80034980: 96x96)
    6656: ("p8", 96, 64),  # CARD%d / BERTIE (0x80032f30: 96x64)
    1536: ("p8", 32, 32),  # PAGE (0x8001240c mod>=2: 32x32)
    336: ("raw16", 12, 14),  # FE2_LBAR (0x80017d90: LoadImage 12x14 halfword)
    288: ("p4", 32, 16),  # TINYWIZ/GRADE* (0x80032eb4: 32x16)
    608: ("p4", 48, 24),  # INV*, *CUP, *SHLD (REPORT büyük karo: 48x24)
    2080: ("p4", 128, 32),  # WIZPAGE (0x80034430: 128x32)
    832: ("p4", 40, 40),  # GLOW (VARSAYIM: boyut/pürüzsüzlük)
    4128: ("p4", 64, 128),  # FE0_REFL (kod: ilk 64x64 yüklenir 0x80023c2c; dosya 64x128)
}
TEXT_FILES = {"SECURITY", "KEEP"}  # ASCII (EA dongle metni / hex dizgesi), doku değil
REPORT_SMALL = (1, 2, 3)  # REPORT.IMG: 12 karo; bu indeksler 32x16 (288 B), diğerleri 48x24 (608 B)
# tam ekran arka planlar: alfa kullanılmaz (yükleyici 0x0000'ı 0x8000 yapar / opak çizer)
OPAQUE_PREFIX = ("STORY", "LOAD", "SKY", "FE5_TTL", "FE6_FL")
OPAQUE_NAMES = {"SYNOPSIS", "GAMEOVER", "HOGWARTS", "LEGAL"}


def decode_img(name, d):
    """→ (meta dict, RGBA ndarray | None)"""
    stem = name[:-4]
    if stem in TEXT_FILES:
        return {"kind": "text"}, None
    if stem == "REPORT":
        return decode_report(d)
    spec = SIZE_RULES.get(len(d))
    if spec is None:
        return {"kind": "unknown", "size": len(d)}, None
    kind, w, h = spec
    opaque = stem.startswith(OPAQUE_PREFIX) or stem in OPAQUE_NAMES
    meta = {"kind": kind, "w": w, "h": h, "opaque": opaque}
    if kind == "raw16":
        px = u16(d, w * h).reshape(h, w)
        if len(d) < w * h * 2:
            return {"kind": "unknown", "size": len(d)}, None
        return meta, to_rgba(px, opaque)
    if kind == "p8":
        pal = u16(d, 256)
        idx = np.frombuffer(d, np.uint8, w * h, 512).reshape(h, w)
        meta["clut"] = 256
    else:
        pal = u16(d, 16)
        idx = unpack4(d[32:], w, h)
        meta["clut"] = 16
    if not opaque:
        # yükleyici (0x800119d0) 0x8000'ı 0 yapar → hem 0x0000 hem 0x8000 şeffaf
        pal = np.where(pal == 0x8000, 0, pal)
    else:
        pal = np.where(pal == 0, 0x8000, pal)  # 0x8001240c: 0 → 0x8000 (opak siyah)
    meta["stp_colors"] = int(((pal & 0x8000) != 0).sum())
    return meta, to_rgba(pal[idx], opaque)


def decode_report(d):
    """REPORT.IMG: 12 karo ardışık [CLUT16 + 4-bit]; 3 küçük (32x16) + 9 büyük (48x24). 4x3 ızgara."""
    cw, ch = 48, 24
    sheet = np.zeros((3 * ch, 4 * cw, 4), np.uint8)
    off, tiles = 0, []
    for i in range(12):
        w, h = (32, 16) if i in REPORT_SMALL else (48, 24)
        pal = np.where(u16(d, 16, off) == 0x8000, 0, u16(d, 16, off))
        idx = unpack4(d[off + 32 : off + 32 + w * h // 2], w, h)
        r, c = divmod(i, 4)
        sheet[r * ch : r * ch + h, c * cw : c * cw + w] = to_rgba(pal[idx])
        tiles.append({"i": i, "off": off, "w": w, "h": h})
        off += 32 + w * h // 2
    assert off == len(d), (off, len(d))
    return {"kind": "report_sheet", "w": 4 * cw, "h": 3 * ch, "tiles": tiles}, sheet


def convert_img(path_out):
    path, out = path_out
    d = path.read_bytes()
    meta, rgba = decode_img(path.name, d)
    meta["name"] = path.name
    meta["size"] = len(d)
    if rgba is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(rgba, "RGBA").save(out, compress_level=3)
    return meta


# ---------------------------------------------------------------- WAD / TPSX


def wad_chunks(d):
    """WAD: u32 toplam, sonra [4B ters ASCII tag][u32 boyut][payload]... → [(tag, ofs, size)]"""
    o, out = 4, []
    while o + 8 <= len(d):
        tag = d[o : o + 4][::-1].decode("latin1")
        size = struct.unpack_from("<I", d, o + 4)[0]
        out.append((tag, o + 8, size))
        if tag == "END " or o + 8 + size > len(d):
            break
        o += 8 + size
    return out


def rle_pages(p, pos, nhw):
    """EURO1.GAM 0x80017454 RLE: s16 n; n>=0 → n literal halfword; n<0 → 1 halfword, |n| kez tekrar."""
    out = np.zeros(nhw, "<u2")
    k, n = 0, len(p)
    while k < nhw and pos + 2 <= n:
        v = struct.unpack_from("<h", p, pos)[0]
        pos += 2
        if v >= 0:
            m = min(v, nhw - k)
            out[k : k + m] = np.frombuffer(p, "<u2", m, pos)
            pos += 2 * v
            k += v
        else:
            out[k : k - v] = struct.unpack_from("<H", p, pos)[0]
            pos += 2
            k -= v
    return out, pos


def parse_tpsx(p):
    """TPSX payload'ı (EURO1.GAM 0x80018054 ile aynı sıra) → dict"""
    flags = struct.unpack_from("<I", p, 0)[0]
    q, name, extra = 4, "", 0
    if flags & 0x14:
        nlen = 0x20 if flags & 4 else 0x40
        name = p[q : q + nlen].split(b"\0")[0].decode("latin1")
        q += nlen
        extra = struct.unpack_from("<I", p, q)[0]
        q += 4 + 0x800  # 0x800 bayt tablo (incelenen WAD'larda hep 0)
    nrec, npg = struct.unpack_from("<II", p, q)
    q += 8
    recs = np.frombuffer(p, np.uint8, nrec * 12, q).reshape(nrec, 12)
    q += nrec * 12
    na, nb = struct.unpack_from("<II", p, q)
    q += 8
    anim = list(struct.unpack_from("<%dI" % na, p, q))
    q += na * 4
    if flags & 8:
        q += 5 * 0xC00
    nhw = npg * 65536
    if flags & 2:
        px, end = rle_pages(p, q, nhw)
    else:
        px, end = u16(p, nhw, q).copy(), q + nhw * 2
    return dict(flags=flags, name=name, extra=extra, nrec=nrec, npg=npg, recs=recs, anim=anim, nb=nb,
                pages=px.reshape(npg, 256, 256), end=end, size=len(p), data_start=q)


def make_vram(pages):
    vram = np.zeros((512, 1024), "<u2")
    for i, pg in enumerate(pages):
        x, y = VRAM_SLOTS[i]
        vram[y : y + 256, x : x + 256] = pg
    return vram


def rec_fields(r):
    """12 bayt: u0 v0 clut(u16) u1 v1 tpage(u16) u2 v2 u3 v3 (PS1 GPU dörtgen UV kaydı)"""
    u0, v0, clut, u1, v1, tp, u2, v2, u3, v3 = struct.unpack("<BBHBBHBBBB", bytes(r))
    return u0, v0, clut, u1, v1, tp, u2, v2, u3, v3


def render_rec(vram, f):
    """UV kaydı → (RGBA, meta) | None"""
    u0, v0, clut, u1, v1, tp, u2, v2, u3, v3 = f
    us, vs = (u0, u1, u2, u3), (v0, v1, v2, v3)
    umin, vmin = min(us), min(vs)
    w, h = max(us) - umin + 1, max(vs) - vmin + 1
    mode = (tp >> 7) & 3
    if mode == 3:
        return None
    tx, ty = (tp & 15) * 64, ((tp >> 4) & 1) * 256
    ys = ty + vmin + np.arange(h)
    meta = {"w": w, "h": h, "u": umin, "v": vmin, "mode": mode, "tx": tx, "ty": ty, "abr": (tp >> 5) & 3}
    if mode == 2:
        xs = (tx + umin + np.arange(w)) & 1023
        return to_rgba(vram[ys[:, None], xs[None, :]]), meta
    cx, cy = (clut & 0x3F) * 16, (clut >> 6) & 0x1FF
    ncol = 16 if mode == 0 else 256
    pal = vram[cy, (cx + np.arange(ncol)) & 1023]
    u = umin + np.arange(w)
    if mode == 0:
        wd = vram[ys[:, None], ((tx + (u >> 2)) & 1023)[None, :]]
        idx = (wd >> ((u & 3) * 4)[None, :]) & 15
    else:
        wd = vram[ys[:, None], ((tx + (u >> 1)) & 1023)[None, :]]
        idx = (wd >> ((u & 1) * 8)[None, :]) & 255
    meta.update(cx=cx, cy=cy, clut_flag=(clut >> 15) & 1)
    meta["stp"] = int(((pal[idx] & 0x8000) != 0).sum())
    return to_rgba(pal[idx]), meta


def convert_wad(path):
    d = path.read_bytes()
    stem = path.stem
    chunks = [c for c in wad_chunks(d) if c[0] == "TPSX"]
    if not chunks:
        return {"wad": stem, "ok": False, "why": "TPSX yok"}
    _, o, s = chunks[0]
    p = d[o : o + s]
    t = parse_tpsx(p)
    out = OUT / "WAD" / stem
    out.mkdir(parents=True, exist_ok=True)
    vram = make_vram(t["pages"])
    (out / "pages.bin").write_bytes(t["pages"].astype("<u2").tobytes())
    seen, textures, recs = {}, [], []
    for i, r in enumerate(t["recs"]):
        f = rec_fields(r)
        if not any(f):
            recs.append(None)
            continue
        key = (min(f[0], f[3], f[6], f[8]), min(f[1], f[4], f[7], f[9]), max(f[0], f[3], f[6], f[8]),
               max(f[1], f[4], f[7], f[9]), f[5], f[2])
        if key not in seen:
            res = render_rec(vram, f)
            if res is None:
                seen[key] = -1
            else:
                rgba, m = res
                m["file"] = f"t{len(textures):04d}.png"
                Image.fromarray(rgba, "RGBA").save(out / m["file"], compress_level=1)
                seen[key] = len(textures)
                textures.append(m)
        recs.append([*f, seen[key]])
    info = {
        "wad": stem, "map_name": t["name"], "flags": t["flags"], "extra": t["extra"], "pages": t["npg"],
        "vram_slots": VRAM_SLOTS[: t["npg"]], "records": t["nrec"], "unique_textures": len(textures),
        "anim_words": t["anim"], "anim_b": t["nb"], "rle_end_matches_chunk": t["end"] == t["size"],
        "recs_fields": "u0,v0,clut,u1,v1,tpage,u2,v2,u3,v3,texture_index(-1=yok)",
        "recs": recs, "textures": textures,
    }
    (out / "atlas.json").write_text(json.dumps(info, separators=(",", ":")))
    return {"wad": stem, "ok": t["end"] == t["size"], "pages": t["npg"], "records": t["nrec"],
            "textures": len(textures)}


# ---------------------------------------------------------------- CLI


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--img", help="tek IMG adı (uzantısız)")
    ap.add_argument("--wad", help="tek WAD adı (uzantısız)")
    ap.add_argument("-j", type=int, default=0, help="işlem sayısı (0=otomatik)")
    a = ap.parse_args()
    only = a.img or a.wad
    imgs = sorted(POTTER.glob("*.IMG")) if not a.wad else []
    wads = sorted(POTTER.glob("*.WAD")) if not a.img else []
    if a.img:
        imgs = [p for p in imgs if p.stem == a.img]
    if a.wad:
        wads = [p for p in wads if p.stem == a.wad]
    if only and not (imgs or wads):
        sys.exit("bulunamadı: " + only)
    with Pool(a.j or None) as pool:
        metas = pool.map(convert_img, [(p, OUT / "IMG" / (p.stem + ".png")) for p in imgs], chunksize=8)
        res = pool.map(convert_wad, wads)
    full = not only
    if imgs:
        ok = [m for m in metas if m["kind"] in ("raw16", "p8", "p4", "report_sheet")]
        if full:
            (OUT / "img_index.json").write_text(json.dumps(metas, indent=1))
        non = [m["name"] for m in metas if m["kind"] in ("text", "unknown")]
        print(f"IMG: {len(ok)}/{len(imgs)} PNG'ye çözüldü; doku olmayan/çözülmeyen: {non}")
    if wads:
        ok = [r for r in res if r["ok"]]
        if full:
            (OUT / "wad_index.json").write_text(json.dumps(res, indent=1))
        print(f"WAD: {len(ok)}/{len(wads)} TPSX çözüldü (RLE akışı chunk sonunda bitti); "
              f"toplam {sum(r.get('textures', 0) for r in res)} benzersiz doku PNG")
        bad = [r for r in res if not r["ok"]]
        if bad:
            print("WAD sorunlu:", bad)


if __name__ == "__main__":
    main()
