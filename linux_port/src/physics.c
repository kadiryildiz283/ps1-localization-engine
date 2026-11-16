#include "physics.h"
#include <math.h>

static bool point_in_tri_xz(float px, float pz,
                            float ax, float az,
                            float bx, float bz,
                            float cx, float cz,
                            float *u, float *v, float *w) {
    float v0x = cx - ax, v0z = cz - az;
    float v1x = bx - ax, v1z = bz - az;
    float v2x = px - ax, v2z = pz - az;
    float d00 = v0x * v0x + v0z * v0z;
    float d01 = v0x * v1x + v0z * v1z;
    float d11 = v1x * v1x + v1z * v1z;
    float denom = d00 * d11 - d01 * d01;
    if (fabsf(denom) < 1e-6f) return false;
    float d20 = v2x * v0x + v2z * v0z;
    float d21 = v2x * v1x + v2z * v1z;
    *u = (d11 * d20 - d01 * d21) / denom;
    *v = (d00 * d21 - d01 * d20) / denom;
    *w = 1.0f - *u - *v;
    return (*u >= -0.001f && *v >= -0.001f && *w >= -0.001f);
}

bool physics_ground_y(const DpsxLevel *lvl, float x, float z, float cur_y, float *out_y) {
    float best_y = -1e30f;
    bool found = false;
    for (uint32_t i = 0; i + 2 < lvl->vert_count; i += 3) {
        const DpsxVertex *a = &lvl->verts[i];
        const DpsxVertex *b = &lvl->verts[i + 1];
        const DpsxVertex *c = &lvl->verts[i + 2];
        /* Sadece yukarı bakan zemin üçgenleri (ny > 0.35 veya |ny| > 0.35) */
        if (fabsf(a->ny) < 0.35f) continue;

        float minx = fminf(a->x, fminf(b->x, c->x));
        float maxx = fmaxf(a->x, fmaxf(b->x, c->x));
        if (x < minx || x > maxx) continue;
        float minz = fminf(a->z, fminf(b->z, c->z));
        float maxz = fmaxf(a->z, fmaxf(b->z, c->z));
        if (z < minz || z > maxz) continue;

        float u, v, w;
        if (point_in_tri_xz(x, z, a->x, a->z, b->x, b->z, c->x, c->z, &u, &v, &w)) {
            float y = w * a->y + v * b->y + u * c->y;
            if (y <= cur_y + 450.0f && y > best_y) {
                best_y = y;
                found = true;
            }
        }
    }
    if (found) *out_y = best_y;
    return found;
}

void physics_find_spawn(const DpsxLevel *lvl, Player *p) {
    p->vy = 0.0f;
    p->on_ground = false;
    p->yaw = 0.0f;
    p->pitch = -0.15f;
    if (lvl->vert_count == 0) {
        p->x = p->z = 0.0f;
        p->y = 500.0f;
        return;
    }
    float cx = 0.5f * (lvl->min_x + lvl->max_x);
    float cz = 0.5f * (lvl->min_z + lvl->max_z);
    float gy = 0.0f;
    if (physics_ground_y(lvl, cx, cz, lvl->max_y + 1000.0f, &gy)) {
        p->x = cx;
        p->z = cz;
        p->y = gy + 380.0f;
        p->on_ground = true;
        return;
    }
    /* Merkez boşluktaysa en yakın zemin üçgenini bul */
    float best_d2 = 1e30f;
    float bx = cx, by = lvl->min_y + 500.0f, bz = cz;
    for (uint32_t i = 0; i + 2 < lvl->vert_count; i += 3) {
        const DpsxVertex *a = &lvl->verts[i];
        if (fabsf(a->ny) < 0.45f) continue;
        float tx = (a->x + lvl->verts[i+1].x + lvl->verts[i+2].x) / 3.0f;
        float ty = (a->y + lvl->verts[i+1].y + lvl->verts[i+2].y) / 3.0f;
        float tz = (a->z + lvl->verts[i+1].z + lvl->verts[i+2].z) / 3.0f;
        float d2 = (tx - cx)*(tx - cx) + (tz - cz)*(tz - cz);
        if (d2 < best_d2) {
            best_d2 = d2;
            bx = tx; by = ty + 380.0f; bz = tz;
        }
    }
    p->x = bx; p->y = by; p->z = bz;
}

void physics_step(const DpsxLevel *lvl, Player *p, float move_fwd, float move_right, bool jump, float dt) {
    const float eye_h = 380.0f;
    float fx = -sinf(p->yaw), fz = -cosf(p->yaw);
    float rx = cosf(p->yaw), rz = -sinf(p->yaw);

    float nx = p->x + (fx * move_fwd + rx * move_right) * dt;
    float nz = p->z + (fz * move_fwd + rz * move_right) * dt;

    if (p->noclip) {
        p->x = nx;
        p->z = nz;
        return;
    }

    /* Zemin yüksekliği kontrolü (yürünebilir alan dışına veya yüksek duvara çarpmayı engelle) */
    float gy = 0.0f;
    if (physics_ground_y(lvl, nx, nz, p->y - eye_h + 250.0f, &gy)) {
        p->x = nx;
        p->z = nz;
    } else if (physics_ground_y(lvl, nx, p->z, p->y - eye_h + 250.0f, &gy)) {
        p->x = nx;
    } else if (physics_ground_y(lvl, p->x, nz, p->y - eye_h + 250.0f, &gy)) {
        p->z = nz;
    }

    if (jump && p->on_ground) {
        p->vy = 1900.0f;
        p->on_ground = false;
    }

    p->vy -= 5200.0f * dt;
    p->y += p->vy * dt;

    if (physics_ground_y(lvl, p->x, p->z, p->y - eye_h + 100.0f, &gy)) {
        if (p->y - eye_h <= gy) {
            p->y = gy + eye_h;
            p->vy = 0.0f;
            p->on_ground = true;
        } else {
            p->on_ground = false;
        }
    } else {
        p->on_ground = false;
    }
}
