#ifndef HP2_DPSX_H
#define HP2_DPSX_H

#include <stdint.h>
#include <stddef.h>
#include "tpsx.h"

typedef struct {
    float x, y, z;
    float nx, ny, nz;
    float u, v;
    float r, g, b;
} DpsxVertex;

typedef struct {
    DpsxVertex *verts;
    uint32_t vert_count;
    float min_x, min_y, min_z;
    float max_x, max_y, max_z;
    uint32_t model_count;
    uint32_t instance_count;
    uint32_t tri_count;
} DpsxLevel;

int dpsx_load(const uint8_t *buf, uint32_t size, const TpsxBank *tpsx, DpsxLevel *out);
void dpsx_free(DpsxLevel *lvl);

#endif
