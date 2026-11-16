#include "lpsx.h"
#include <stdlib.h>
#include <string.h>

static inline uint32_t u32(const uint8_t *b, uint32_t o) {
    return (uint32_t)b[o] | ((uint32_t)b[o+1] << 8) |
           ((uint32_t)b[o+2] << 16) | ((uint32_t)b[o+3] << 24);
}
static inline uint16_t u16(const uint8_t *b, uint32_t o) {
    return (uint16_t)b[o] | ((uint16_t)b[o+1] << 8);
}

static char *decode_str(const uint8_t *pool, uint32_t pool_len, uint32_t off) {
    if (off >= pool_len) return strdup("");
    uint32_t cur = off, cap = 64, len = 0;
    char *out = malloc(cap);
    while (cur + 2 <= pool_len) {
        uint16_t v = u16(pool, cur);
        cur += 2;
        if (v == 0) break;
        if (len + 4 >= cap) { cap *= 2; out = realloc(out, cap); }
        if (v >= 0x60 && v <= 0x79) out[len++] = (char)(v + 1);
        else if (v >= 32 && v < 127) out[len++] = (char)v;
        else out[len++] = ' ';
    }
    out[len] = 0;
    return out;
}

int lpsx_load(const uint8_t *buf, uint32_t size, LpsxTable *out) {
    memset(out, 0, sizeof(*out));
    if (size < 12) return 0;
    uint32_t n_rec = u32(buf, 4);
    if (n_rec == 0) return 0;
    uint32_t ptrs_bytes = n_rec * 4 * 4;
    if (12 + ptrs_bytes > size) return -1;

    const uint8_t *pool = buf + 12 + ptrs_bytes;
    uint32_t pool_len = size - (12 + ptrs_bytes);

    out->entries = calloc(n_rec, sizeof(LpsxEntry));
    out->count = n_rec;
    for (uint32_t i = 0; i < n_rec; i++) {
        uint32_t base = 12 + i * 16;
        out->entries[i].en = decode_str(pool, pool_len, u32(buf, base + 0));
        out->entries[i].fr = decode_str(pool, pool_len, u32(buf, base + 4));
        out->entries[i].de = decode_str(pool, pool_len, u32(buf, base + 8));
    }
    return 0;
}

void lpsx_free(LpsxTable *t) {
    for (uint32_t i = 0; i < t->count; i++) {
        free(t->entries[i].en);
        free(t->entries[i].fr);
        free(t->entries[i].de);
    }
    free(t->entries);
    memset(t, 0, sizeof(*t));
}
