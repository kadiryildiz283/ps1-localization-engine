#include "dpsx.h"
#include "tpsx.h"
#include "lpsx.h"
#include "audio_spu.h"
#include "render_gl.h"
#include "physics.h"
#include <SDL2/SDL.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* Statik asset kökü: motor disc yerine çıkarılmış dosyalardan çağırır. */
static const char *ASSETS = "build_assets";

static uint8_t *read_file(const char *path, uint32_t *out_size) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (sz < 0) { fclose(f); return NULL; }
    uint8_t *buf = malloc((size_t)sz ? (size_t)sz : 1);
    if (fread(buf, 1, (size_t)sz, f) != (size_t)sz) { free(buf); fclose(f); return NULL; }
    fclose(f);
    if (out_size) *out_size = (uint32_t)sz;
    return buf;
}

static uint32_t le32(const uint8_t *p) {
    return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* Çıkarılmış statik medya: STR video kare manifestosu + DEM kamera pisti. */
static char s_video_paths[128][64];
static int s_n_video;
static uint16_t *s_dem_yaw;
static int s_dem_n;

static void load_static_media(void) {
    char path[512], line[64];
    snprintf(path, sizeof(path), "%s/video/frames.txt", ASSETS);
    FILE *f = fopen(path, "r");
    if (f) {
        while (s_n_video < 128 && fgets(line, sizeof(line), f)) {
            line[strcspn(line, "\r\n")] = 0;
            if (line[0]) snprintf(s_video_paths[s_n_video++], 64, "%s", line);
        }
        fclose(f);
    }
    snprintf(path, sizeof(path), "%s/animations/T1L1M002.bin", ASSETS);
    uint32_t sz = 0;
    uint8_t *b = read_file(path, &sz);
    if (b && sz >= 4) {
        uint32_t n = le32(b);
        if (n && 4 + n * 2 <= sz) {
            s_dem_n = (int)n;
            s_dem_yaw = malloc(n * 2);
            for (uint32_t i = 0; i < n; i++) s_dem_yaw[i] = (uint16_t)(b[4 + i * 2] | (b[5 + i * 2] << 8));
        }
        free(b);
    }
}

typedef enum {
    STATE_TITLE = 0,
    STATE_LEVEL_SELECT,
    STATE_PLAYING,
    STATE_PAUSE
} GameState;

typedef struct {
    char name[13];
} WadName;

typedef struct {
    bool active;
    float x, y, z;
    float vx, vy, vz;
    float life;
} SpellOrb;

#define MAX_COLLECTIBLES 16
typedef struct {
    bool active;
    float x, y, z;
    float r, g, b;
} Collectible;

static void spawn_collectibles(const DpsxLevel *lvl, Collectible *cols) {
    memset(cols, 0, sizeof(Collectible) * MAX_COLLECTIBLES);
    if (lvl->vert_count < 9) return;
    uint32_t tris = lvl->vert_count / 3;
    uint32_t step = tris / (MAX_COLLECTIBLES + 1);
    if (step < 1) step = 1;
    int placed = 0;
    for (uint32_t t = 0; t < tris && placed < MAX_COLLECTIBLES; t += step) {
        const DpsxVertex *a = &lvl->verts[t * 3];
        if (fabsf(a->ny) < 0.45f) continue;
        cols[placed].active = true;
        cols[placed].x = (a->x + lvl->verts[t*3+1].x + lvl->verts[t*3+2].x) / 3.0f;
        cols[placed].y = (a->y + lvl->verts[t*3+1].y + lvl->verts[t*3+2].y) / 3.0f + 130.0f;
        cols[placed].z = (a->z + lvl->verts[t*3+1].z + lvl->verts[t*3+2].z) / 3.0f;
        cols[placed].r = (placed % 3 == 0) ? 1.0f : (placed % 3 == 1 ? 0.3f : 0.9f);
        cols[placed].g = (placed % 3 == 0) ? 0.3f : (placed % 3 == 1 ? 0.95f : 0.8f);
        cols[placed].b = (placed % 3 == 0) ? 0.8f : (placed % 3 == 1 ? 0.4f : 0.2f);
        placed++;
    }
}

/* Seviye listesi statik manifest'ten (build_assets/wads.txt). */
static int collect_wads(WadName *out, int max) {
    char path[512];
    snprintf(path, sizeof(path), "%s/wads.txt", ASSETS);
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    int n = 0;
    char line[64];
    while (n < max && fgets(line, sizeof(line), f)) {
        line[strcspn(line, "\r\n")] = 0;
        if (line[0]) { snprintf(out[n].name, sizeof(out[n].name), "%s", line); n++; }
    }
    fclose(f);
    return n;
}

/* Tüm assetler çıkarılmış statik dosyalardan okunur (disc yok). */
static int load_wad_level(const char *stem, DpsxLevel *lvl, TpsxBank *tpsx, LpsxTable *lpsx) {
    char path[512];
    uint32_t sz = 0;
    int rc = -1;
    if (tpsx) {
        snprintf(path, sizeof(path), "%s/textures/WAD/%s/tpsx.bin", ASSETS, stem);
        uint8_t *t = read_file(path, &sz);
        if (t) { tpsx_load(t, sz, tpsx); free(t); }
    }
    snprintf(path, sizeof(path), "%s/levels/%s/dpsx.bin", ASSETS, stem);
    uint8_t *d = read_file(path, &sz);
    if (d) { rc = dpsx_load(d, sz, tpsx, lvl); free(d); }
    if (lpsx) {
        snprintf(path, sizeof(path), "%s/dialogues/%s/lpsx.bin", ASSETS, stem);
        uint8_t *l = read_file(path, &sz);
        if (l) { lpsx_load(l, sz, lpsx); free(l); }
    }
    return rc;
}

static int cmd_test_all(void) {
    WadName wads[128];
    int n = collect_wads(wads, 128);
    int ok = 0, fail = 0;
    uint64_t total_tris = 0, total_lpsx = 0;
    for (int i = 0; i < n; i++) {
        DpsxLevel lvl = {0};
        TpsxBank tpsx = {0};
        LpsxTable lpsx = {0};
        if (load_wad_level(wads[i].name, &lvl, &tpsx, &lpsx) == 0) {
            ok++;
            total_tris += lvl.tri_count;
            total_lpsx += lpsx.count;
        } else {
            fail++;
            fprintf(stderr, "FAIL: %s\n", wads[i].name);
        }
        dpsx_free(&lvl);
        tpsx_free(&tpsx);
        lpsx_free(&lpsx);
    }
    printf("WAD test: ok=%d fail=%d total_tris=%llu total_dialogues=%llu\n",
           ok, fail, (unsigned long long)total_tris, (unsigned long long)total_lpsx);
    return fail == 0 ? 0 : 1;
}

static void play_wad_sfx(AudioEngine *ae, const char *wad_name, int *cur_sfx) {
    char stem[16];
    snprintf(stem, sizeof(stem), "%s", wad_name);
    char *dot = strchr(stem, '.');
    if (dot) *dot = 0;
    char wav[256];
    snprintf(wav, sizeof(wav), "build_assets/audio/WAD/%s/%d.wav", stem, *cur_sfx);
    if (audio_play_wav(ae, wav) != 0) {
        *cur_sfx = 0;
        snprintf(wav, sizeof(wav), "build_assets/audio/WAD/%s/0.wav", stem);
        audio_play_wav(ae, wav);
    } else {
        (*cur_sfx)++;
    }
}

static void switch_level(const WadName *wads, int idx,
                         DpsxLevel *lvl, TpsxBank *tpsx, LpsxTable *lpsx,
                         GlMesh *gm, Player *pl, Collectible *cols, uint32_t *cur_dlg, int *cur_sfx) {
    dpsx_free(lvl);
    tpsx_free(tpsx);
    lpsx_free(lpsx);
    if (load_wad_level(wads[idx].name, lvl, tpsx, lpsx) == 0) {
        gl_upload_mesh(gm, lvl, tpsx);
        physics_find_spawn(lvl, pl);
        spawn_collectibles(lvl, cols);
        *cur_dlg = 0;
        *cur_sfx = 0;
    }
}

int main(int argc, char **argv) {
    if (argc >= 2 && strcmp(argv[1], "ls") == 0) {
        WadName w[128];
        int n = collect_wads(w, 128);
        for (int i = 0; i < n; i++) printf("%s\n", w[i].name);
        return 0;
    }
    if (argc >= 2 && strcmp(argv[1], "--test-all") == 0) {
        return cmd_test_all();
    }

    WadName wads[128];
    int n_wads = collect_wads(wads, 128);
    if (n_wads == 0) {
        fprintf(stderr, "build_assets/wads.txt yok; once re/extract_all.py calistir\n");
        return 1;
    }

    int cur_wad = 0;
    char start_stem[16];
    const char *start_wad = (argc >= 2) ? argv[1] : "T1L2M001";
    snprintf(start_stem, sizeof(start_stem), "%s", start_wad);
    char *dot = strchr(start_stem, '.');
    if (dot) *dot = 0;
    for (int i = 0; i < n_wads; i++) {
        if (strcmp(wads[i].name, start_stem) == 0) { cur_wad = i; break; }
    }

    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO) != 0) {
        return 1;
    }
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 2);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 1);
    SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
    SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 24);

    int win_w = 1280, win_h = 720;
    SDL_Window *win = SDL_CreateWindow(
        "Harry Potter and the Chamber of Secrets - Native Linux Port",
        SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
        win_w, win_h, SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE
    );
    if (!win) {
        SDL_Quit();
        return 1;
    }
    SDL_GLContext ctx = SDL_GL_CreateContext(win);
    SDL_GL_SetSwapInterval(1);
    gl_setup_scene(win_w, win_h);

    AudioEngine ae;
    audio_init(&ae);
    /* Çıkarılmış XA müziğini statik dosyadan çal (EA.STR intro). */
    audio_play_wav(&ae, "build_assets/audio/XA/1.wav");

    DpsxLevel lvl = {0};
    TpsxBank tpsx = {0};
    LpsxTable lpsx = {0};
    GlMesh gm = {0};
    Player pl = {0};
    SpellOrb orb = {0};
    Collectible cols[MAX_COLLECTIBLES];
    uint32_t cur_dlg = 0;
    int cur_sfx = 0;
    int beans = 0;
    bool third_person = false;
    bool show_hud = true;
    bool mouse_grab = false;

    load_static_media();
    int vid_idx = 0, vid_w = 0, vid_h = 0;
    uint8_t *vid_rgb = NULL;
    uint32_t vid_tick = 0;
    float dem_acc = 0;
    int dem_idx = 0;

    GameState state = (argc >= 2) ? STATE_PLAYING : STATE_TITLE;
    int menu_idx = 0;
    int sel_wad = cur_wad;

    switch_level(wads, cur_wad, &lvl, &tpsx, &lpsx, &gm, &pl, cols, &cur_dlg, &cur_sfx);

    uint32_t last_ticks = SDL_GetTicks();
    bool running = true;
    while (running) {
        uint32_t now = SDL_GetTicks();
        float dt = (now - last_ticks) / 1000.0f;
        if (dt > 0.05f) dt = 0.05f;
        last_ticks = now;

        bool jump_req = false;
        SDL_Event ev;
        while (SDL_PollEvent(&ev)) {
            if (ev.type == SDL_QUIT) running = false;
            else if (ev.type == SDL_WINDOWEVENT && ev.window.event == SDL_WINDOWEVENT_SIZE_CHANGED) {
                win_w = ev.window.data1;
                win_h = ev.window.data2;
            } else if (state == STATE_PLAYING && ev.type == SDL_MOUSEMOTION &&
                       (mouse_grab || (ev.motion.state & SDL_BUTTON_LMASK))) {
                pl.yaw -= ev.motion.xrel * 0.004f;
                pl.pitch -= ev.motion.yrel * 0.004f;
                if (pl.pitch > 1.45f) pl.pitch = 1.45f;
                if (pl.pitch < -1.45f) pl.pitch = -1.45f;
            } else if (state == STATE_PLAYING && ev.type == SDL_MOUSEBUTTONDOWN && ev.button.button == SDL_BUTTON_RIGHT) {
                /* Sağ tık: Asa ile Flipendo büyüsü at! */
                orb.active = true;
                orb.x = pl.x; orb.y = pl.y - 60.0f; orb.z = pl.z;
                float cp = cosf(pl.pitch);
                orb.vx = -sinf(pl.yaw) * cp * 9000.0f;
                orb.vy = sinf(pl.pitch) * 9000.0f;
                orb.vz = -cosf(pl.yaw) * cp * 9000.0f;
                orb.life = 2.0f;
                play_wad_sfx(&ae, wads[cur_wad].name, &cur_sfx);
            } else if (ev.type == SDL_KEYDOWN) {
                SDL_Keycode k = ev.key.keysym.sym;
                if (state == STATE_TITLE) {
                    if (k == SDLK_UP || k == SDLK_w) menu_idx = (menu_idx + 2) % 3;
                    else if (k == SDLK_DOWN || k == SDLK_s) menu_idx = (menu_idx + 1) % 3;
                    else if (k == SDLK_RETURN || k == SDLK_SPACE) {
                        if (menu_idx == 0) { state = STATE_PLAYING; }
                        else if (menu_idx == 1) { sel_wad = cur_wad; state = STATE_LEVEL_SELECT; }
                        else { running = false; }
                    } else if (k == SDLK_ESCAPE) running = false;
                } else if (state == STATE_LEVEL_SELECT) {
                    if (k == SDLK_UP || k == SDLK_w) sel_wad = (sel_wad - 1 + n_wads) % n_wads;
                    else if (k == SDLK_DOWN || k == SDLK_s) sel_wad = (sel_wad + 1) % n_wads;
                    else if (k == SDLK_PAGEUP) sel_wad = (sel_wad - 10 + n_wads) % n_wads;
                    else if (k == SDLK_PAGEDOWN) sel_wad = (sel_wad + 10) % n_wads;
                    else if (k == SDLK_RETURN || k == SDLK_SPACE) {
                        cur_wad = sel_wad;
                        switch_level(wads, cur_wad, &lvl, &tpsx, &lpsx, &gm, &pl, cols, &cur_dlg, &cur_sfx);
                        state = STATE_PLAYING;
                    } else if (k == SDLK_ESCAPE) state = STATE_TITLE;
                } else if (state == STATE_PAUSE) {
                    if (k == SDLK_UP || k == SDLK_w) menu_idx = (menu_idx + 3) % 4;
                    else if (k == SDLK_DOWN || k == SDLK_s) menu_idx = (menu_idx + 1) % 4;
                    else if (k == SDLK_ESCAPE) state = STATE_PLAYING;
                    else if (k == SDLK_RETURN || k == SDLK_SPACE) {
                        if (menu_idx == 0) state = STATE_PLAYING;
                        else if (menu_idx == 1) { sel_wad = cur_wad; state = STATE_LEVEL_SELECT; }
                        else if (menu_idx == 2) { pl.noclip = !pl.noclip; state = STATE_PLAYING; }
                        else { state = STATE_TITLE; menu_idx = 0; }
                    }
                } else if (state == STATE_PLAYING) {
                    if (k == SDLK_ESCAPE) {
                        mouse_grab = false;
                        SDL_SetRelativeMouseMode(SDL_FALSE);
                        menu_idx = 0;
                        state = STATE_PAUSE;
                    } else if (k == SDLK_TAB) show_hud = !show_hud;
                    else if (k == SDLK_F1) pl.noclip = !pl.noclip;
                    else if (k == SDLK_v) third_person = !third_person;
                    else if (k == SDLK_m) {
                        mouse_grab = !mouse_grab;
                        SDL_SetRelativeMouseMode(mouse_grab ? SDL_TRUE : SDL_FALSE);
                    } else if (k == SDLK_SPACE) {
                        jump_req = true;
                    } else if (k == SDLK_f) {
                        orb.active = true;
                        orb.x = pl.x; orb.y = pl.y - 60.0f; orb.z = pl.z;
                        float cp = cosf(pl.pitch);
                        orb.vx = -sinf(pl.yaw) * cp * 9000.0f;
                        orb.vy = sinf(pl.pitch) * 9000.0f;
                        orb.vz = -cosf(pl.yaw) * cp * 9000.0f;
                        orb.life = 2.0f;
                        play_wad_sfx(&ae, wads[cur_wad].name, &cur_sfx);
                    } else if (k == SDLK_n) {
                        if (lpsx.count > 0) cur_dlg = (cur_dlg + 1) % lpsx.count;
                        play_wad_sfx(&ae, wads[cur_wad].name, &cur_sfx);
                    } else if (k == SDLK_LEFTBRACKET || k == SDLK_RIGHTBRACKET) {
                        cur_wad = (k == SDLK_RIGHTBRACKET) ? (cur_wad + 1) % n_wads : (cur_wad - 1 + n_wads) % n_wads;
                        switch_level(wads, cur_wad, &lvl, &tpsx, &lpsx, &gm, &pl, cols, &cur_dlg, &cur_sfx);
                    } else if (k == SDLK_r) {
                        physics_find_spawn(&lvl, &pl);
                    }
                }
            }
        }

        if (state == STATE_PLAYING) {
            const uint8_t *ks = SDL_GetKeyboardState(NULL);
            float mult = (ks[SDL_SCANCODE_LSHIFT] || ks[SDL_SCANCODE_RSHIFT]) ? 2.6f : 1.0f;
            float spd = (pl.noclip ? 4500.0f : 2400.0f) * mult;
            float mf = 0.0f, mr = 0.0f;
            if (ks[SDL_SCANCODE_W] || ks[SDL_SCANCODE_UP])    mf += spd;
            if (ks[SDL_SCANCODE_S] || ks[SDL_SCANCODE_DOWN])  mf -= spd;
            if (ks[SDL_SCANCODE_D] || ks[SDL_SCANCODE_RIGHT]) mr += spd;
            if (ks[SDL_SCANCODE_A] || ks[SDL_SCANCODE_LEFT])  mr -= spd;
            if (pl.noclip) {
                if (ks[SDL_SCANCODE_E]) pl.y += spd * dt;
                if (ks[SDL_SCANCODE_Q]) pl.y -= spd * dt;
            }
            physics_step(&lvl, &pl, mf, mr, jump_req, dt);

            if (orb.active) {
                orb.x += orb.vx * dt;
                orb.y += orb.vy * dt;
                orb.z += orb.vz * dt;
                orb.life -= dt;
                if (orb.life <= 0.0f) orb.active = false;
            }
            for (int i = 0; i < MAX_COLLECTIBLES; i++) {
                if (!cols[i].active) continue;
                float dx = cols[i].x - pl.x, dy = cols[i].y - (pl.y - 160.0f), dz = cols[i].z - pl.z;
                if (dx*dx + dy*dy + dz*dz < 360.0f * 360.0f) {
                    cols[i].active = false;
                    beans++;
                    play_wad_sfx(&ae, wads[cur_wad].name, &cur_sfx);
                }
            }
        } else {
            /* Menü/attract: çıkarılmış DEM kamera pistini izle (statik animasyon). */
            if (s_dem_n > 0) {
                dem_acc += dt * 50.0f; /* DEM 50 Hz VSync */
                while (dem_acc >= 1.0f) { dem_acc -= 1.0f; dem_idx = (dem_idx + 1) % s_dem_n; }
                pl.yaw = (s_dem_yaw[dem_idx] & 0xFFF) * (2.0f * (float)M_PI / 4096.0f);
            } else {
                pl.yaw += 0.15f * dt;
            }
            /* STR intro karelerini ~10 fps döndür (statik video dosyaları). */
            if (state == STATE_TITLE && s_n_video > 0 && now - vid_tick >= 100) {
                vid_tick = now;
                vid_idx = (vid_idx + 1) % s_n_video;
                char vp[512];
                snprintf(vp, sizeof(vp), "%s/video/%s", ASSETS, s_video_paths[vid_idx]);
                uint32_t vs = 0;
                uint8_t *vb = read_file(vp, &vs);
                if (vb && vs >= 4) {
                    free(vid_rgb);
                    vid_w = vb[0] | (vb[1] << 8);
                    vid_h = vb[2] | (vb[3] << 8);
                    vid_rgb = vb;
                } else free(vb);
            }
        }

        Camera cam = { pl.x, pl.y, pl.z, pl.yaw, pl.pitch };
        if (third_person && state == STATE_PLAYING) {
            cam.x = pl.x + sinf(pl.yaw) * 650.0f;
            cam.z = pl.z + cosf(pl.yaw) * 650.0f;
            cam.y = pl.y + 180.0f;
        }
        gl_draw_mesh(&gm, &cam, win_w, win_h);
        if (third_person && state == STATE_PLAYING) {
            gl_draw_player(pl.x, pl.y, pl.z, pl.yaw);
        }
        for (int i = 0; i < MAX_COLLECTIBLES; i++) {
            if (cols[i].active) {
                float bob = sinf(now * 0.005f + i) * 35.0f;
                gl_draw_orb(cols[i].x, cols[i].y + bob, cols[i].z, 65.0f, cols[i].r, cols[i].g, cols[i].b);
            }
        }
        if (orb.active) {
            gl_draw_orb(orb.x, orb.y, orb.z, 90.0f, 0.35f, 0.85f, 1.0f);
        }

        gl_hud_begin(win_w, win_h);
        if (state == STATE_TITLE && vid_rgb) {
            gl_video_frame(vid_rgb, vid_w, vid_h, win_w, win_h);
        }
        if (state == STATE_TITLE) {
            gl_hud_rect(win_w * 0.5f - 280, win_h * 0.5f - 160, 560, 320, 0.04f, 0.05f, 0.10f, 0.88f);
            gl_hud_text(win_w * 0.5f - 240, win_h * 0.5f - 125, 2.5f, "HARRY POTTER II", 1.0f, 0.84f, 0.25f);
            gl_hud_text(win_w * 0.5f - 240, win_h * 0.5f - 90, 1.8f, "Chamber of Secrets - Native Linux Port", 0.78f, 0.85f, 0.95f);
            const char *opts[3] = { "OYUNA BASLA (Kovuk Bahcesi)", "BOLUM SEC (78 Seviye)", "CIKIS" };
            for (int i = 0; i < 3; i++) {
                float r = (i == menu_idx) ? 1.0f : 0.75f;
                float g = (i == menu_idx) ? 0.92f : 0.78f;
                float b = (i == menu_idx) ? 0.35f : 0.82f;
                char buf[64];
                snprintf(buf, sizeof(buf), "%s %s", (i == menu_idx) ? ">" : " ", opts[i]);
                gl_hud_text(win_w * 0.5f - 220, win_h * 0.5f - 10 + i * 40, 2.0f, buf, r, g, b);
            }
            gl_hud_text(win_w * 0.5f - 240, win_h * 0.5f + 125, 1.4f, "W/S Sec | ENTER Onayla", 0.65f, 0.7f, 0.75f);
        } else if (state == STATE_LEVEL_SELECT) {
            gl_hud_rect(win_w * 0.5f - 260, 60, 520, win_h - 120, 0.04f, 0.05f, 0.10f, 0.90f);
            gl_hud_text(win_w * 0.5f - 230, 80, 2.0f, "BOLUM SECIMI (78 WAD)", 1.0f, 0.84f, 0.25f);
            int start = sel_wad - 8;
            if (start < 0) start = 0;
            if (start > n_wads - 18) start = n_wads - 18;
            if (start < 0) start = 0;
            for (int i = 0; i < 18 && start + i < n_wads; i++) {
                int idx = start + i;
                char row[64];
                snprintf(row, sizeof(row), "%s [%02d] %s", (idx == sel_wad) ? ">" : " ", idx + 1, wads[idx].name);
                gl_hud_text(win_w * 0.5f - 220, 125 + i * 28, 1.8f, row,
                            idx == sel_wad ? 1.0f : 0.8f, idx == sel_wad ? 0.9f : 0.82f, idx == sel_wad ? 0.3f : 0.88f);
            }
        } else if (state == STATE_PAUSE) {
            gl_hud_rect(win_w * 0.5f - 220, win_h * 0.5f - 130, 440, 260, 0.04f, 0.05f, 0.10f, 0.90f);
            gl_hud_text(win_w * 0.5f - 180, win_h * 0.5f - 100, 2.2f, "OYUN DURAKLATILDI", 1.0f, 0.84f, 0.25f);
            const char *opts[4] = {
                "Devam Et",
                "Bolum Degistir",
                pl.noclip ? "Mod: Serbest Ucus (Yurume Ac)" : "Mod: Yurume + Fizik (Ucus Ac)",
                "Ana Menu"
            };
            for (int i = 0; i < 4; i++) {
                char buf[64];
                snprintf(buf, sizeof(buf), "%s %s", (i == menu_idx) ? ">" : " ", opts[i]);
                gl_hud_text(win_w * 0.5f - 190, win_h * 0.5f - 45 + i * 36, 1.7f, buf,
                            i == menu_idx ? 1.0f : 0.8f, i == menu_idx ? 0.9f : 0.8f, i == menu_idx ? 0.3f : 0.85f);
            }
        } else if (show_hud) {
            gl_hud_rect(12, 12, 760, 62, 0.04f, 0.06f, 0.10f, 0.72f);
            char line1[256], line2[256];
            snprintf(line1, sizeof(line1), "HP2 LINUX | [%d/%d] %s | %s | FASULYE:%d | TRIS:%u",
                     cur_wad + 1, n_wads, wads[cur_wad].name,
                     pl.noclip ? "SERBEST UCUS" : "OYUN MODU", beans, lvl.tri_count);
            snprintf(line2, sizeof(line2), "WASD Yuru | SPACE Zipla | V 3.Sahis | F/SagTik Buyu | N Diyalog | [/] Bolum | ESC Menu");
            gl_hud_text(22, 20, 1.8f, line1, 1.0f, 0.86f, 0.32f);
            gl_hud_text(22, 46, 1.4f, line2, 0.85f, 0.90f, 0.96f);

            if (lpsx.count > 0) {
                gl_hud_rect(12, win_h - 68, win_w - 24.0f, 54, 0.04f, 0.05f, 0.09f, 0.82f);
                char dlg[180];
                snprintf(dlg, sizeof(dlg), "DIYALOG [%u/%u]: %.130s",
                         cur_dlg + 1, lpsx.count, lpsx.entries[cur_dlg].en);
                gl_hud_text(24, win_h - 50, 1.6f, dlg, 0.72f, 1.0f, 0.76f);
            }
        }
        gl_hud_end();

        SDL_GL_SwapWindow(win);
    }

    gl_free_mesh(&gm);
    dpsx_free(&lvl);
    tpsx_free(&tpsx);
    lpsx_free(&lpsx);
    free(vid_rgb);
    free(s_dem_yaw);
    audio_shutdown(&ae);
    SDL_GL_DeleteContext(ctx);
    SDL_DestroyWindow(win);
    SDL_Quit();
    return 0;
}
