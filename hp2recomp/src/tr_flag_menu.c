/* HP2 bayrak (dil seçim) ekranına iki Türkçe seçenek ekleyen güvenilir plugin.
 *
 * Orijinal 3 bayrak (EN/FR/DE) değişmez; alt banda iki TR bayrağı çizilir:
 *   bank 1 = TR ALTYAZI        (TR metin + orijinal EN ses)
 *   bank 2 = TR DUBLAJ+ALTYAZI (TR metin + TR ses)
 *
 * Mekanizma: PSXRecomp mod system — texture bank + host GPU draw packet.
 * Disc patch'i YOK; tüm etki runtime'da, feature kapatılınca stock davranış.
 */
#include "mod_plugins.h"
#include "func_override.h"
#include "cpu_state.h"
#include "tr_flag_tex.h"
#include <string.h>
#include <stdio.h>
#include <math.h>

#define DRAW_OTAG      0x000600A8u /* PsyQ DrawOTag: a0 = OT head, kicks DMA2 LL */
#define FLAG_MENU_FN   0x00025DF4u /* EURO1.GAM bayrak seçimi / giriş işleyici */
#define SFX_PREP_FN    0x00052C04u /* Menü ses parametresi hazırla */
#define SFX_PLAY_FN    0x00052B70u /* Menü tıklama sesi çal */
#define SFX_PARAM_ADDR 0x0007E488u /* Ses kanalı parametre yapısı */

#define GP_BASE       0x0007C91Cu
#define FLAG_ACTIVE   (GP_BASE + 0x1714u) /* 0x7E030: frontend bayrağı (save'de de 1) */
#define FE_FADE       0x0007DB5Cu         /* != 0 iken geçiş/fade sürüyor */
#define FE_STATE      0x0007DBBCu         /* 8 = Bayrak ekranı, 11 = Hafıza kartı/Slot */
#define PAD_EDGE      0x0007DFC0u         /* Menü kenar tetiklemeli tuş maskesi */
#define FLAG_SUBSTATE 0x000802D0u         /* >= 1 yalnızca interaktif bayrak ekranında */
#define LANG_ADDR     0x000802D4u         /* 0 = EN, 1 = FR, 2 = DE */
#define POTTER_DAT_LBA 1284u

#define PAD_UP    0x0010u
#define PAD_RIGHT 0x0020u
#define PAD_DOWN  0x0040u
#define PAD_LEFT  0x0080u
#define PAD_CROSS 0x4000u

#define BANK_SUB 1
#define BANK_DUB 2

/* Dalga için dikey şerit ızgarası: 2 bayrak x COLS şerit x 2 üçgen. */
#define COLS 8
#define NODES (2 * COLS * 2)
#define STRIDE 80
#define ARENA_BYTES (NODES * STRIDE)
#define LAST_OFF ((NODES - 1) * STRIDE)

static uint32_t s_arena;
static int s_active;
static int s_sel;          /* 0..4: 0-2 stock, 3=TR sub, 4=TR dub */
static int s_last_stock;   /* TR satırından Yukarı dönünce korunacak stock slot */
static int s_built_sel = -1;
static int s_tr_mode;      /* 0=stock, 1=TR ALTYAZI, 2=TR DUBLAJ+ALTYAZI */
static FILE *s_tr_fp;
static float s_phase;

/* Bir GT3 textured triangle node: header(4) + 9 word(36) + precision suffix(40).
 * Bank id word3/word6 high byte; gerçek koordinatlar precision suffix'ten. */
static uint32_t bitsf(float f) { uint32_t n; memcpy(&n, &f, 4); return n; }

static int in_flag_menu(void) {
    return psx_mod_read_word(FLAG_ACTIVE) == 1u &&
           psx_mod_read_word(FE_STATE) == 8u &&
           psx_mod_read_word(FE_FADE) == 0u;
}

static void close_tr_disc(void) {
    if (s_tr_fp) {
        fclose(s_tr_fp);
        s_tr_fp = NULL;
    }
    s_tr_mode = 0;
}

static void set_tr_mode(int mode) {
    static const char *const sub_paths[] = {
        "../../Harry Potter and the Chamber of Secrets (Turkce Altyazi).bin",
        "../Harry Potter and the Chamber of Secrets (Turkce Altyazi).bin",
        "disc/Harry Potter and the Chamber of Secrets (Turkce Altyazi).bin",
        "Harry Potter and the Chamber of Secrets (Turkce Altyazi).bin",
    };
    static const char *const dub_paths[] = {
        "../../Harry Potter and the Chamber of Secrets (Turkish).bin",
        "../Harry Potter and the Chamber of Secrets (Turkish).bin",
        "disc/Harry Potter and the Chamber of Secrets (Turkish).bin",
        "Harry Potter and the Chamber of Secrets (Turkish).bin",
    };
    if (mode <= 0) {
        close_tr_disc();
        return;
    }
    if (mode == s_tr_mode && s_tr_fp) return;
    close_tr_disc();
    const char *const *paths = (mode == 1) ? sub_paths : dub_paths;
    for (int i = 0; i < 4; ++i) {
        FILE *f = fopen(paths[i], "rb");
        if (f) {
            s_tr_fp = f;
            s_tr_mode = mode;
            fprintf(stdout, "tr_flag_menu: localization mode=%d image=%s\n",
                    mode, paths[i]);
            fflush(stdout);
            return;
        }
    }
    fprintf(stderr, "tr_flag_menu: warning: localized disc image missing for mode=%d\n", mode);
    fflush(stderr);
}

static void tr_patch_sector(uint32_t lba, int raw_sector,
                            uint8_t *bytes, uint32_t size) {
    if (!s_tr_mode || !s_tr_fp || lba < POTTER_DAT_LBA) return;
    uint32_t want = raw_sector ? 2352u : 2048u;
    if (size < want) return;
    long off = (long)lba * 2352L + (raw_sector ? 0L : 24L);
    if (fseek(s_tr_fp, off, SEEK_SET) != 0) return;
    size_t got = fread(bytes, 1u, want, s_tr_fp);
    (void)got;
}

static void put_tri(uint32_t base, uint32_t next, uint16_t bank,
                    const int xy[3][2], const int uv[3][2],
                    const uint32_t rgb[3]) {
    uint32_t hdr = (9u << 24) | (next & 0x00FFFFFFu);
    /* GT3 0x34 üçlüleri: C0,V0,TC0 | C1,V1,TC1 | C2,V2,TC2.
     * V=1,4,7; TC=2,5,8; bank id = C1(word3)/C2(word6) high byte. */
    uint32_t q[9];
    q[0] = 0x34000000u | (rgb[0] & 0x00FFFFFFu);
    q[1] = (uint32_t)xy[0][0] | ((uint32_t)xy[0][1] << 16);
    q[2] = (uint32_t)uv[0][0] | ((uint32_t)uv[0][1] << 8);
    q[3] = (rgb[1] & 0x00FFFFFFu) | ((uint32_t)(bank & 0xFF) << 24);
    q[4] = (uint32_t)xy[1][0] | ((uint32_t)xy[1][1] << 16);
    q[5] = (uint32_t)uv[1][0] | ((uint32_t)uv[1][1] << 8) | (0x100u << 16);
    q[6] = (rgb[2] & 0x00FFFFFFu) | ((uint32_t)(bank >> 8) << 24);
    q[7] = (uint32_t)xy[2][0] | ((uint32_t)xy[2][1] << 16);
    q[8] = (uint32_t)uv[2][0] | ((uint32_t)uv[2][1] << 8);
    psx_mod_write_gpu_draw_memory(base, &hdr, 4);
    psx_mod_write_gpu_draw_memory(base + 4, q, sizeof q);
    /* precision suffix: magic + q[3] + xy[6] (source = base+4) */
    uint32_t suf[10];
    suf[0] = 0x48545031u;
    suf[1] = suf[2] = suf[3] = bitsf(1.0f);
    for (int i = 0; i < 3; ++i) {
        suf[4 + i * 2] = bitsf((float)xy[i][0]);
        suf[5 + i * 2] = bitsf((float)xy[i][1]);
    }
    psx_mod_write_gpu_draw_memory(base + 40, suf, sizeof suf);
}

/* Sol kenarda sabit, sağa doğru artan sinüs dalga (orijinal bayrak hissi). */
static int wave_off(int xr, int w, float phase) {
    return (int)(3.0f * ((float)xr / (float)w) * sinf(phase + (float)xr * 0.07f));
}

static uint32_t flag_col_rgb(int chosen, int col, float phase) {
    float s = 0.5f + 0.5f * sinf(phase * 1.4f - (float)col * 0.55f);
    int v = chosen ? (0xA4 + (int)(0x38 * s)) : (0x3C + (int)(0x12 * s));
    return ((uint32_t)v << 16) | ((uint32_t)v << 8) | (uint32_t)v;
}

static void build_wave(float phase, int sel) {
    const int H = TR_FLAG_H - 1;
    for (int f = 0; f < 2; ++f) {
        uint16_t bank = f ? BANK_DUB : BANK_SUB;
        int chosen = (f == 0 && sel == 3) || (f == 1 && sel == 4);
        int x = f ? 320 : 64, y = 170, w = 128, h = 64;
        for (int c = 0; c < COLS; ++c) {
            int xa = x + c * 16, xb = x + (c + 1) * 16;
            int ua = c * 16, ub = (c + 1) * 16; if (ub > 127) ub = 127;
            int oa = wave_off(xa - x, w, phase), ob = wave_off(xb - x, w, phase);
            int nA = f * (COLS * 2) + c * 2, nB = nA + 1;
            uint32_t bA = s_arena + nA * STRIDE, bB = bA + STRIDE;
            uint32_t nxB = (nB == NODES - 1) ? 0x00FFFFFFu : bB + STRIDE;
            uint32_t ca = flag_col_rgb(chosen, c, phase);
            uint32_t cb = flag_col_rgb(chosen, c + 1, phase);
            int a_xy[3][2] = {{xa, y + oa}, {xb, y + ob}, {xa, y + h + oa}};
            int a_uv[3][2] = {{ua, 0}, {ub, 0}, {ua, H}};
            uint32_t a_rgb[3] = {ca, cb, ca};
            int b_xy[3][2] = {{xb, y + ob}, {xb, y + h + ob}, {xa, y + h + oa}};
            int b_uv[3][2] = {{ub, 0}, {ub, H}, {ua, H}};
            uint32_t b_rgb[3] = {cb, cb, ca};
            put_tri(bA, bB, bank, a_xy, a_uv, a_rgb);
            put_tri(bB, nxB, bank, b_xy, b_uv, b_rgb);
        }
    }
    s_built_sel = sel;
}

static void dim_stock_active_flag(uint32_t ot) {
    uint32_t cur = ot & 0x00FFFFFFu;
    int steps = 0;
    while (cur != 0u && cur != 0x00FFFFFFu && steps++ < 4096) {
        uint32_t hdr = psx_mod_read_word(cur);
        uint32_t len = (hdr >> 24) & 0xFFu;
        uint32_t nxt = hdr & 0x00FFFFFFu;
        if (len == 12u) {
            uint32_t w0 = psx_mod_read_word(cur + 4u);
            if ((w0 >> 24) == 0x3Cu) {
                int16_t y0 = (int16_t)(psx_mod_read_word(cur + 8u) >> 16);
                if (y0 >= 70 && y0 <= 165) {
                    uint32_t w3 = psx_mod_read_word(cur + 16u);
                    uint32_t w6 = psx_mod_read_word(cur + 28u);
                    uint32_t w9 = psx_mod_read_word(cur + 40u);
                    psx_mod_write_word(cur + 4u,  (0x3Eu << 24) | ((w0 >> 1) & 0x007F7F7Fu));
                    psx_mod_write_word(cur + 16u, ((w3 >> 1) & 0x007F7F7Fu) | (w3 & 0xFF000000u));
                    psx_mod_write_word(cur + 28u, ((w6 >> 1) & 0x007F7F7Fu) | (w6 & 0xFF000000u));
                    psx_mod_write_word(cur + 40u, ((w9 >> 1) & 0x007F7F7Fu) | (w9 & 0xFF000000u));
                }
            }
        }
        cur = nxt;
    }
}

/* DrawOTag wrap: bayrak ekranındayken sahne OT'sine TR node'larını ekle. */
static int drawotag_wrap(struct CPUState *cpu) {
    if (!s_arena || !in_flag_menu()) return 0;
    uint32_t ot = cpu->gpr[4] & 0x00FFFFFFu;
    uint32_t probe = ot;
    int cnt = 0;
    while (probe != 0u && probe != 0x00FFFFFFu && cnt < 4) {
        probe = psx_mod_read_word(probe) & 0x00FFFFFFu;
        cnt++;
    }
    if (cnt < 4) return 0; /* 1 node'luk clear OT'ye ekleme */
    if (s_built_sel != s_sel) build_wave(s_phase, s_sel);
    if (s_sel >= 3) dim_stock_active_flag(ot);
    uint32_t hdr = (9u << 24) | ot;
    psx_mod_write_gpu_draw_memory(s_arena + LAST_OFF, &hdr, 4);
    cpu->gpr[4] = s_arena;
    func_override_call_original(cpu);
    return 1;
}

static void play_click_sfx(struct CPUState *cpu) {
    struct CPUState saved = *cpu;
    psx_mod_write_word(SFX_PARAM_ADDR, 9u);
    psx_mod_write_half(SFX_PARAM_ADDR + 0xEu, 0xFFFFu);
    psx_mod_write_word(SFX_PARAM_ADDR + 0x10u, 0x7Fu);
    cpu->pc = 0u;
    cpu->gpr[4] = 0u;
    cpu->gpr[5] = 1u;
    cpu->gpr[6] = SFX_PARAM_ADDR;
    func_override_guest_call(cpu, SFX_PREP_FN, saved.gpr[31]);
    cpu->pc = 0u;
    cpu->gpr[4] = 0u;
    cpu->gpr[5] = SFX_PARAM_ADDR;
    func_override_guest_call(cpu, SFX_PLAY_FN, saved.gpr[31]);
    *cpu = saved;
}

static int flag_menu_wrap(struct CPUState *cpu) {
    if (!in_flag_menu()) return 0;

    uint32_t edge = psx_mod_read_word(PAD_EDGE);
    uint32_t stock_lang = psx_mod_read_word(LANG_ADDR);
    if (stock_lang > 2u) stock_lang = 0u;

    if (s_sel < 3) {
        s_sel = (int)stock_lang;
        if (edge & PAD_DOWN) {
            s_last_stock = s_sel;
            s_sel = (s_last_stock == 2) ? 4 : 3;
            psx_mod_write_word(LANG_ADDR, 0u);
            psx_mod_write_word(PAD_EDGE, edge & ~(PAD_DOWN | PAD_LEFT | PAD_RIGHT | PAD_CROSS));
            play_click_sfx(cpu);
            func_override_call_original(cpu);
            psx_mod_write_word(PAD_EDGE, edge);
            return 1;
        }
        if (edge & PAD_CROSS) set_tr_mode(0);
        func_override_call_original(cpu);
        uint32_t next_lang = psx_mod_read_word(LANG_ADDR);
        if (next_lang <= 2u) s_sel = (int)next_lang;
        return 1;
    }

    if (edge & PAD_UP) {
        s_sel = s_last_stock;
        psx_mod_write_word(LANG_ADDR, (uint32_t)s_sel);
        psx_mod_write_word(PAD_EDGE, edge & ~(PAD_UP | PAD_LEFT | PAD_RIGHT | PAD_CROSS));
        play_click_sfx(cpu);
        func_override_call_original(cpu);
        psx_mod_write_word(PAD_EDGE, edge);
        return 1;
    }
    if (edge & (PAD_LEFT | PAD_RIGHT)) {
        s_sel = (s_sel == 3) ? 4 : 3;
        psx_mod_write_word(PAD_EDGE, edge & ~(PAD_LEFT | PAD_RIGHT | PAD_CROSS));
        play_click_sfx(cpu);
        func_override_call_original(cpu);
        psx_mod_write_word(PAD_EDGE, edge);
        return 1;
    }
    if (edge & PAD_CROSS) {
        set_tr_mode((s_sel == 3) ? 1 : 2);
        psx_mod_write_word(LANG_ADDR, 0u);
        func_override_call_original(cpu);
        return 1;
    }

    psx_mod_write_word(PAD_EDGE, edge & ~(PAD_LEFT | PAD_RIGHT | PAD_CROSS));
    func_override_call_original(cpu);
    psx_mod_write_word(PAD_EDGE, edge);
    return 1;
}

static void tr_reset(void) {
    close_tr_disc();
    s_sel = 0;
    s_last_stock = 0;
    s_built_sel = -1;
    s_active = 0;
    s_phase = 0.0f;
}

static void tr_activate(void) {
    tr_reset();
    psx_mod_define_texture_bank(BANK_SUB, TR_FLAG_W, TR_FLAG_H, tr_flag_sub);
    psx_mod_define_texture_bank(BANK_DUB, TR_FLAG_W, TR_FLAG_H, tr_flag_dub);
    psx_mod_set_disc_sector_patcher(tr_patch_sector);
    s_arena = psx_mod_alloc_texture_packet_memory(ARENA_BYTES, 16);
    if (s_arena) build_wave(0.0f, s_sel);
    fprintf(stdout, "tr_flag_menu: active arena=%08x\n", s_arena);
    fflush(stdout);
}

static void tr_vblank(void) {
    int on = psx_mod_game_started() && s_arena && in_flag_menu();
    if (on) {
        s_phase += 0.12f;
        build_wave(s_phase, s_sel); /* dalga + vurgu durumunu güncelle */
        if (!s_active) {
            psx_mod_set_host_gpu_draw_range(0, s_arena, ARENA_BYTES);
            s_active = 1;
        }
    } else if (s_active) {
        psx_mod_set_host_gpu_draw_range(0, 0, 0);
        s_active = 0;
    }
}

static int tr_cmd(const char *args, char *reply, int cap) {
    (void)args;
    return snprintf(reply, cap, "active=%d sel=%d mode=%d arena=%08x flag=%u state=%u sub=%u",
                    s_active, s_sel, s_tr_mode, s_arena,
                    psx_mod_read_word(FLAG_ACTIVE),
                    psx_mod_read_word(FE_STATE),
                    psx_mod_read_word(FLAG_SUBSTATE));
}

PSX_MOD_CONSTRUCTOR(register_tr_flag_menu) {
    psx_mod_register_activation_plugin("hp2.tr-flag-menu", tr_activate);
    psx_mod_register_session_reset_plugin("hp2.tr-flag-menu", tr_reset);
    psx_mod_register_vblank_plugin("hp2.tr-flag-menu", tr_vblank);
    psx_mod_register_command("trflag", tr_cmd);
    /* Constructor'da kaydol: plan resolution'da ARM edilir (activation'dan önce). */
    psx_mod_register_function_override("hp2.tr-flag-menu:drawotag", DRAW_OTAG,
                                       drawotag_wrap, NULL, 0, FO_CREDIT_SELF);
    psx_mod_register_function_override("hp2.tr-flag-menu:flagmenu", FLAG_MENU_FN,
                                       flag_menu_wrap, NULL, 0, FO_CREDIT_SELF);
}
