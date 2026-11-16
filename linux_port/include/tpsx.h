#ifndef HP2_TPSX_H
#define HP2_TPSX_H

#include <stdint.h>

#define TPSX_ATLAS_SIZE 2048

typedef struct {
    float u[4];
    float v[4];
    uint8_t valid;
} TpsxUv;

typedef struct {
    TpsxUv *uvs;
    uint32_t nrec;
    uint8_t *atlas_rgba; /* TPSX_ATLAS_SIZE * TPSX_ATLAS_SIZE * 4 */
    char map_name[64];
} TpsxBank;

int tpsx_load(const uint8_t *buf, uint32_t size, TpsxBank *out);
void tpsx_free(TpsxBank *tb);

#endif
