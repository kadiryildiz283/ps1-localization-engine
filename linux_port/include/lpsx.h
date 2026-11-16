#ifndef HP2_LPSX_H
#define HP2_LPSX_H

#include <stdint.h>

typedef struct {
    char *en;
    char *fr;
    char *de;
} LpsxEntry;

typedef struct {
    LpsxEntry *entries;
    uint32_t count;
} LpsxTable;

int lpsx_load(const uint8_t *buf, uint32_t size, LpsxTable *out);
void lpsx_free(LpsxTable *t);

#endif
