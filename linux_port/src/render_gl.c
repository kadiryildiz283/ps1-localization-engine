#define GL_GLEXT_PROTOTYPES
#include "render_gl.h"
#include <SDL2/SDL_opengl.h>
#include <math.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

void gl_setup_scene(int w, int h) {
    glViewport(0, 0, w, h);
    glEnable(GL_DEPTH_TEST);
    glDepthFunc(GL_LEQUAL);
    glEnable(GL_LIGHTING);
    glEnable(GL_LIGHT0);
    glEnable(GL_COLOR_MATERIAL);
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE);

    float amb[4] = {0.38f, 0.38f, 0.42f, 1.0f};
    float dif[4] = {0.75f, 0.72f, 0.68f, 1.0f};
    float pos[4] = {0.4f, 0.8f, 0.45f, 0.0f};
    glLightfv(GL_LIGHT0, GL_AMBIENT, amb);
    glLightfv(GL_LIGHT0, GL_DIFFUSE, dif);
    glLightfv(GL_LIGHT0, GL_POSITION, pos);
    glClearColor(0.06f, 0.08f, 0.12f, 1.0f);
}

void gl_upload_mesh(GlMesh *gm, const DpsxLevel *lvl, const TpsxBank *tpsx) {
    if (gm->vbo) glDeleteBuffers(1, &gm->vbo);
    if (gm->tex) glDeleteTextures(1, &gm->tex);
    gm->vbo = 0;
    gm->tex = 0;
    gm->vert_count = lvl->vert_count;
    if (tpsx && tpsx->atlas_rgba) {
        glGenTextures(1, &gm->tex);
        glBindTexture(GL_TEXTURE_2D, gm->tex);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, TPSX_ATLAS_SIZE, TPSX_ATLAS_SIZE, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, tpsx->atlas_rgba);
        glBindTexture(GL_TEXTURE_2D, 0);
    }
    if (lvl->vert_count == 0) return;
    glGenBuffers(1, &gm->vbo);
    glBindBuffer(GL_ARRAY_BUFFER, gm->vbo);
    glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)(lvl->vert_count * sizeof(DpsxVertex)),
                 lvl->verts, GL_STATIC_DRAW);
    glBindBuffer(GL_ARRAY_BUFFER, 0);
}

void gl_free_mesh(GlMesh *gm) {
    if (gm->vbo) glDeleteBuffers(1, &gm->vbo);
    if (gm->tex) glDeleteTextures(1, &gm->tex);
    gm->vbo = 0;
    gm->tex = 0;
    gm->vert_count = 0;
}

static void set_perspective(float fov_deg, float aspect, float znear, float zfar) {
    float f = 1.0f / tanf(fov_deg * (float)M_PI / 360.0f);
    float m[16] = {
        f / aspect, 0, 0, 0,
        0, f, 0, 0,
        0, 0, (zfar + znear) / (znear - zfar), -1,
        0, 0, (2 * zfar * znear) / (znear - zfar), 0
    };
    glLoadMatrixf(m);
}

void gl_draw_mesh(const GlMesh *gm, const Camera *cam, int w, int h) {
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
    glViewport(0, 0, w, h);
    glEnable(GL_DEPTH_TEST);
    glEnable(GL_LIGHTING);

    glMatrixMode(GL_PROJECTION);
    set_perspective(65.0f, h > 0 ? (float)w / (float)h : 1.333f, 32.0f, 120000.0f);

    glMatrixMode(GL_MODELVIEW);
    glLoadIdentity();
    glRotatef(-cam->pitch * 180.0f / (float)M_PI, 1, 0, 0);
    glRotatef(-cam->yaw * 180.0f / (float)M_PI, 0, 1, 0);
    glTranslatef(-cam->x, -cam->y, -cam->z);

    if (!gm->vbo || gm->vert_count == 0) return;
    if (gm->tex) {
        glEnable(GL_TEXTURE_2D);
        glBindTexture(GL_TEXTURE_2D, gm->tex);
        glEnable(GL_ALPHA_TEST);
        glAlphaFunc(GL_GREATER, 0.15f);
    }
    glBindBuffer(GL_ARRAY_BUFFER, gm->vbo);
    glEnableClientState(GL_VERTEX_ARRAY);
    glEnableClientState(GL_NORMAL_ARRAY);
    glEnableClientState(GL_TEXTURE_COORD_ARRAY);
    glEnableClientState(GL_COLOR_ARRAY);
    glVertexPointer(3, GL_FLOAT, sizeof(DpsxVertex), (const void *)0);
    glNormalPointer(GL_FLOAT, sizeof(DpsxVertex), (const void *)(3 * sizeof(float)));
    glTexCoordPointer(2, GL_FLOAT, sizeof(DpsxVertex), (const void *)(6 * sizeof(float)));
    glColorPointer(3, GL_FLOAT, sizeof(DpsxVertex), (const void *)(8 * sizeof(float)));
    glDrawArrays(GL_TRIANGLES, 0, (GLsizei)gm->vert_count);
    glDisableClientState(GL_COLOR_ARRAY);
    glDisableClientState(GL_TEXTURE_COORD_ARRAY);
    glDisableClientState(GL_NORMAL_ARRAY);
    glDisableClientState(GL_VERTEX_ARRAY);
    glBindBuffer(GL_ARRAY_BUFFER, 0);
    if (gm->tex) {
        glDisable(GL_ALPHA_TEST);
        glBindTexture(GL_TEXTURE_2D, 0);
        glDisable(GL_TEXTURE_2D);
    }
}

void gl_draw_orb(float x, float y, float z, float radius, float r, float g, float b) {
    glDisable(GL_LIGHTING);
    glDisable(GL_TEXTURE_2D);
    glPushMatrix();
    glTranslatef(x, y, z);
    glColor3f(r, g, b);
    glBegin(GL_TRIANGLES);
    const float s = radius;
    /* 8 yüzlü parlayan büyü kristali */
    const float v[6][3] = {{0,s,0},{0,-s,0},{s,0,0},{-s,0,0},{0,0,s},{0,0,-s}};
    const int f[8][3] = {{0,4,2},{0,2,5},{0,5,3},{0,3,4},{1,2,4},{1,5,2},{1,3,5},{1,4,3}};
    for (int i = 0; i < 8; i++) {
        glVertex3fv(v[f[i][0]]);
        glVertex3fv(v[f[i][1]]);
        glVertex3fv(v[f[i][2]]);
    }
    glEnd();
    glPopMatrix();
}

void gl_draw_player(float x, float y, float z, float yaw) {
    glDisable(GL_LIGHTING);
    glDisable(GL_TEXTURE_2D);
    glPushMatrix();
    glTranslatef(x, y - 380.0f, z);
    glRotatef(yaw * 180.0f / (float)M_PI, 0, 1, 0);
    /* Cüppe gövde (koyu lacivert/siyah) */
    glColor3f(0.12f, 0.14f, 0.28f);
    glBegin(GL_QUADS);
    float w = 55.0f, h = 230.0f;
    glVertex3f(-w, 0, w); glVertex3f(w, 0, w); glVertex3f(w, h, w); glVertex3f(-w, h, w);
    glVertex3f(-w, 0, -w); glVertex3f(w, 0, -w); glVertex3f(w, h, -w); glVertex3f(-w, h, -w);
    glVertex3f(-w, 0, -w); glVertex3f(-w, 0, w); glVertex3f(-w, h, w); glVertex3f(-w, h, -w);
    glVertex3f(w, 0, -w); glVertex3f(w, 0, w); glVertex3f(w, h, w); glVertex3f(w, h, -w);
    /* Kafa */
    glColor3f(0.88f, 0.72f, 0.58f);
    float hw = 38.0f;
    glVertex3f(-hw, h, hw); glVertex3f(hw, h, hw); glVertex3f(hw, h + 75, hw); glVertex3f(-hw, h + 75, hw);
    glVertex3f(-hw, h, -hw); glVertex3f(hw, h, -hw); glVertex3f(hw, h + 75, -hw); glVertex3f(-hw, h + 75, -hw);
    /* Asa (sağ elde ileri uzanan) */
    glColor3f(0.55f, 0.35f, 0.15f);
    glVertex3f(w, 150, 0); glVertex3f(w + 12, 150, 0); glVertex3f(w + 12, 162, -130); glVertex3f(w, 162, -130);
    glEnd();
    glPopMatrix();
}

void gl_hud_begin(int w, int h) {
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_LIGHTING);
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
    glMatrixMode(GL_PROJECTION);
    glLoadIdentity();
    glOrtho(0, w, h, 0, -1, 1);
    glMatrixMode(GL_MODELVIEW);
    glLoadIdentity();
}

void gl_hud_rect(float x, float y, float w, float h, float r, float g, float b, float a) {
    glColor4f(r, g, b, a);
    glBegin(GL_QUADS);
    glVertex2f(x, y);
    glVertex2f(x + w, y);
    glVertex2f(x + w, y + h);
    glVertex2f(x, y + h);
    glEnd();
}

/* Çıkarılmış STR video karesini (ham RGB) tam ekran çiz. HUD ortho modunda çağrılır. */
static uint32_t s_vid_tex;
void gl_video_frame(const uint8_t *rgb, int w, int h, int sw, int sh) {
    if (!rgb || w <= 0 || h <= 0) return;
    if (!s_vid_tex) glGenTextures(1, &s_vid_tex);
    glBindTexture(GL_TEXTURE_2D, s_vid_tex);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, w, h, 0, GL_RGB, GL_UNSIGNED_BYTE, rgb);
    glEnable(GL_TEXTURE_2D);
    glColor4f(1, 1, 1, 1);
    glBegin(GL_QUADS);
    glTexCoord2f(0, 0); glVertex2f(0, 0);
    glTexCoord2f(1, 0); glVertex2f((float)sw, 0);
    glTexCoord2f(1, 1); glVertex2f((float)sw, (float)sh);
    glTexCoord2f(0, 1); glVertex2f(0, (float)sh);
    glEnd();
    glDisable(GL_TEXTURE_2D);
    glBindTexture(GL_TEXTURE_2D, 0);
}

/* Kompakt 5x7 ASCII font (0x20..0x7E) */
static const uint8_t FONT5X7[95][5] = {
    {0x00,0x00,0x00,0x00,0x00},{0x00,0x00,0x5F,0x00,0x00},{0x00,0x07,0x00,0x07,0x00},{0x14,0x7F,0x14,0x7F,0x14},
    {0x24,0x2A,0x7F,0x2A,0x12},{0x23,0x13,0x08,0x64,0x62},{0x36,0x49,0x55,0x22,0x50},{0x00,0x05,0x03,0x00,0x00},
    {0x00,0x1C,0x22,0x41,0x00},{0x00,0x41,0x22,0x1C,0x00},{0x14,0x08,0x3E,0x08,0x14},{0x08,0x08,0x3E,0x08,0x08},
    {0x00,0x50,0x30,0x00,0x00},{0x08,0x08,0x08,0x08,0x08},{0x00,0x60,0x60,0x00,0x00},{0x20,0x10,0x08,0x04,0x02},
    {0x3E,0x51,0x49,0x45,0x3E},{0x00,0x42,0x7F,0x40,0x00},{0x42,0x61,0x51,0x49,0x46},{0x21,0x41,0x45,0x4B,0x31},
    {0x18,0x14,0x12,0x7F,0x10},{0x27,0x45,0x45,0x45,0x39},{0x3C,0x4A,0x49,0x49,0x30},{0x01,0x71,0x09,0x05,0x03},
    {0x36,0x49,0x49,0x49,0x36},{0x06,0x49,0x49,0x29,0x1E},{0x00,0x36,0x36,0x00,0x00},{0x00,0x56,0x36,0x00,0x00},
    {0x08,0x14,0x22,0x41,0x00},{0x14,0x14,0x14,0x14,0x14},{0x00,0x41,0x22,0x14,0x08},{0x02,0x01,0x51,0x09,0x06},
    {0x32,0x49,0x79,0x41,0x3E},{0x7E,0x11,0x11,0x11,0x7E},{0x7F,0x49,0x49,0x49,0x36},{0x3E,0x41,0x41,0x41,0x22},
    {0x7F,0x41,0x41,0x22,0x1C},{0x7F,0x49,0x49,0x49,0x41},{0x7F,0x09,0x09,0x09,0x01},{0x3E,0x41,0x49,0x49,0x7A},
    {0x7F,0x08,0x08,0x08,0x7F},{0x00,0x41,0x7F,0x41,0x00},{0x20,0x40,0x41,0x3F,0x01},{0x7F,0x08,0x14,0x22,0x41},
    {0x7F,0x40,0x40,0x40,0x40},{0x7F,0x02,0x0C,0x02,0x7F},{0x7F,0x04,0x08,0x10,0x7F},{0x3E,0x41,0x41,0x41,0x3E},
    {0x7F,0x09,0x09,0x09,0x06},{0x3E,0x41,0x51,0x21,0x5E},{0x7F,0x09,0x19,0x29,0x46},{0x46,0x49,0x49,0x49,0x31},
    {0x01,0x01,0x7F,0x01,0x01},{0x3F,0x40,0x40,0x40,0x3F},{0x1F,0x20,0x40,0x20,0x1F},{0x3F,0x40,0x38,0x40,0x3F},
    {0x63,0x14,0x08,0x14,0x63},{0x07,0x08,0x70,0x08,0x07},{0x61,0x51,0x49,0x45,0x43},{0x00,0x7F,0x41,0x41,0x00},
    {0x02,0x04,0x08,0x10,0x20},{0x00,0x41,0x41,0x7F,0x00},{0x04,0x02,0x01,0x02,0x04},{0x40,0x40,0x40,0x40,0x40},
    {0x00,0x01,0x02,0x04,0x00},{0x20,0x54,0x54,0x54,0x78},{0x7F,0x48,0x44,0x44,0x38},{0x38,0x44,0x44,0x44,0x20},
    {0x38,0x44,0x44,0x48,0x7F},{0x38,0x54,0x54,0x54,0x18},{0x08,0x7E,0x09,0x01,0x02},{0x0C,0x52,0x52,0x52,0x3E},
    {0x7F,0x08,0x04,0x04,0x78},{0x00,0x44,0x7D,0x40,0x00},{0x20,0x40,0x44,0x3D,0x00},{0x7F,0x10,0x28,0x44,0x00},
    {0x00,0x41,0x7F,0x40,0x00},{0x7C,0x04,0x18,0x04,0x78},{0x7C,0x08,0x04,0x04,0x78},{0x38,0x44,0x44,0x44,0x38},
    {0x7C,0x14,0x14,0x14,0x08},{0x08,0x14,0x14,0x18,0x7C},{0x7C,0x08,0x04,0x04,0x08},{0x48,0x54,0x54,0x54,0x20},
    {0x04,0x3F,0x44,0x40,0x20},{0x3C,0x40,0x40,0x20,0x7C},{0x1C,0x20,0x40,0x20,0x1C},{0x3C,0x40,0x30,0x40,0x3C},
    {0x44,0x28,0x10,0x28,0x44},{0x0C,0x50,0x50,0x50,0x3C},{0x44,0x64,0x54,0x4C,0x44},{0x00,0x08,0x36,0x41,0x00},
    {0x00,0x00,0x7F,0x00,0x00},{0x00,0x41,0x36,0x08,0x00},{0x10,0x08,0x08,0x10,0x08}
};

void gl_hud_text(float x, float y, float scale, const char *txt, float r, float g, float b) {
    glColor4f(r, g, b, 1.0f);
    float cx = x;
    glBegin(GL_QUADS);
    for (const char *p = txt; *p; p++) {
        unsigned char c = (unsigned char)*p;
        if (c == '\n') { cx = x; y += 9 * scale; continue; }
        if (c >= 32 && c <= 126) {
            const uint8_t *col = FONT5X7[c - 32];
            for (int i = 0; i < 5; i++) {
                uint8_t bits = col[i];
                for (int j = 0; j < 7; j++) {
                    if (bits & (1 << j)) {
                        float px = cx + i * scale, py = y + j * scale;
                        glVertex2f(px, py);
                        glVertex2f(px + scale, py);
                        glVertex2f(px + scale, py + scale);
                        glVertex2f(px, py + scale);
                    }
                }
            }
        }
        cx += 6 * scale;
    }
    glEnd();
}

void gl_hud_end(void) {
    glDisable(GL_BLEND);
}
