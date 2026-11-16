#ifndef HP2_RENDER_GL_H
#define HP2_RENDER_GL_H

#include "dpsx.h"
#include <stdint.h>

typedef struct {
    float x, y, z;
    float yaw;   /* radyan */
    float pitch; /* radyan */
} Camera;

typedef struct {
    uint32_t vbo;
    uint32_t tex;
    uint32_t vert_count;
} GlMesh;

void gl_setup_scene(int w, int h);
void gl_upload_mesh(GlMesh *gm, const DpsxLevel *lvl, const TpsxBank *tpsx);
void gl_free_mesh(GlMesh *gm);
void gl_draw_mesh(const GlMesh *gm, const Camera *cam, int w, int h);
void gl_draw_orb(float x, float y, float z, float radius, float r, float g, float b);
void gl_draw_player(float x, float y, float z, float yaw);

void gl_hud_begin(int w, int h);
void gl_video_frame(const uint8_t *rgb, int w, int h, int sw, int sh);
void gl_hud_rect(float x, float y, float w, float h, float r, float g, float b, float a);
void gl_hud_text(float x, float y, float scale, const char *txt, float r, float g, float b);
void gl_hud_end(void);

#endif
