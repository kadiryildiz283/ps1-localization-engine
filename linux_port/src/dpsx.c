#include "dpsx.h"
#include <math.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

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
static inline int32_t s32(const uint8_t *b, uint32_t o) {
    return (int32_t)u32(b, o);
}

typedef struct {
    const int16_t *verts; /* 4 int16 per vert */
    uint32_t n_verts;
    const uint16_t *faces; /* 6 uint16 per face */
    uint32_t n_faces;
} DpsxModel;

static void make_rot(int16_t rx, int16_t ry, int16_t rz, float R[3][3]) {
    const float f = (float)(2.0 * M_PI / 4096.0);
    float cx = cosf(rx * f), sx = sinf(rx * f);
    float cy = cosf(ry * f), sy = sinf(ry * f);
    float cz = cosf(rz * f), sz = sinf(rz * f);
    /* R = Rz * Ry * Rx */
    float RzRy[3][3] = {
        { cz * cy, -sz, cz * sy },
        { sz * cy,  cz, sz * sy },
        { -sy,       0, cy }
    };
    float Rx[3][3] = {
        { 1,  0,   0 },
        { 0, cx, -sx },
        { 0, sx,  cx }
    };
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            R[i][j] = RzRy[i][0] * Rx[0][j] + RzRy[i][1] * Rx[1][j] + RzRy[i][2] * Rx[2][j];
        }
    }
}

static void push_tri(DpsxLevel *lvl, uint32_t *cap,
                     const float p0[3], const float p1[3], const float p2[3],
                     const float uv0[2], const float uv1[2], const float uv2[2],
                     bool textured, uint32_t model_id) {
    if (lvl->vert_count + 3 > *cap) {
        *cap = (*cap == 0) ? 4096 : (*cap * 2);
        lvl->verts = realloc(lvl->verts, (*cap) * sizeof(DpsxVertex));
    }
    float ux = p1[0] - p0[0], uy = p1[1] - p0[1], uz = p1[2] - p0[2];
    float vx = p2[0] - p0[0], vy = p2[1] - p0[1], vz = p2[2] - p0[2];
    float nx = uy * vz - uz * vy;
    float ny = uz * vx - ux * vz;
    float nz = ux * vy - uy * vx;
    float nl = sqrtf(nx * nx + ny * ny + nz * nz);
    if (nl > 1e-6f) { nx /= nl; ny /= nl; nz /= nl; }
    else { nx = 0; ny = 1; nz = 0; }

    float r = textured ? 1.0f : (((model_id * 67) % 80 + 110) / 255.0f);
    float g = textured ? 1.0f : (((model_id * 131) % 80 + 110) / 255.0f);
    float bl = textured ? 1.0f : (((model_id * 29) % 80 + 110) / 255.0f);

    const float *pts[3] = { p0, p1, p2 };
    const float *uvs[3] = { uv0, uv1, uv2 };
    for (int k = 0; k < 3; k++) {
        DpsxVertex *dv = &lvl->verts[lvl->vert_count++];
        dv->x = pts[k][0]; dv->y = pts[k][1]; dv->z = pts[k][2];
        dv->nx = nx; dv->ny = ny; dv->nz = nz;
        dv->u = uvs[k][0]; dv->v = uvs[k][1];
        dv->r = r; dv->g = g; dv->b = bl;
        if (dv->x < lvl->min_x) lvl->min_x = dv->x;
        if (dv->y < lvl->min_y) lvl->min_y = dv->y;
        if (dv->z < lvl->min_z) lvl->min_z = dv->z;
        if (dv->x > lvl->max_x) lvl->max_x = dv->x;
        if (dv->y > lvl->max_y) lvl->max_y = dv->y;
        if (dv->z > lvl->max_z) lvl->max_z = dv->z;
    }
    lvl->tri_count++;
}

int dpsx_load(const uint8_t *b, uint32_t size, const TpsxBank *tpsx, DpsxLevel *out) {
    memset(out, 0, sizeof(*out));
    out->min_x = out->min_y = out->min_z = 1e30f;
    out->max_x = out->max_y = out->max_z = -1e30f;
    if (size < 0x810) return -1;

    uint32_t F = u32(b, 0);
    uint32_t p = 0x808;

    /* A: iskelet modelleri */
    if (p + 4 > size) return -1;
    uint32_t nA = u32(b, p); p += 4;
    for (uint32_t i = 0; i < nA; i++) {
        if (p + 0x68 > size) return -1;
        uint32_t n1 = u32(b, p + 0x48);
        uint32_t nB = u32(b, p + 0x54);
        uint32_t nP = (uint32_t)u16(b, p + 0x5C) + u16(b, p + 0x5E) + u16(b, p + 0x60);
        p += 0x68 + n1 * 16 + nB * 20 + nP * 32;
    }

    /* B: animasyon tabloları */
    if (p + 4 > size) return -1;
    uint32_t nBn = u32(b, p); p += 4;
    for (uint32_t i = 0; i < nBn; i++) {
        if (p + 0x30 > size) return -1;
        uint32_t h0 = u32(b, p), h2 = u32(b, p + 8), h3 = u32(b, p + 12);
        uint32_t h4 = u32(b, p + 16), h6 = u32(b, p + 24), h8 = u32(b, p + 32);
        p += 0x30 + h0 * 4;
        if (h3 != 1) p += h2 * 8;
        if (h4) p += h2 * 4;
        p += h2 * 4;
        if (h8) p += h8 * 4;
        for (uint32_t j = 0; j < h2; j++) {
            if (h4) {
                p += (j == 0) ? (h4 * 8) : ((h4 & 1) ? ((h4 + 1) * 2) : (h4 * 2));
            }
            if (h8 == 0) p += h6 * 24;
        }
        if (h8) p += h8 * h6 * 16;
    }

    if (F & 0x40000) {
        if (p + 4 > size) return -1;
        uint32_t k = u32(b, p) & 0xFFFF;
        p += 4 + k * 0xC00;
    }

    /* betikler */
    if (p + 4 > size) return -1;
    uint32_t ns = u32(b, p); p += 4;
    for (uint32_t i = 0; i < ns; i++) {
        if (p + 4 > size) return -1;
        p += 4 + u32(b, p) * 4;
    }

    /* C: statik mesh şablonları */
    if (p + 4 > size) return -1;
    uint32_t nC = u32(b, p); p += 4;
    uint32_t H = p;
    p += nC * 0x68;
    if (p > size) return -1;

    DpsxModel *models = calloc(nC ? nC : 1, sizeof(DpsxModel));
    for (uint32_t i = 0; i < nC; i++) {
        uint32_t h = H + i * 0x68;
        uint32_t n1 = u32(b, h + 0x48);
        uint32_t nB = u32(b, h + 0x54);
        uint32_t nprim = (uint32_t)u16(b, h + 0x5C) + u16(b, h + 0x5E) + u16(b, h + 0x60);
        models[i].verts = (const int16_t *)(b + p);
        models[i].n_verts = n1;
        p += n1 * 8;
        models[i].faces = (const uint16_t *)(b + p);
        models[i].n_faces = nB;
        p += nB * 12;
        p += nprim * 32;
        if (p > size) { free(models); return -1; }
    }

    if (F & 4) p += 4;
    if (F & 0x10) p += 4;
    if (p + 4 > size) { free(models); return -1; }

    if (u32(b, p) == 0) {
        out->model_count = nC;
        free(models);
        return 0;
    }

    p += 4;
    if (p + 4 > size) { free(models); return -1; }
    uint32_t s2 = u32(b, p);
    uint32_t s6 = p + 4 + s2 * 4;
    if (s6 + 0x98 > size) { free(models); return -1; }
    uint32_t W0 = u32(b, s6 + 0);
    uint32_t W3 = u32(b, s6 + 12);
    uint32_t W4 = u32(b, s6 + 16);
    uint32_t W5 = u32(b, s6 + 20);
    p = s6 + 0x98 + W3 * 4 + W0 * 8;
    if (F & 0x1000) {
        p += 0x100;
        if (p + 4 > size) { free(models); return -1; }
        p += 4 + u32(b, p) * 4;
    } else {
        p += W0 * 8;
    }
    if (p + 4 <= size && u32(b, p) == 0x777666) {
        p += 4 + ((W4 * W5) >> 1) * 4;
    }

    uint32_t inst_off = p;
    uint32_t idx_off = p + W0 * 24;
    if (idx_off + W0 * 4 > size) { free(models); return -1; }

    uint32_t vcap = 0;
    out->model_count = nC;
    out->instance_count = W0;

    for (uint32_t i = 0; i < W0; i++) {
        const uint8_t *ins = b + inst_off + i * 24;
        int16_t rx = s16(ins, 0), ry = s16(ins, 2), rz = s16(ins, 4);
        float px = (float)s32(ins, 8), py = (float)s32(ins, 12), pz = (float)s32(ins, 16);
        uint32_t mid = u32(b, idx_off + i * 4);
        if (mid >= nC) continue;
        const DpsxModel *m = &models[mid];
        float R[3][3];
        make_rot(rx, ry, rz, R);

        for (uint32_t fi = 0; fi < m->n_faces; fi++) {
            const uint16_t *f = m->faces + fi * 6;
            uint16_t a = f[0], bb = f[1], c_ = f[2], d = f[3], tex_idx = f[4], fl = f[5];
            if (a >= m->n_verts || bb >= m->n_verts || c_ >= m->n_verts) continue;

            float va[3], vb[3], vc[3], vd[3];
            const int16_t *pa = m->verts + a * 4;
            const int16_t *pb = m->verts + bb * 4;
            const int16_t *pc = m->verts + c_ * 4;
            for (int k = 0; k < 3; k++) {
                va[k] = R[k][0]*pa[0] + R[k][1]*pa[1] + R[k][2]*pa[2] + (k==0?px:(k==1?py:pz));
                vb[k] = R[k][0]*pb[0] + R[k][1]*pb[1] + R[k][2]*pb[2] + (k==0?px:(k==1?py:pz));
                vc[k] = R[k][0]*pc[0] + R[k][1]*pc[1] + R[k][2]*pc[2] + (k==0?px:(k==1?py:pz));
            }
            bool has_tex = (tpsx != NULL && tex_idx < tpsx->nrec && tpsx->uvs[tex_idx].valid);
            float uv0[2] = { has_tex ? tpsx->uvs[tex_idx].u[0] : 0.001f, has_tex ? tpsx->uvs[tex_idx].v[0] : 0.001f };
            float uv1[2] = { has_tex ? tpsx->uvs[tex_idx].u[1] : 0.001f, has_tex ? tpsx->uvs[tex_idx].v[1] : 0.001f };
            float uv2[2] = { has_tex ? tpsx->uvs[tex_idx].u[2] : 0.001f, has_tex ? tpsx->uvs[tex_idx].v[2] : 0.001f };
            float uv3[2] = { has_tex ? tpsx->uvs[tex_idx].u[3] : 0.001f, has_tex ? tpsx->uvs[tex_idx].v[3] : 0.001f };

            push_tri(out, &vcap, va, vb, vc, uv0, uv1, uv2, has_tex, mid);
            if ((fl & 0x800) && d < m->n_verts) {
                const int16_t *pd = m->verts + d * 4;
                for (int k = 0; k < 3; k++) {
                    vd[k] = R[k][0]*pd[0] + R[k][1]*pd[1] + R[k][2]*pd[2] + (k==0?px:(k==1?py:pz));
                }
                push_tri(out, &vcap, vb, vd, vc, uv1, uv3, uv2, has_tex, mid);
            }
        }
    }

    free(models);
    return 0;
}

void dpsx_free(DpsxLevel *lvl) {
    free(lvl->verts);
    memset(lvl, 0, sizeof(*lvl));
}
