# PORT STATUS — HP2 PS1 → Native Linux (PSXRecomp omurgalı)

Son güncelleme: 2026-11-15. Karar ve kanıt issue'su: **#6**
(feat(port): PSXRecomp tabanlı native Linux portu). Strateji kullanıcı
onaylı: PSXRecomp omurga, `linux_port/` asset/referans hattı olarak korunur.

## 1. Doğrulanmış baseline (2026-11-15)

- `linux_port/` (C11+SDL2+OpenGL asset motoru): yeniden derlendi,
  `./hp2_linux --test-all` → `WAD test: ok=78 fail=0 total_tris=604426
  total_dialogues=7239`. Bu motor orijinal MIPS mantığını ÇALIŞTIRMAZ;
  oyun mantığı elle yeniden inşa edilmiştir. Tam oynanabilirlik kapısı
  için recompilation hattı gereklidir.
- `ps1towasm/`: tarayıcı emülasyon paketleyicisi (issue #5), ayrı deliverable.
- Disk: orijinal Avrupa `.bin/.cue` repo kökünde (715.207.920 bayt,
  MD5 `f573f8b4d5fe381c09ad99da8617c038`). `linux_port/dump/` 1,2 GB
  çıkarılmış varlık (POTTER.DIR/DAT, 81 WAD, EA.STR, 40MEG.RAW).

## 2. PSXRecomp uyumluluk kanıtı

- Framework: `psxrecomp/` clone `b263b855` (nightly). PolyForm
  Noncommercial 1.0.0 + PERMISSIONS.md (ücretsiz erişim + bağış/reklam
  serbest). Repo MIT → psxrecomp MIT ağacına GÖMÜLMEZ; ayrı checkout.
- `psxrecomp-analyze` bu makinede derlendi (gcc 16.2.1, cmake 4.5,
  Ninja, `-DPSXRECOMP_ENABLE_CHD=OFF`, sıfır hata).
- EURO1.GAM: **1644 fonksiyon, %86.0 kapsama, 22 jump table (973 hedef),
  108 çözülmemiş indirect**; load `0x00010000`, entry `0x00060B54`,
  size `0x6E000` (KUSEG — framework açıkça destekli, Kula World emsali).
- SLES_039.72: **281 fonksiyon, %80.9 kapsama, 3 jump table (171 hedef)**;
  load `0x00100000`, entry `0x00105130`, size `0x11800`.
- Çıktılar: `analysis/functions/{EURO1,SLES_039}/` (yerel; telifli
  türev disassembly — commit EDİLMEZ).
- REA notu: REA MCP PS-X EXE açmıyor (linux_port/docs/CONTEXT.md kaydı);
  fonksiyon haritasını psxrecomp-analyze sağlıyor.

## 3. hp2recomp oyun projesi (kuruldu, derlendi, boot etti)

Dizin: `hp2recomp/`. Framework `hp2recomp/psxrecomp` symlink → `../psxrecomp`
(submodule yerine yerel checkout; CMake `PSXRECOMP_ROOT` REALPATH'e çözülür —
Ninja çift-yol çakışması düzeltmesi).

- `game.toml`: probe_disc.py üretimi; disc hash'leri pinli, KUSEG link
  segmenti korunmuş, `[runtime] overlay_cache = true`.
- `seeds/ghidra_funcs.txt`: 224 JAL seed (probe).
- Generate: OpenBIOS `emitted=651 instructions=17526`;
  SLES_039.72 → **332 fonksiyon, 204.107 satır C, 6 shard + dispatch**.
- **EURO1.GAM → statik C (2026-11-15):** `psxrecomp-game EURO1.GAM --strict`
  → **2228 fonksiyon, 1.386.775 satır C, 39 shard, 2217 dispatch**, tamamı
  KUSEG (`func_00010000`... §5.3 link-segment native). Çıktı:
  `hp2recomp/generated_euro1/` (yerel, telifli türev — gitignore).
  NOT: bu tam C referans/arşivdir; runtime'a linkli değil (main-exe formatı).
- **Statik native overlay LİNKLENDİ ve doğrulandı (2026-11-16):**
  Runtime capture'ları (`build/overlay_captures.json`, KUSEG schema v3)
  `compile_overlays.py --static` ile `aot_static/overlays_static.c` + 16 shard
  TU'ya derlendi (14 shard OK, 12991 identity). `GAME_OVERLAY_STATIC_C` ile
  linklendi. Ölçüm (`overlay_loader_status`, frame 13986):
  `static_hits=11.046.716`, `static_address_misses=2.570.740`,
  `static_crc_misses=3`, `variant_misses=3`. Kabaca overlay dispatch'lerin
  ~%80'i native; kalanı interpreter fallback (kapsanmamış adresler).
  **%100 native DEĞİL** — kapsama = capture edilen boot/menu kodu; oynanışla
  birikir. Ekran doğrulandı: memory card seçim ekranına ilerledi (OCR).
  - **CMake dersi:** `GAME_OVERLAY_STATIC_C` wrapper'da parse edilmez;
    `GEN_FULL_GLOB` (çok-değerli) sonrasına yazılırsa onun değeri olarak
    yutulur. `GEN_*` argümanlarından ÖNCE yazılmalı.
  - AOT static pipeline KSEG0-only (`RAM_WINDOW`); KUSEG shard'lar
    `compile_overlays.py --static` + runtime capture ile üretilir.
  - `PSX_NATIVE_CPU_SPANS` açık bırakıldı (dispatcher doğru yoldan gelince
    span kontrolü sadece SLES C'sine bakar, geçiyor).
- Build: `cmake -S hp2recomp -B hp2recomp/build -G Ninja
  -DCMAKE_BUILD_TYPE=Release -DPSX_REWIND=OFF` → 292 adım, temiz.
  Binary: `build/Harry_Potter_and_the_Chamber_of_Secrets_Recompiled`.
  (Rewind kapalı: rbengine submodule yok; netplay zaten OFF.)

### Boot kanıtı (headless-opengl + TCP debug 4731)

- OpenBIOS LLE + boot-skip HLE → SLES → EURO1.GAM overlay yüklendi:
  `read_ram(0x00010000,64) == EURO1.GAM payload` → **True** (bayt düzeyi).
- GPU: 512×256×15bit, 772K+ draw, aktif 3D; CD: 3.981+ sektör,
  WAD akışı (LBA 29228 civarı, mode 0xA0).
- Ekran: `hp2recomp/boot_01.png` — dil seçim ekranı (OCR "Select"),
  %93.3 non-black, 822 renk. Gerçek oyun ekranı, placeholder değil.
- Overlay native derleme YOK (TCC toolchain staged değil) → EURO1.GAM
  interpreter'da (`disp_interp=144359, disp_native=0`). Doğru ama yavaş.

## 4. P0 BLOCKER — ÇÖZÜLDÜ (deterministik wedge, frame 13624)

Belirti: boot'tan ~2 dk sonra %99.5 CPU, TCP debug "emu busy or frozen".
İki koşuda da aynı frame 13624, guest PC `0x0006B5A0` (CD DRQSTS poll).

### Kök neden (kanıtlı)

Guest CD sürücüsü kesmeleri kapalı (SR IEc=0) polled DMA yolu kullanıyor:
`0x6B514` fonksiyonu BFRD=0x80 set edip DRQSTS (status bit 6) bekliyor.
Oyun deseni: `SetLoc → ReadN` (bazen +Pause), iki akış dönüşümlü
(~900 sektör arayla, 8 sektör/burst), `irq_flag=0x03` (INT3 ack'lanmamış).

Framework'te sektör verisi ring buffer'a okunuyor ama RB_ FIFO'suna
(DRQSTS'yi besleyen) yalnızca INT1 "data-ready" sunumunda yükleniyordu;
INT1 sunumu ise önceki INT'in ack'lanmasını bekliyordu
(`present_pending_dataready`, `irq_flag==0` şartı). Guest ack'lamadan
DRQSTS beklediği için deadlock: veri ring'de var, FIFO boş, guest sonsuz
dönüyor. 200ms çözünürlüklü TCP poll (`cdrom_command_history` +
`cdrom_sector_history`) geçiş anını yakaladı: son komut SetLoc+ReadN
(f13616), sektör akışı duruyor, guest spin. gdb (RelWithDebInfo) ölçümü
host tarafının sağlıklı olduğunu doğruladı: cycle gap 23-694 (küçük),
sayaç 5 sn'de 1.65 milyar ilerliyor → host değil guest spin.

Gerçek donanımda DRQSTS bir donanım status bitidir; IRQ bildiriminden
bağımsız olarak veri FIFO'sunu yansıtır. Framework'ün ack-gate'i Final
Bout gibi "ack'layıp sonra eski slot'u okuyan" oyunlar için doğru,
HP2'nin polled yolu için yanlış.

### Düzeltme (opt-in quirk, framework checkout'ında yerel)

`psxrecomp/runtime/src/cdrom.c` — `process_read_stream` pended INT1
dalında (`s_int1_pended++` sonrası): `PSX_CD_EXPOSE_PENDING_FIFO=1`
env değişkeniyle, BFRD set ise yeni okunan slot hemen FIFO'ya açılır
(`s_ring_read = s_ring_write; load_data_fifo(0)`). Varsayılan davranış
değişmez (Final Bout güvenli). ~20 satır, geri alınabilir.

### Doğrulama (quirk açık, headless-opengl)

- Frame **32183** → wedge noktası 13624 aşıldı (2.4x), TCP yanıt veriyor,
  SR IEc=1 (kesmeler açık, sağlıklı).
- Ekran zinciri (OCR kanıtlı): dil seçim ("Select") → title
  ("CHAMBER/SECRETS", "© 2002 Electronic Arts Inc.") → ana menü
  ("Start Game") → **Demo Mode: Quidditch 3D sahne + spiker metni**
  ("..important Quidditch game between Slytherin and Gryffindor..").
- TCP input injection çalışıyor (`set_input buttons=48127 layer=host`
  = Cross; `clear_input`). Menü geçişleri tuşla doğrulandı.
- Kanıt görüntüleri (yerel, telifli): `hp2recomp/boot_01.png`,
  `quirk_01..03.png`.

Denenen ama etkisiz olan: `idle_skip=true` (döngü MMIO read içeriyor).
perf paranoid=2 engelli; gdb parent-child ptrace ile çalıştı.

### Kalıcılaştırma notu

Quirk şu an env değişkeniyle (`PSX_CD_EXPOSE_PENDING_FIFO=1`).
Framework'e `[runtime]` config knob'u olarak taşınması ve upstream
PR'ı (Final Bout regresyon testiyle) follow-up işidir.

## 5. Komutlar

```bash
# Analiz
./psxrecomp/recompiler/build/psxrecomp-analyze <EXE> --out analysis/functions/<AD>

# Codegen (mutlak disc yolu!)
python3 psxrecomp/psxrecomp_cli.py generate --config hp2recomp/game.toml \
  --project-root hp2recomp --disc "/home/kadir/Projeler/PS1-Localization-Engine/Harry Potter and the Chamber of Secrets (Europe) (En,Fr,De).cue"

# Build
cmake -S hp2recomp -B hp2recomp/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DPSX_REWIND=OFF
cmake --build hp2recomp/build --target psx-runtime -j4

# Çalıştır (CWD=hp2recomp; disc/ orada; quirk ZORUNLU — bkz. §4)
cd hp2recomp && PSX_DEBUG_SERVER=1 PSX_CD_EXPOSE_PENDING_FIFO=1 \
  build/Harry_Potter_and_the_Chamber_of_Secrets_Recompiled \
  --headless-opengl --debug-port 4731

# TCP debug
python3 psxrecomp/tools/debug_client.py --port 4731 frame
python3 psxrecomp/tools/debug_client.py --port 4731 screenshot boot.png
python3 psxrecomp/tools/debug_client.py --port 4731 cdrom_command_history count=8
```

## 6. Lisans ve telif

- psxrecomp: PolyForm NC 1.0.0 — MIT repo ağacına gömülmez; birleşik
  binary NC lisanslı dağıtılır (ücretsiz erişim şartı). Dağıtım notlarına
  NC bildirimi + OpenBIOS MIT notices eklenmeli.
- `analysis/`, `hp2recomp/generated/`, `hp2recomp/disc/` telifli türev
  içerir → `.gitignore` kapsamında, commit edilmez.
- Orijinal ISO/BIOS/asset commit edilmez (AGENTS.md).

## 7. Sıradaki işler (öncelik sırası)

1. Quirk'i `[runtime]` config knob'u olarak framework'e taşı + upstream
   PR (Final Bout regresyon testiyle). Şu an env: `PSX_CD_EXPOSE_PENDING_FIFO=1`.
2. Menü → yeni oyun → bölüm ilerlemesi doğrulaması (input injection ile;
   DuckStation oracle referans için kurulabilir, `tools/duckstation_oracle.py`).
3. Overlay native derleme hattı (TCC toolchain stage veya gcc dev path)
   — interpreter doğru ama oyun içi performans için gerekli.
4. `docs/GAMEPLAY_COVERAGE.md` bölüm bazlı kayıt.
5. Türkçe dublaj entegrasyonu (psxmod / disc-overlay; linux_port hattı).
