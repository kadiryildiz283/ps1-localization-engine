#!/usr/bin/env python3
"""HP2 (PS1) WAD -> 3B seviye geometrisi (DPSX statik mesh örnekleri) -> OBJ (+ ortografik PNG).

Format ayrıntıları: docs/formats/DPSX.md, docs/formats/UNIF_PORT.md.
Kullanım:  level_geom.py dump/potter/T1L1M000.WAD [--out build_assets/levels] [--render]
"""
import argparse
import math
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- WAD chunk zinciri
def wad_chunks(data):
    """[(tag, payload_ofset, boyut)]; tag diskte ters yazılıdır ('XSPD' -> 'DPSX')."""
    o, out = 4, []
    while o + 8 <= len(data):
        tag = data[o : o + 4][::-1].decode("latin1")
        n = struct.unpack_from("<I", data, o + 4)[0]
        out.append((tag, o + 8, n))
        o += 8 + n
        if tag == "END ":
            break
    return out


def chunk(data, tag):
    for t, o, n in wad_chunks(data):
        if t == tag:
            return data[o : o + n]
    raise KeyError(tag)


# ---------------------------------------------------------------- DPSX ayrıştırıcı
# Bkz. EURO1.GAM 0x80018260.. (DPSX işleyici). s1 yürüyüşünü birebir yansıtır.
def parse_dpsx(b):
    u32 = lambda a: struct.unpack_from("<I", b, a)[0]
    u16 = lambda a: struct.unpack_from("<H", b, a)[0]
    F = u32(0)
    p = 0x808  # 8 bayt başlık + 0x800 bayt (çalışma zamanı tamponu, diskte 0)
    sec = {"flags": F}
    # --- A: iskelet/karakter modelleri (her biri 0x68 başlık + inline diziler)
    nA = u32(p); p += 4
    sec["A_off"] = p
    A = []
    for _ in range(nA):
        n1, nB = u32(p + 0x48), u32(p + 0x54)
        nP = u16(p + 0x5C) + u16(p + 0x5E) + u16(p + 0x60)
        A.append({"off": p, "nvert": n1, "nface": nB, "nprim": nP})
        p += 0x68 + n1 * 16 + nB * 20 + nP * 32
    sec["A"] = A
    # --- B: animasyon tabloları
    nBn = u32(p); p += 4
    for _ in range(nBn):
        h = [u32(p + k * 4) for k in range(12)]
        n = h[2]
        p += 0x30 + h[0] * 4
        if h[3] != 1:
            p += n * 8
        if h[4]:
            p += n * 4
        p += n * 4
        if h[8]:
            p += h[8] * 4
        for j in range(n):
            if h[4]:
                v = h[4]
                p += v * 8 if j == 0 else ((v + 1) * 2 if v & 1 else v * 2)
            if h[8] == 0:
                p += h[6] * 24
        if h[8]:
            p += h[8] * h[6] * 16
    sec["B_count"] = nBn
    if F & 0x40000:
        k = u32(p) & 0xFFFF; p += 4 + k * 0xC00
    # --- betikler
    ns = u32(p); p += 4
    sec["script_off"] = p
    sec["n_scripts"] = ns
    for _ in range(ns):
        p += 4 + u32(p) * 4
    sec["script_end"] = p
    # --- C: statik mesh şablonları (önce nC adet 0x68 başlık, sonra veri blokları)
    nC = u32(p); p += 4
    H = p
    p += nC * 0x68
    models = []
    for i in range(nC):
        h = H + i * 0x68
        n1, nB = u32(h + 0x48), u32(h + 0x54)
        c = (u16(h + 0x5C), u16(h + 0x5E), u16(h + 0x60))
        verts = np.frombuffer(b, "<i2", n1 * 4, p).reshape(n1, 4); p += n1 * 8
        faces = np.frombuffer(b, "<u2", nB * 6, p).reshape(nB, 6).copy(); p += nB * 12
        nprim = sum(c)
        prims = np.frombuffer(b, "u1", nprim * 32, p).reshape(nprim, 32); p += nprim * 32
        bbox = np.frombuffer(b, "<i2", 32, h + 8).reshape(8, 4)[:, :3]
        models.append({"verts": verts, "faces": faces, "prims": prims, "pcount": c, "bbox": bbox,
                       "hdr": h})
    sec["models"] = models
    if F & 4:
        p += 4
    if F & 0x10:
        p += 4
    # --- dünya
    if u32(p) == 0:
        sec["instances"] = []
        sec["end"] = p
        return sec
    sec["n_world"] = u32(p); p += 4
    s2 = u32(p)
    list_off = p + 4
    s6 = list_off + s2 * 4
    W = [u32(s6 + k * 4) for k in range(0x26)]
    n0, c = W[0], W[3]
    sec["world_list"] = (list_off, s2)
    sec["world_hdr"] = s6
    p = s6 + 0x98 + c * 4 + n0 * 8
    if F & 0x1000:
        p += 0x100
        p += 4 + u32(p) * 4
    else:
        p += n0 * 8
    if u32(p) == 0x777666:
        p += 4 + ((W[4] * W[5]) >> 1) * 4
    inst_off = p
    p += n0 * 24
    idx_off = p
    p += n0 * 4
    inst = []
    for i in range(n0):
        rx, ry, rz = struct.unpack_from("<3h", b, inst_off + i * 24)
        x, y, z = struct.unpack_from("<3i", b, inst_off + i * 24 + 8)
        inst.append({"rot": (rx, ry, rz), "pos": (x, y, z), "model": u32(idx_off + i * 4)})
    sec["instances"] = inst
    sec["world_words"] = W
    n1a = W[6] >> 16
    p += (W[6] & 0xFFFF) * 0x54 + W[8] * 36 + (W[1] & 0xFFFF) * 64
    if not F & 0x800000:
        p += n0 * 64
    if F & 0x10000:
        sec["x50_off"] = p
        p += n1a * 24
    p += 4 + u32(p) * 32  # 32 baytlık kayıt tablosu (çoğu seviyede boş)
    if F & 0x8000:
        cnt_off = p
        nc = n0 + (n1a if F & 0x10000000 else 0)
        p += nc * 4
        for i in range(n0):
            cnt = u32(cnt_off + i * 4)
            if cnt:
                p += models[inst[i]["model"]]["verts"].shape[0] * cnt * 4
        if F & 0x10000000:
            for j in range(n1a):
                cnt = u32(cnt_off + (n0 + j) * 4)
                if cnt:
                    p += models[u32(sec["x50_off"] + j * 24 + 0x10)]["verts"].shape[0] * cnt * 4
    if F & 8:
        for _ in range(2):
            p += n0 * 4
            for i in range(n0):
                p += len(models[inst[i]["model"]]["faces"]) * 52
    sec["end_of_lists"] = p
    return sec


# ---------------------------------------------------------------- mesh kurma
def rot_matrix(rx, ry, rz):
    """PS1 açı birimi: 4096 = 360°. Y dönüşü: x' = c*x + s*z, z' = -s*x + c*z (libgte RotMatrix)."""
    f = 2 * math.pi / 4096
    cx, sx, cy, sy, cz, sz = math.cos(rx * f), math.sin(rx * f), math.cos(ry * f), math.sin(ry * f), \
        math.cos(rz * f), math.sin(rz * f)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def build_mesh(sec):
    """Dünya uzayında üçgen mesh: V (N,3) float, T (M,3) int, meta (M,) = (örnek, model, yüz, bayrak)."""
    V, T, meta = [], [], []
    base = 0
    for ii, ins in enumerate(sec["instances"]):
        m = sec["models"][ins["model"]]
        R = rot_matrix(*ins["rot"])
        v = m["verts"][:, :3].astype(np.float64) @ R.T + np.array(ins["pos"], dtype=np.float64)
        V.append(v)
        for fi, f in enumerate(m["faces"]):
            a, bb, c_, d, _, fl = (int(x) for x in f)
            if fl & 0x800:  # dörtlü: z-sırası köşeler (0,1,2,3) -> (0,1,2),(1,3,2)
                T.append((base + a, base + bb, base + c_)); meta.append((ii, ins["model"], fi, fl))
                T.append((base + bb, base + d, base + c_)); meta.append((ii, ins["model"], fi, fl))
            else:
                T.append((base + a, base + bb, base + c_)); meta.append((ii, ins["model"], fi, fl))
        base += len(v)
    return np.concatenate(V), np.array(T, dtype=np.int64), meta


def write_obj(path, V, T, meta):
    with open(path, "w") as f:
        f.write(f"# HP2 seviye mesh: {len(V)} köşe, {len(T)} üçgen (y YUKARI (zemin y=1024), 4096 = 1 karo)\n")
        for v in V:
            f.write("v %.1f %.1f %.1f\n" % tuple(v))
        last = None
        for t, mt in zip(T, meta):
            if mt[:2] != last:
                f.write(f"g inst{mt[0]}_model{mt[1]}\n")
                last = mt[:2]
            f.write("f %d %d %d\n" % (t[0] + 1, t[1] + 1, t[2] + 1))


# ---------------------------------------------------------------- ortografik rasterizer (numpy+PIL)
def view_matrix(yaw, tilt):
    """Y YUKARI. tilt=90 üstten (ekran=(x,z)), tilt=0 önden (ekran=(x,-y)); yaw dünya Y ekseni etrafında (derece)."""
    a, t = math.radians(yaw), math.radians(tilt)
    Ry = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
    Mt = np.array([[1, 0, 0], [0, -math.cos(t), math.sin(t)], [0, math.sin(t), math.cos(t)]])
    return Mt @ Ry


def render(V, T, meta, M, size, path):
    """M: görünüm matrisi (satırlar = ekran x, ekran y, derinlik; büyük derinlik = yakın). Z-tamponlu, düz gölgeli."""
    from PIL import Image

    P = V @ M.T
    lo, hi = P[:, :2].min(0), P[:, :2].max(0)
    sc = (size - 20) / max(hi - lo)
    S = (P[:, :2] - lo) * sc + 10
    h = int((hi[1] - lo[1]) * sc) + 20
    img = np.full((h, size, 3), 20, np.uint8)
    zb = np.full((h, size), -1e18)
    tri = V[T]
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    nl = np.linalg.norm(nrm, axis=1) + 1e-9
    nrm /= nl[:, None]
    light = np.array([0.4, -0.8, 0.45]); light /= np.linalg.norm(light)
    shade = 0.35 + 0.65 * np.abs(nrm @ light)
    palette = np.array([[(i * 67) % 160 + 70, (i * 131) % 150 + 80, (i * 29) % 140 + 90] for i in range(256)])
    for k, t in enumerate(T):
        p = S[t]
        d = P[t, 2]
        x0, x1 = int(max(p[:, 0].min(), 0)), int(min(p[:, 0].max(), size - 1))
        y0, y1 = int(max(p[:, 1].min(), 0)), int(min(p[:, 1].max(), h - 1))
        if x1 < x0 or y1 < y0:
            continue
        (ax, ay), (bx, by), (cx, cy) = p
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-9:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
        l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
        l3 = 1 - l1 - l2
        m = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
        z = l1 * d[0] + l2 * d[1] + l3 * d[2]
        sub = zb[y0 : y1 + 1, x0 : x1 + 1]
        up = m & (z > sub)
        sub[up] = z[up]
        col = (palette[meta[k][1] % 256] * shade[k]).astype(np.uint8)
        img[y0 : y1 + 1, x0 : x1 + 1][up] = col
    Image.fromarray(img).save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wad")
    ap.add_argument("--out", default=str(ROOT / "build_assets" / "levels"))
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--clip-y", type=float, default=None,
                    help="cut.png için: tüm köşeleri y > değer olan üçgenleri at (çatı/tavanı kaldırır)")
    a = ap.parse_args()
    data = Path(a.wad).read_bytes()
    sec = parse_dpsx(chunk(data, "DPSX"))
    V, T, meta = build_mesh(sec)
    out = Path(a.out) / Path(a.wad).stem
    out.mkdir(parents=True, exist_ok=True)
    write_obj(out / "mesh.obj", V, T, meta)
    print(f"{Path(a.wad).name}: flags={sec['flags']:#x} modeller={len(sec['models'])} "
          f"örnek={len(sec['instances'])} köşe={len(V)} üçgen={len(T)} "
          f"(dörtlü={sum(1 for m in meta if m[3] & 0x800) // 2})")
    if a.render:
        for name, (yaw, tilt) in {"top": (0, 90), "front": (0, 0), "iso": (35, 50)}.items():
            render(V, T, meta, view_matrix(yaw, tilt), 1400, out / f"{name}.png")
        if a.clip_y is not None:
            keep = (V[T][:, :, 1] <= a.clip_y).any(1)
            render(V, T[keep], [m for m, k in zip(meta, keep) if k], view_matrix(25, 60), 1400, out / "cut.png")



if __name__ == "__main__":
    sys.exit(main())
