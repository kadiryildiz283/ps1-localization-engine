#include "tpsx.h"
#include <stdlib.h>
#include <string.h>

static inline uint32_t u32(const uint8_t *b, uint32_t o) {
    return (uint32_t)b[o] | ((uint32_t)b[o+1] << 8) |
           ((uint32_t)b[o+2] << 16) | ((uint32_t)b[o+3] << 24);
}
static inline uint16_t u16(const uint8_t *b, uint32_t o) {
    return (uint16_t)b[o] | ((uint16_t)b[o+1] << 8);
}
static inline int16_t s16(const uint8_t *b, uint32_t o) {
    return (int16_t)u16(b, o);
}

static uint32_t ps1_to_rgba(uint16_t c) {
    if (c == 0) return 0x00000000u;
    uint8_t r = (uint8_t)((c & 31) << 3 | (c & 31) >> 2);
    uint8_t g = (uint8_t)(((c >> 5) & 31) << 3 | ((c >> 5) & 31) >> 2);
    uint8_t b = (uint8_t)(((c >> 10) & 31) << 3 | ((c >> 10) & 31) >> 2);
    return 0xFF000000u | ((uint32_t)b << 16) | ((uint32_t)g << 8) | r;
}

typedef struct {
    uint8_t umin, vmin, w, h;
    uint16_t tp, clut;
    int ax, ay;
} AtlasCache;

int tpsx_load(const uint8_t *p, uint32_t size, TpsxBank *out) {
    memset(out, 0, sizeof(*out));
    if (size < 16) return -1;

    uint32_t flags = u32(p, 0);
    uint32_t q = 4;
    if (flags & 0x14) {
        uint32_t nlen = (flags & 4) ? 0x20 : 0x40;
        if (q + nlen + 4 + 0x800 > size) return -1;
        memcpy(out->map_name, p + q, nlen < 63 ? nlen : 63);
        out->map_name[63] = 0;
        q += nlen + 4 + 0x800;
    }
    if (q + 8 > size) return -1;
    uint32_t nrec = u32(p, q);
    uint32_t npg = u32(p, q + 4);
    q += 8;
    if (q + nrec * 12 + 8 > size) return -1;
    const uint8_t *recs = p + q;
    q += nrec * 12;
    uint32_t na = u32(p, q);
    q += 8 + na * 4;
    if (flags & 8) q += 5 * 0xC00;
    if (q > size) return -1;

    if (npg > 4) npg = 4;
    uint32_t nhw = npg * 65536;
    uint16_t *pages = calloc(4 * 65536, sizeof(uint16_t));
    if (flags & 2) {
        uint32_t k = 0;
        while (k < nhw && q + 2 <= size) {
            int16_t v = s16(p, q); q += 2;
            if (v >= 0) {
                uint32_t m = (uint32_t)v;
                if (k + m > nhw) m = nhw - k;
                if (q + m * 2 > size) break;
                memcpy(pages + k, p + q, m * 2);
                q += (uint32_t)v * 2;
                k += (uint32_t)v;
            } else {
                uint32_t cnt = (uint32_t)(-v);
                if (q + 2 > size) break;
                uint16_t val = u16(p, q); q += 2;
                for (uint32_t i = 0; i < cnt && k + i < nhw; i++) pages[k + i] = val;
                k += cnt;
            }
        }
    } else if (q + nhw * 2 <= size) {
        memcpy(pages, p + q, nhw * 2);
    }

    /* 1024x512 VRAM'e yerleştir */
    uint16_t *vram = calloc(1024 * 512, sizeof(uint16_t));
    static const int sx[4] = {512, 512, 768, 768};
    static const int sy[4] = {0, 256, 0, 256};
    for (uint32_t i = 0; i < npg; i++) {
        for (int y = 0; y < 256; y++) {
            memcpy(vram + (sy[i] + y) * 1024 + sx[i], pages + i * 65536 + y * 256, 256 * 2);
        }
    }
    free(pages);

    out->nrec = nrec;
    out->uvs = calloc(nrec ? nrec : 1, sizeof(TpsxUv));
    out->atlas_rgba = calloc((size_t)TPSX_ATLAS_SIZE * TPSX_ATLAS_SIZE * 4, 1);
    uint32_t *atlas = (uint32_t *)out->atlas_rgba;
    /* 0,0 pikseli beyaz olsun (dokusuz yüzler için) */
    for (int y = 0; y < 4; y++)
        for (int x = 0; x < 4; x++)
            atlas[y * TPSX_ATLAS_SIZE + x] = 0xFFFFFFFFu;

    AtlasCache *cache = calloc(nrec ? nrec : 1, sizeof(AtlasCache));
    uint32_t n_cache = 0;
    int pen_x = 8, pen_y = 0, row_h = 8;

    for (uint32_t i = 0; i < nrec; i++) {
        const uint8_t *r = recs + i * 12;
        uint8_t u0 = r[0], v0 = r[1];
        uint16_t clut = u16(r, 2);
        uint8_t u1 = r[4], v1 = r[5];
        uint16_t tp = u16(r, 6);
        uint8_t u2 = r[8], v2 = r[9], u3 = r[10], v3 = r[11];

        if ((u0|v0|clut|u1|v1|tp|u2|v2|u3|v3) == 0) continue;
        uint8_t mode = (tp >> 7) & 3;
        if (mode == 3) continue;

        uint8_t us[4] = {u0, u1, u2, u3};
        uint8_t vs[4] = {v0, v1, v2, v3};
        uint8_t umin = us[0], umax = us[0], vmin = vs[0], vmax = vs[0];
        for (int k = 1; k < 4; k++) {
            if (us[k] < umin) umin = us[k];
            if (us[k] > umax) umax = us[k];
            if (vs[k] < vmin) vmin = vs[k];
            if (vs[k] > vmax) vmax = vs[k];
        }
        int w = (int)umax - (int)umin + 1;
        int h = (int)vmax - (int)vmin + 1;

        int ax = -1, ay = -1;
        for (uint32_t c = 0; c < n_cache; c++) {
            if (cache[c].umin == umin && cache[c].vmin == vmin &&
                cache[c].w == w && cache[c].h == h &&
                cache[c].tp == tp && cache[c].clut == clut) {
                ax = cache[c].ax; ay = cache[c].ay; break;
            }
        }

        if (ax < 0) {
            if (pen_x + w + 2 > TPSX_ATLAS_SIZE) {
                pen_x = 0;
                pen_y += row_h + 2;
                row_h = 0;
            }
            if (pen_y + h + 2 > TPSX_ATLAS_SIZE) continue;
            ax = pen_x; ay = pen_y;
            pen_x += w + 2;
            if (h > row_h) row_h = h;

            int tx = (tp & 15) * 64;
            int ty = ((tp >> 4) & 1) * 256;
            int cx = (clut & 0x3F) * 16;
            int cy = (clut >> 6) & 0x1FF;

            for (int dy = 0; dy < h; dy++) {
                int vy = (ty + vmin + dy) & 511;
                for (int dx = 0; dx < w; dx++) {
                    int u = umin + dx;
                    uint16_t px16 = 0;
                    if (mode == 2) {
                        px16 = vram[vy * 1024 + ((tx + u) & 1023)];
                    } else if (mode == 0) {
                        uint16_t wd = vram[vy * 1024 + ((tx + (u >> 2)) & 1023)];
                        uint8_t idx = (wd >> ((u & 3) * 4)) & 15;
                        px16 = vram[cy * 1024 + ((cx + idx) & 1023)];
                    } else {
                        uint16_t wd = vram[vy * 1024 + ((tx + (u >> 1)) & 1023)];
                        uint8_t idx = (wd >> ((u & 1) * 8)) & 255;
                        px16 = vram[cy * 1024 + ((cx + idx) & 1023)];
                    }
                    atlas[(ay + dy) * TPSX_ATLAS_SIZE + (ax + dx)] = ps1_to_rgba(px16);
                }
            }
            cache[n_cache++] = (AtlasCache){umin, vmin, (uint8_t)w, (uint8_t)h, tp, clut, ax, ay};
        }

        for (int k = 0; k < 4; k++) {
            out->uvs[i].u[k] = (ax + (us[k] - umin) + 0.5f) / (float)TPSX_ATLAS_SIZE;
            out->uvs[i].v[k] = (ay + (vs[k] - vmin) + 0.5f) / (float)TPSX_ATLAS_SIZE;
        }
        out->uvs[i].valid = 1;
    }

    free(cache);
    free(vram);
    return 0;
}

void tpsx_free(TpsxBank *tb) {
    free(tb->uvs);
    free(tb->atlas_rgba);
    memset(tb, 0, sizeof(*tb));
}
