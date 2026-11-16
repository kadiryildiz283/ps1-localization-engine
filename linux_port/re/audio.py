#!/usr/bin/env python3
"""HP2 PS1: WAD SPSX ses bankalari + EA.STR XA-ADPCM -> 16-bit WAV (yalniz stdlib).

Kullanim:  python re/audio.py [--wad ADI ...] [--no-wad] [--no-xa] [--jobs N]
Cikti:     linux_port/build_assets/audio/{WAD/<wad>/<n>.wav + meta.json, XA/<ch>.wav + meta.json, index.json}
Format:    docs/formats/AUDIO.md  (idempotent: ayni girdi -> ayni cikti)
"""
import argparse
import array
import glob
import hashlib
import json
import math
import os
import shutil
import struct
import sys
import time
import wave
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POTTER = os.path.join(ROOT, "dump", "potter")
XA_RAW = os.path.join(ROOT, "dump", "disc", "EA.STR.raw2352")
OUT = os.path.join(ROOT, "build_assets", "audio")

assert sys.byteorder == "little"

# --- Sony ADPCM (SPU): 16 bayt = 1 shift/filtre + 1 bayrak + 14 veri = 28 ornek ---------------
K0 = (0, 60, 115, 98, 122)
K1 = (0, 0, -52, -55, -60)
NIB = [[(((n - 16) if n >= 8 else n) << 12) >> sh for n in range(16)] for sh in range(16)]
ZERO14 = bytes(14)


def decode_spu(buf):
    """SPU ADPCM -> array('h'). Donanim kurali: shift>12 => 9, filtre>4 => 4. Bayraklar cozumu etkilemez."""
    out = array.array("h")
    ext = out.extend
    s1 = s2 = 0
    for o in range(0, len(buf) - 15, 16):
        hdr = buf[o]
        filt = hdr >> 4
        if filt == 0 and buf[o + 2 : o + 16] == ZERO14:
            ext(bytes(56))  # filtre 0 + sifir veri: gecmisten bagimsiz 28 sifir
            s1 = s2 = 0
            continue
        sh = hdr & 15
        tab = NIB[9 if sh > 12 else sh]
        if filt > 4:
            filt = 4
        k0, k1 = K0[filt], K1[filt]
        blk = []
        ap = blk.append
        for b in buf[o + 2 : o + 16]:
            for n in (b & 15, b >> 4):  # once dusuk nibble
                s = tab[n] + ((k0 * s1 + k1 * s2 + 32) >> 6)
                s = 32767 if s > 32767 else -32768 if s < -32768 else s
                s2 = s1
                s1 = s
                ap(s)
        ext(blk)
    return out


def loop_info(buf):
    """(son blok bayragi, dongu baslangic ornegi). Bayrak: bit0=bitis, bit1=tekrar, bit2=dongu basi."""
    fl = buf[1::16]
    if not fl:
        return 0, 0
    st = next((i for i, f in enumerate(fl) if f & 4), None)
    return fl[-1], (st * 28 if st is not None else 0)


# --- XA-ADPCM (CD-ROM XA Form2, 4-bit): 18 grup x 128 bayt / sektor -------------------------
def decode_xa_group(g, st, stereo):
    """128 baytlik ses grubu -> (L[], R[]). Parametre bayti: birim u<4 -> g[u], u>=4 -> g[4+u]
    (g[0:4]==g[4:8] ve g[8:12]==g[12:16] kopya). st=[[l1,l2],[r1,r2]] gecmis (yerinde guncellenir)."""
    chans = ([], [])
    for u in range(8):
        hdr = g[u + 4 * (u >> 2)]
        sh = 12 - (hdr & 15)
        k0, k1 = K0[min((hdr >> 4) & 3, 3)], K1[min((hdr >> 4) & 3, 3)]
        c = (u & 1) if stereo else 0
        s1, s2 = st[c]
        dst = chans[c]
        for w in range(28):
            n = (g[16 + w * 4 + (u >> 1)] >> ((u & 1) * 4)) & 15
            if n >= 8:
                n -= 16
            s = ((n << sh) if sh >= 0 else (n >> -sh)) + ((k0 * s1 + k1 * s2 + 32) >> 6)
            s = 32767 if s > 32767 else -32768 if s < -32768 else s
            s2 = s1
            s1 = s
            dst.append(s)
        st[c][0], st[c][1] = s1, s2
    return chans


def extract_xa(raw_path, out_dir):
    """EA.STR.raw2352 -> XA/<ch>.wav (Form2 + audio bayragi 0x04 olan sektorler, (dosya,kanal) basina)."""
    d = open(raw_path, "rb").read()
    sync = b"\x00" + b"\xff" * 10 + b"\x00"
    streams, summary = {}, {}
    for i in range(len(d) // 2352):
        s = d[i * 2352 : (i + 1) * 2352]
        assert s[:12] == sync and s[16:20] == s[20:24]
        f, ch, sm, co = s[16:20]
        key = (sm, co, f, ch)
        summary[key] = summary.get(key, 0) + 1
        if sm & 0x04 and sm & 0x20:  # audio + Form2
            streams.setdefault((f, ch), []).append((i, s, co))
    shutil.rmtree(out_dir, ignore_errors=True)
    files = {f for f, _ in streams}
    meta = {
        "source": os.path.relpath(raw_path, ROOT),
        "sector_census": [
            {"submode": hex(k[0]), "coding": hex(k[1]), "file": k[2], "channel": k[3], "sectors": v}
            for k, v in sorted(summary.items())
        ],
        "streams": [],
    }
    for (f, ch), secs in sorted(streams.items()):
        codings = {c for _, _, c in secs}
        assert len(codings) == 1
        co = codings.pop()
        assert not co & 0x10, "8-bit XA desteklenmiyor"
        stereo = bool(co & 1)
        rate = 18900 if co & 4 else 37800
        st = [[0, 0], [0, 0]]
        pcm = array.array("h")
        for _, s, _ in secs:
            for k in range(18):
                l, r = decode_xa_group(s[24 + 128 * k : 24 + 128 * k + 128], st, stereo)
                if stereo:
                    inter = [0] * (2 * len(l))
                    inter[0::2] = l
                    inter[1::2] = r
                    pcm.extend(inter)
                else:
                    pcm.extend(l)
        name = f"{ch}.wav" if len(files) == 1 else f"{f}_{ch}.wav"
        write_wav(os.path.join(out_dir, name), pcm, rate, 2 if stereo else 1)
        ns = 2 if stereo else 1
        entry = {"file": name, "xa_file_number": f, "channel": ch, "coding": hex(co), "stereo": stereo,
                 "sample_rate": rate, "sectors": len(secs), "first_sector": secs[0][0], "last_sector": secs[-1][0],
                 "frames": len(pcm) // ns}
        entry.update(stats(pcm, rate, ns))
        if stereo:
            entry["left"] = stats(pcm[0::2], rate)
            entry["right"] = stats(pcm[1::2], rate)
        meta["streams"].append(entry)
    with open(os.path.join(out_dir, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    return meta


# --- WAV + istatistik --------------------------------------------------------------------
def write_wav(path, samples, rate, channels=1):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())


def stats(smp, rate, channels=1):
    """RMS (dBFS), tepe, sifir-gecis orani. Uzun seslerde 8 x 16384 ornekli pencere."""
    n = len(smp)
    if n == 0:
        return {"duration_s": 0.0, "rms_dbfs": None, "peak": 0, "zcr": 0.0}
    win = 16384
    segs = [smp] if n <= 8 * win else [smp[int(i * (n - win) / 7) :][:win] for i in range(8)]
    cnt = sum(len(s) for s in segs)
    ss = sum(x * x for s in segs for x in s)
    zc = sum(1 for s in segs for a, b in zip(s, s[1:]) if (a < 0) != (b < 0))
    zn = sum(len(s) - 1 for s in segs)
    rms = math.sqrt(ss / cnt)
    return {
        "duration_s": round(n / channels / rate, 4),
        "rms_dbfs": round(20 * math.log10(rms / 32768), 2) if rms else None,
        "peak": max(max(s) for s in segs),
        "zcr": round(zc / zn, 4) if zn else 0.0,
    }


def sr_raw_to_hz(sr):
    """Akis p2 alt yarisi (SPU pitch, 0x1000 = 44100 Hz) -> Hz; bilinen hizlara yapistir."""
    hz = 44100 * sr / 4096
    for r in (6000, 8000, 11025, 16000, 22050, 32000, 44100):
        if abs(hz - r) <= r * 0.005:
            return r
    return round(hz)


# --- WAD / SPSX ---------------------------------------------------------------------------
def walk_chunks(d):
    """[u32 toplam] + zincir [4B ters-ASCII tag][u32 boyut][payload]; 'END ' son."""
    pos, out = 4, []
    while pos + 8 <= len(d):
        tag = d[pos : pos + 4][::-1].decode("latin1")
        sz = struct.unpack_from("<I", d, pos + 4)[0]
        out.append((tag, pos, sz))
        if tag == "END ":
            return out
        pos += 8 + sz
        if pos > len(d):
            return None
    return None


def entries(P, off, n):
    """n adet 20B kayit: (rate_hz, pitch|vol<<16, flag, adsr, size)."""
    return [struct.unpack_from("<5I", P, off + 20 * i) for i in range(n)]


def valid_rec(r):
    rate, _pv, flag, adsr, size = r
    return (3000 <= rate <= 48000 and adsr in (0x42008F, 0x4200FF) and (flag & 0xFF) <= 1
            and 0 < size <= 0x400000 and size % 16 == 0)


def longest_run(P, lo, hi):
    """[lo,hi) icinde 4-hizali baslangiclardan en uzun ardisik gecerli 20B kayit dizisi."""
    best = (0, 0)
    for st in range(lo, hi - 19, 4):
        k = 0
        while st + 20 * (k + 1) <= hi and valid_rec(struct.unpack_from("<5I", P, st + 20 * k)):
            k += 1
        if k > best[1]:
            best = (st, k)
    return entries(P, best[0], best[1]) if best[1] else []


def parse_spsx(P):
    """SPSX yuku -> dict | None (akis tablosu yok). Duzen (T1L2M001'de bayt-duzeyi dogrulandi):
      0x00  u32 A (anlami bilinmiyor), u32 N1
      0x08  N1 x 20B kayit (banka #1)
      ...   banka #2 basligi + N2 x 20B kayit + N2 x 16B 'ff idx' satiri
      H     u32 M (akis sayisi), u32 B (akis tabani = ses bolgesi basindaki banka #2 boyutu)
      H+8   M x 16B (a_off, p2, p3, a_sz)   a_off[i+1] = a_off[i]+a_sz[i] (0x800'e yuvarlanabilir)
      H+8+16M  u32 S1 (= banka #1 bayt toplami), S1 bayt ADPCM
    Akis verisi: ses_bolgesi[B + a_off : +a_sz]; ses_bolgesi[0:B] = banka #2.
    """
    a, n1 = struct.unpack_from("<II", P, 0)
    if n1 > 4000:
        return None
    ent1 = entries(P, 8, n1)
    s1 = sum(e[4] for e in ent1)
    e1 = 8 + 20 * n1
    for h in range(e1, len(P) - 8, 4):
        m, b = struct.unpack_from("<II", P, h)
        if not (1 <= m <= 4000 and b % 0x800 == 0 and b <= 0x400000):
            continue
        end = h + 8 + 16 * m
        if end + 4 > len(P) or struct.unpack_from("<I", P, end)[0] != s1 or end + 4 + s1 > len(P):
            continue
        st = [struct.unpack_from("<4I", P, h + 8 + 16 * i) for i in range(m)]
        pos = 0
        for e in st:
            if e[0] not in (pos, (pos + 0x7FF) & ~0x7FF):
                break
            pos = e[0] + e[3]
        else:
            return {"a": a, "ent1": ent1, "bank1": bytes(P[end + 4 : end + 4 + s1]), "stream_base": b,
                    "streams": st, "ent2": longest_run(P, e1, h), "hdr_off": h}
    return None


def parse_inline(P):
    """Akis tablosu olmayan SPSX (T0I0M999): ...N x 20B kayit, u32 0, u32 T, T bayt ADPCM = yuk sonu."""
    for h in range(0, len(P) - 8, 4):
        t = struct.unpack_from("<I", P, h + 4)[0]
        if h + 8 + t != len(P) or struct.unpack_from("<I", P, h)[0] != 0 or t == 0:
            continue
        for k in range(1, 64):
            if h - 20 * k < 0:
                break
            recs = entries(P, h - 20 * k, k)
            if sum(r[4] for r in recs) == t:
                return recs, bytes(P[h + 8 :])
    return None


def parse_mini(d):
    """FE3_SOND / FE5_THND: [u32 dosya boyutu][N x 20B kayit][ADPCM]. Kayit adsr=0x1FC0001F, flag=8."""
    if len(d) < 24 or struct.unpack_from("<I", d, 0)[0] != len(d):
        return None
    for n in range(1, 33):
        recs = entries(d, 4, n)
        if not all(3000 <= r[0] <= 48000 and r[4] % 16 == 0 and r[4] > 0 for r in recs):
            break
        s0, tot = 4 + 20 * n, sum(r[4] for r in recs)
        if s0 + tot <= len(d) and all(d[s0 + c - 15] & 1 for c in _cum(recs)):
            return recs, d[s0 : s0 + tot]
    return None


def _cum(recs):
    c, out = 0, []
    for r in recs:
        c += r[4]
        out.append(c)
    return out


def place(region, recs, align):
    """Kayit boyutlariyla ornekleri bolgeye yerlestir. Sonu bayrakli (bit0) blokta bitmiyorsa ve align
    verilmisse 0x800'e hizalanmis baslangic denenir (banka #2 alt-grup sinirlari). -> [(ofs,size,verified)]"""
    cur, out = 0, []
    for r in recs:
        sz = r[4]
        cands = (cur, (cur + 0x7FF) & ~0x7FF) if align else (cur,)
        for st in cands:
            if st + sz <= len(region) and region[st + sz - 15] & 1:
                ok = True
                break
        else:
            st, ok = cur, False
        out.append((st, sz, ok))
        cur = st + sz
    return out


def rec_fields(r):
    return {"rate_hz": r[0], "pitch_reg": hex(r[1] & 0xFFFF), "volume": (r[1] >> 16) & 0xFF,
            "rec_flag": hex(r[2]), "adsr": hex(r[3])}


def collect_wad(path):
    """WAD -> (meta-iskeleti, ornek listesi). Her ornek: dict(kind, index, data, rate, extra...)."""
    d = open(path, "rb").read()
    name = os.path.splitext(os.path.basename(path))[0]
    meta = {"wad": os.path.basename(path), "layout": None, "notes": []}
    items = []

    def add(kind, idx, region, ofs, size, rate, verified, extra):
        data = bytes(region[ofs : ofs + size])
        end_flag, loop_start = loop_info(data)
        it = {"kind": kind, "index": idx, "rate_hz": rate, "data": data,
              "src": {"region": kind if kind != "stream" else "stream", "offset": ofs, "bytes": len(data)},
              "end_flag": end_flag, "loop": end_flag == 3, "loop_start_sample": loop_start,
              "end_flag_verified": verified}
        it.update(extra)
        items.append(it)

    mini = parse_mini(d)
    if mini:
        recs, data = mini
        meta["layout"] = "mini"
        for i, (ofs, sz, ok) in enumerate(place(data, recs, False)):
            add("mini", i, data, ofs, sz, recs[i][0], ok, rec_fields(recs[i]))
        return name, meta, items
    ch = walk_chunks(d)
    if not ch:
        meta["layout"] = "none"
        meta["notes"].append("zincir cozulemedi (FE3_WIZC: 'CPRS' sikistirilmis, cozulmedi)")
        return name, meta, items
    sp = next((c for c in ch if c[0] == "SPSX"), None)
    if not sp:
        meta["layout"] = "none"
        return name, meta, items
    P = d[sp[1] + 8 : sp[1] + 8 + sp[2]]
    r = parse_spsx(P)
    if r is None:
        inl = parse_inline(P)
        if inl is None:
            meta["layout"] = "unparsed"
            return name, meta, items
        recs, data = inl
        meta["layout"] = "inline"
        for i, (ofs, sz, ok) in enumerate(place(data, recs, False)):
            add("bank", i, data, ofs, sz, recs[i][0], ok, rec_fields(recs[i]))
        return name, meta, items

    dne = next(c for c in ch if c[0] == "END ")[1]
    ab = ((dne + 8 + 2047) // 2048) * 2048  # END yuku sektor-hizali baslar
    audio = d[ab:]
    B = r["stream_base"]
    meta.update(layout="spsx", audio_base=ab, stream_base=B, spsx_header_offset=r["hdr_off"], spsx_A=r["a"])
    for i, (ofs, sz, ok) in enumerate(place(r["bank1"], r["ent1"], False)):
        add("bank", i, r["bank1"], ofs, sz, r["ent1"][i][0], ok, rec_fields(r["ent1"][i]))
    if B:
        head = audio[:B]
        for i, (ofs, sz, ok) in enumerate(place(head, r["ent2"], True)):
            add("head", i, head, ofs, sz, r["ent2"][i][0], ok, rec_fields(r["ent2"][i]))
    for i, (a_off, p2, p3, sz) in enumerate(r["streams"]):
        ofs = B + a_off
        sz = max(0, min(sz, len(audio) - ofs))
        ex = {"hw": (p2 >> 16) & 0xFFFF, "sr_raw": hex(p2 & 0xFFFF), "p3": p3}
        add("stream", i, audio, ofs, sz, sr_raw_to_hz(p2 & 0xFFFF), bool(sz >= 16 and audio[ofs + sz - 15] & 1), ex)
    return name, meta, items


# --- toplu uretim ---------------------------------------------------------------------------
def decode_job(job):
    key, data, rate, path = job
    pcm = decode_spu(data)
    write_wav(path, pcm, rate)
    s = stats(pcm, rate)
    s["samples"] = len(pcm)
    return key, s


def link_or_copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def run_wads(paths, jobs):
    t0 = time.time()
    wads = []
    for p in paths:
        name, meta, items = collect_wad(p)
        wads.append((name, meta, items))
    uniq, order = {}, []  # key -> (data, rate, canonical path)
    for name, meta, items in wads:
        wdir = os.path.join(OUT, "WAD", name)
        shutil.rmtree(wdir, ignore_errors=True)
        for n, it in enumerate(items):
            it["n"] = n
            it["file"] = f"{n}.wav"
            key = (hashlib.md5(it["data"]).hexdigest(), it["rate_hz"])
            it["_key"] = key
            it["_path"] = os.path.join(wdir, it["file"])
            if key not in uniq:
                uniq[key] = (it["data"], it["rate_hz"], it["_path"])
                order.append(key)
    todo = sorted(order, key=lambda k: -len(uniq[k][0]))
    jl = [(k, uniq[k][0], uniq[k][1], uniq[k][2]) for k in todo]
    res = {}
    with Pool(jobs) as pool:
        for key, s in pool.imap_unordered(decode_job, jl, chunksize=1):
            res[key] = s
    index = {"wads": {}, "totals": {}}
    for name, meta, items in wads:
        out_samples = []
        for it in items:
            if it["_path"] != uniq[it["_key"]][2]:
                link_or_copy(uniq[it["_key"]][2], it["_path"])
            s = res[it["_key"]]
            rec = {k: v for k, v in it.items() if k not in ("data", "_key", "_path")}
            rec.update(s)
            rec["silent"] = s["peak"] == 0
            out_samples.append(rec)
        kinds = {}
        for it in out_samples:
            kinds[it["kind"]] = kinds.get(it["kind"], 0) + 1
        meta.update(counts=kinds, total=len(out_samples), samples=out_samples)
        if items or meta["layout"] != "none":
            os.makedirs(os.path.join(OUT, "WAD", name), exist_ok=True)
            with open(os.path.join(OUT, "WAD", name, "meta.json"), "w") as fh:
                json.dump(meta, fh, indent=1)
        index["wads"][name] = {"layout": meta["layout"], "total": len(out_samples), **kinds,
                               "unverified_end_flag": sum(1 for s in out_samples if not s["end_flag_verified"])}
    index["totals"] = {"wads_with_audio": sum(1 for w in index["wads"].values() if w["total"]),
                       "sounds": sum(w["total"] for w in index["wads"].values()),
                       "unique_decodes": len(uniq), "seconds": round(time.time() - t0, 1)}
    return index


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wad", nargs="*", help="yalniz bu WAD adlari (orn. T1L2M001)")
    ap.add_argument("--no-wad", action="store_true")
    ap.add_argument("--no-xa", action="store_true")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    a = ap.parse_args()
    index_path = os.path.join(OUT, "index.json")
    index = json.load(open(index_path)) if os.path.exists(index_path) else {}
    if not a.no_wad:
        paths = sorted(glob.glob(os.path.join(POTTER, "*.WAD")))
        if a.wad:
            paths = [p for p in paths if os.path.splitext(os.path.basename(p))[0] in a.wad]
        idx = run_wads(paths, a.jobs)
        if a.wad:  # kismi kosu: mevcut indeksi birlestir
            w = index.get("wads", {})
            w.update(idx["wads"])
            idx = {"wads": w, "totals": {"wads_with_audio": sum(1 for v in w.values() if v["total"]),
                                         "sounds": sum(v["total"] for v in w.values()),
                                         "unique_decodes": idx["totals"]["unique_decodes"],
                                         "seconds": idx["totals"]["seconds"]}}
        index.update(idx)
    if not a.no_xa:
        m = extract_xa(XA_RAW, os.path.join(OUT, "XA"))
        index["xa"] = [{k: s[k] for k in ("file", "channel", "sample_rate", "sectors", "duration_s")}
                       for s in m["streams"]]
    os.makedirs(OUT, exist_ok=True)
    with open(index_path, "w") as fh:
        json.dump(index, fh, indent=1)
    print(json.dumps({"totals": index.get("totals"), "xa": index.get("xa")}, indent=1))


if __name__ == "__main__":
    main()
