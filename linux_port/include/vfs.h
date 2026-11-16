#ifndef HP2_VFS_H
#define HP2_VFS_H

#include <stdint.h>
#include <stddef.h>

/* POTTER.DIR / POTTER.DAT sanal dosya sistemi (diskten dökülmüş dump/disc altında). */
typedef struct {
    char name[13];
    uint32_t size;
    uint32_t offset;
} VfsEntry;

typedef struct {
    VfsEntry *entries;
    uint32_t count;
    char dat_path[1024];
} Vfs;

int vfs_open(Vfs *v, const char *disc_dir);
void vfs_close(Vfs *v);
const VfsEntry *vfs_find(const Vfs *v, const char *name);
/* Dosyanın tamamını malloc'lı belleğe okur; çağıran free eder. NULL = hata. */
uint8_t *vfs_read(const Vfs *v, const char *name, uint32_t *out_size);

/* WAD: [u32 toplam][ {tag[4] ters ASCII, u32 boyut, payload} ... ] */
typedef struct {
    char tag[5];       /* normalize edilmiş (ör. "TPSX") */
    uint32_t offset;   /* payload ofseti */
    uint32_t size;
} WadChunk;

int wad_chunks(const uint8_t *wad, uint32_t size, WadChunk *out, int max);

#endif
