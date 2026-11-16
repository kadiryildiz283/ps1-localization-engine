#include "vfs.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint32_t le32(const uint8_t *p) {
    return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
}

int vfs_open(Vfs *v, const char *disc_dir) {
    char path[1100];
    memset(v, 0, sizeof(*v));
    snprintf(path, sizeof(path), "%s/POTTER.DIR", disc_dir);
    snprintf(v->dat_path, sizeof(v->dat_path), "%s/POTTER.DAT", disc_dir);

    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); return -1; }
    uint8_t cnt[4];
    if (fread(cnt, 1, 4, f) != 4) { fclose(f); return -1; }
    v->count = le32(cnt);
    v->entries = calloc(v->count, sizeof(VfsEntry));
    for (uint32_t i = 0; i < v->count; i++) {
        uint8_t rec[20];
        if (fread(rec, 1, 20, f) != 20) { fclose(f); vfs_close(v); return -1; }
        memcpy(v->entries[i].name, rec, 12);
        v->entries[i].name[12] = 0;
        v->entries[i].size = le32(rec + 12);
        v->entries[i].offset = le32(rec + 16);
    }
    fclose(f);
    return 0;
}

void vfs_close(Vfs *v) {
    free(v->entries);
    memset(v, 0, sizeof(*v));
}

const VfsEntry *vfs_find(const Vfs *v, const char *name) {
    for (uint32_t i = 0; i < v->count; i++)
        if (strcmp(v->entries[i].name, name) == 0) return &v->entries[i];
    return NULL;
}

uint8_t *vfs_read(const Vfs *v, const char *name, uint32_t *out_size) {
    const VfsEntry *e = vfs_find(v, name);
    if (!e) return NULL;
    FILE *f = fopen(v->dat_path, "rb");
    if (!f) return NULL;
    uint8_t *buf = malloc(e->size ? e->size : 1);
    if (fseeko(f, e->offset, SEEK_SET) != 0 || fread(buf, 1, e->size, f) != e->size) {
        free(buf); fclose(f); return NULL;
    }
    fclose(f);
    if (out_size) *out_size = e->size;
    return buf;
}

int wad_chunks(const uint8_t *wad, uint32_t size, WadChunk *out, int max) {
    uint32_t pos = 4;
    int n = 0;
    while (pos + 8 <= size && n < max) {
        WadChunk *c = &out[n];
        for (int i = 0; i < 4; i++) c->tag[i] = (char)wad[pos + 3 - i];
        c->tag[4] = 0;
        c->size = le32(wad + pos + 4);
        c->offset = pos + 8;
        n++;
        if (c->offset + c->size > size) return -1;
        pos = c->offset + c->size;
        if (strcmp(c->tag, "END ") == 0) break;
    }
    return n;
}
