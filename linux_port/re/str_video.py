#!/usr/bin/env python3
"""EA.STR (PS1 STR, BS v2) -> PNG. Saf Python + numpy MDEC çözücüsü.

Kullanım:
  python re/str_video.py [--raw dump/disc/EA.STR.raw2352] [--out build_assets/video]
                         [--first 30] [--all]
Format notları: docs/formats/STR_VIDEO.md
"""
import argparse
import os
import struct
import sys

import numpy as np

SECTOR = 2352
SYNC = b"\x00" + b"\xff" * 10 + b"\x00"
STR_MAGIC = 0x80010160
HDR = 32  # sektör-içi STR video başlığı; veri 2048-32 = 2016 bayt/sektör

# PS1 varsayılan luma/chroma kuantizasyon matrisi (zigzag sırası DEĞİL, raster)
QT = np.array([
    2, 16, 19, 22, 26, 27, 29, 34,
    16, 16, 22, 24, 27, 29, 34, 37,
    19, 22, 26, 27, 29, 34, 34, 38,
    22, 22, 26, 27, 29, 34, 37, 40,
    22, 26, 27, 29, 32, 35, 40, 48,
    26, 27, 29, 32, 35, 40, 48, 58,
    26, 27, 29, 34, 38, 46, 56, 69,
    27, 29, 35, 38, 46, 56, 69, 83], dtype=np.int64)

# zigzag[raster_index] = akış sırası (psx-spx); zagzig = tersi
_ZIGZAG = [0, 1, 5, 6, 14, 15, 27, 28, 2, 4, 7, 13, 16, 26, 29, 42,
           3, 8, 12, 17, 25, 30, 41, 43, 9, 11, 18, 24, 31, 40, 44, 53,
           10, 19, 23, 32, 39, 45, 52, 54, 20, 22, 33, 38, 46, 51, 55, 60,
           21, 34, 37, 47, 50, 56, 59, 61, 35, 36, 48, 49, 57, 58, 62, 63]
ZAGZIG = [0] * 64
for _r, _k in enumerate(_ZIGZAG):
    ZAGZIG[_k] = _r

# AC Huffman (BS v1/v2/v3): (önek, indeks_biti, [MDEC değerleri]) ; sonuna işaret biti 's'
_AC_ROWS = [
    ("11", 0, [0x0001]),
    ("011", 0, [0x0401]),
    ("010", 1, [0x0002, 0x0801]),
    ("0011", 1, [0x1001, 0x0C01]),
    ("00101", 0, [0x0003]),
    ("00100", 3, [0x3401, 0x0006, 0x3001, 0x2C01, 0x0C02, 0x0403, 0x0005, 0x2801]),
    ("0001", 2, [0x1C01, 0x1801, 0x0402, 0x1401]),
    ("00001", 2, [0x0802, 0x2401, 0x0004, 0x2001]),
    ("0000001", 3, [0x4001, 0x1402, 0x0007, 0x0803, 0x0404, 0x3C01, 0x3801, 0x1002]),
    ("00000001", 4, [0x000B, 0x2002, 0x1003, 0x000A, 0x0804, 0x1C02, 0x5401, 0x5001,
                     0x0009, 0x4C01, 0x4801, 0x0405, 0x0C03, 0x0008, 0x1802, 0x4401]),
    ("000000001", 4, [0x2802, 0x2402, 0x1403, 0x0C04, 0x0805, 0x0407, 0x0406, 0x000F,
                      0x000E, 0x000D, 0x000C, 0x6801, 0x6401, 0x6001, 0x5C01, 0x5801]),
    ("0000000001", 4, [0x001F, 0x001E, 0x001D, 0x001C, 0x001B, 0x001A, 0x0019, 0x0018,
                       0x0017, 0x0016, 0x0015, 0x0014, 0x0013, 0x0012, 0x0011, 0x0010]),
    ("00000000001", 4, [0x0028, 0x0027, 0x0026, 0x0025, 0x0024, 0x0023, 0x0022, 0x0021,
                        0x0020, 0x040E, 0x040D, 0x040C, 0x040B, 0x040A, 0x0409, 0x0408]),
    ("000000000001", 4, [0x0412, 0x0411, 0x0410, 0x040F, 0x1803, 0x4002, 0x3C02, 0x3802,
                         0x3402, 0x3002, 0x2C02, 0x7C01, 0x7801, 0x7401, 0x7001, 0x6C01]),
]
AC = {}  # kod bit dizgisi (işaret hariç) -> MDEC değeri
for _p, _n, _vals in _AC_ROWS:
    for _i, _v in enumerate(_vals):
        AC[_p + (format(_i, "0%db" % _n) if _n else "")] = _v
AC["10"] = 0xFE00  # EOB
MAXLEN = max(len(k) for k in AC)


def _idct_matrix():
    m = np.zeros((8, 8))
    for u in range(8):
        for x in range(8):
            m[u, x] = (np.sqrt(0.5) if u == 0 else 1.0) / 2 * np.cos((2 * x + 1) * u * np.pi / 16)
    return m


M = _idct_matrix()


# ---------------------------------------------------------------- sektör/frame
def read_sectors(path):
    d = open(path, "rb").read()
    assert len(d) % SECTOR == 0
    return d, len(d) // SECTOR


def classify(d, n):
    """Her sektör için ('video'|'audio'|'empty', alanlar)."""
    out = []
    for i in range(n):
        s = d[i * SECTOR:(i + 1) * SECTOR]
        assert s[:12] == SYNC, "sektör %d senkron yok" % i
        sm = s[18]
        if sm & 0x04:
            out.append(("audio", s))
        elif sm & 0x08 and struct.unpack_from("<I", s, 24)[0] == STR_MAGIC:
            out.append(("video", s))
        else:
            out.append(("empty", s))
    return out


def assemble_frames(sectors):
    """frame_no -> dict(chunks_total, w, h, demux_size, data(bytes), missing[list])."""
    frames = {}
    for kind, s in sectors:
        if kind != "video":
            continue
        (_, chunk, nchunks, fno, dsize, w, h) = struct.unpack_from("<IHHIIHH", s, 24)
        f = frames.setdefault(fno, dict(n=nchunks, w=w, h=h, size=dsize, parts={}))
        f["parts"][chunk] = s[24 + HDR:24 + 2048]
    for f in frames.values():
        f["missing"] = [c for c in range(f["n"]) if c not in f["parts"]]
        f["data"] = b"".join(f["parts"].get(c, b"\0" * 2016) for c in range(f["n"]))[:f["size"]]
    return frames


# ---------------------------------------------------------------- MDEC (BS v2)
def _signed10(v):
    return v - 1024 if v & 0x200 else v


def decode_bitstream(data, w, h):
    """BS v2 -> (bloklar[N,8,8] float, ok, kullanılan_bit). Blok sırası: MB sütun-öncelikli,
    MB içi Cr,Cb,Y1,Y2,Y3,Y4."""
    mdec_cnt, magic, qscale, version = struct.unpack_from("<HHHH", data, 0)
    assert magic == 0x3800 and version == 2, (hex(magic), version)
    body = data[8:]
    if len(body) % 2:
        body += b"\0"
    bits = "".join(format(int.from_bytes(body[i:i + 2], "little"), "016b")
                   for i in range(0, len(body), 2))
    nblk = ((w + 15) // 16) * ((h + 15) // 16) * 6
    blocks = np.zeros((nblk, 64), dtype=np.int64)
    pos = 0
    nbits = len(bits)
    for b in range(nblk):
        dc = _signed10(int(bits[pos:pos + 10], 2))
        pos += 10
        blk = blocks[b]
        blk[0] = max(-1024, min(1023, dc * int(QT[0])))
        k = 0
        while True:
            for L in range(2, MAXLEN + 1):
                v = AC.get(bits[pos:pos + L])
                if v is not None:
                    pos += L
                    break
            else:
                if bits[pos:pos + 6] == "000001":  # escape: 16 bit ham MDEC değeri
                    v = int(bits[pos + 6:pos + 22], 2)
                    pos += 22
                    sign = False
                    lvl = _signed10(v & 0x3FF)
                    run = v >> 10
                    k += run + 1
                    if k > 63:
                        break
                    blk[ZAGZIG[k]] = _dq(lvl, k, qscale)
                    continue
                return blocks.reshape(nblk, 8, 8).astype(np.float64), False, pos
            if v == 0xFE00:
                break
            sign = bits[pos] == "1"
            pos += 1
            lvl = -(v & 0x3FF) if sign else (v & 0x3FF)
            k += (v >> 10) + 1
            if k > 63:
                break
            blk[ZAGZIG[k]] = _dq(lvl, k, qscale)
        if pos > nbits:
            return blocks.reshape(nblk, 8, 8).astype(np.float64), False, pos
    # Frame sonu işareti: sonraki "Cr DC" yerinde 0111111111
    eof = bits[pos:pos + 10] == "0111111111"
    return blocks.reshape(nblk, 8, 8).astype(np.float64), eof, pos


def _dq(lvl, k, qs):
    v = lvl * int(QT[ZAGZIG[k]]) * qs  # QT raster indeksli, k zigzag sırası
    v = (abs(v) + 4) // 8 * (1 if v >= 0 else -1)
    return max(-1024, min(1023, v))


def blocks_to_rgb(blocks, w, h):
    """IDCT + YCbCr->RGB. blocks: (N,8,8) dequant edilmiş katsayılar."""
    pix = np.einsum("vy,nvu,ux->nyx", M, blocks, M)
    mbw, mbh = (w + 15) // 16, (h + 15) // 16
    pix = pix.reshape(mbw * mbh, 6, 8, 8)
    Y = np.zeros((mbh * 16, mbw * 16))
    Cr = np.zeros((mbh * 8, mbw * 8))
    Cb = np.zeros((mbh * 8, mbw * 8))
    for m in range(mbw * mbh):
        mx, my = m // mbh, m % mbh
        Cr[my * 8:my * 8 + 8, mx * 8:mx * 8 + 8] = pix[m, 0]
        Cb[my * 8:my * 8 + 8, mx * 8:mx * 8 + 8] = pix[m, 1]
        for j, (dy, dx) in enumerate(((0, 0), (0, 8), (8, 0), (8, 8))):
            Y[my * 16 + dy:my * 16 + dy + 8, mx * 16 + dx:mx * 16 + dx + 8] = pix[m, 2 + j]
    Cr = Cr.repeat(2, 0).repeat(2, 1)
    Cb = Cb.repeat(2, 0).repeat(2, 1)
    rgb = np.stack([Y + 1.402 * Cr, Y - 0.3437 * Cb - 0.7143 * Cr, Y + 1.772 * Cb], -1) + 128
    return np.clip(np.rint(rgb), 0, 255).astype(np.uint8)[:h, :w]


def decode_frame(f):
    blocks, ok, used = decode_bitstream(f["data"], f["w"], f["h"])
    return blocks_to_rgb(blocks, f["w"], f["h"]), ok, used


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=os.path.join(root, "dump/disc/EA.STR.raw2352"))
    ap.add_argument("--out", default=os.path.join(root, "build_assets/video"))
    ap.add_argument("--first", type=int, default=30)
    ap.add_argument("--all", action="store_true", help="tüm kareleri yaz")
    a = ap.parse_args()

    from PIL import Image
    d, n = read_sectors(a.raw)
    secs = classify(d, n)
    kinds = [k for k, _ in secs]
    frames = assemble_frames(secs)
    print("sektör: %d  video: %d  ses: %d  boş: %d" % (
        n, kinds.count("video"), kinds.count("audio"), kinds.count("empty")))
    nos = sorted(frames)
    f0 = frames[nos[0]]
    print("frame: %d (no %d..%d)  çözünürlük %dx%d  eksik-chunk'lı frame: %d" % (
        len(nos), nos[0], nos[-1], f0["w"], f0["h"], sum(1 for f in frames.values() if f["missing"])))
    os.makedirs(a.out, exist_ok=True)
    good = 0
    for i, no in enumerate(nos):
        rgb, ok, used = decode_frame(frames[no])
        good += ok
        want = a.all or i < a.first or no == nos[-1]
        if want:
            Image.fromarray(rgb).save(os.path.join(a.out, "EA_frame_%04d.png" % no))
        print("frame %3d: bit %6d/%6d  EOF-işareti=%s%s" % (
            no, used, frames[no]["size"] * 8, ok, "  [PNG]" if want else ""))
    print("ÇÖZÜLEN: %d/%d (EOF işareti doğrulanan: %d)" % (len(nos), len(nos), good))


if __name__ == "__main__":
    sys.exit(main())
