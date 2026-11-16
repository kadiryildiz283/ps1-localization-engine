# DİZİN HARİTASI — Hangi dizinde ne var?

Bu repo üç iş kolu (workstream) + ortak RE hattı içerir. Karışıklığı gidermek
için her dizinin rolü aşağıda. Telifli varlıklar (`.bin`, `.WAD`, ses, üretilmiş
oyun C'si) repoya girmez; yerel kalır (`.gitignore`).

## Kök dizin — iş kolları

| Dizin | Rol | Not |
|-------|-----|-----|
| `hp2recomp/` | **Native port** (PSXRecomp ile MIPS→C). Asıl port projesi. | aşağıda detay |
| `psxrecomp/` | PSXRecomp framework checkout'ı ( PolyForm NC, ayrı git). | MIT ağacına gömülmez |
| `ps1towasm/` | Tarayıcı emülasyon paketleyicisi (pcsx_rearmed WASM, issue #5). | ayrı deliverable |
| `tools/` | **Dublaj/lokalizasyon hattı** Python araçları (44 script). | inject, build, synthesize |
| `translations/` | EN→TR diyalog JSON'ları (78 bölüm) + UI metinleri. | dublaj metni |
| `audio/` | Dublaj manifestleri (ses binary'leri depoya girmez). | classified/dubbing manifest |
| `docs/` | Proje dokümanları (PORT_STATUS, GAMEPLAY_COVERAGE, bu harita, ARGONAUT). | |
| `analysis/` | psxrecomp-analyze fonksiyon haritaları (EURO1, SLES_039). | telifli türev, yerel |
| `tests/` | Pytest testleri (dublaj hattı + ps1towasm). | |
| `extracted/` | Full-dub patch'lenmiş asset'ler (POTTER.DAT içeriği). | 506M, yerel |
| `extracted_text_only/` | Sadece-altyazı patch'lenmiş asset'ler. | 505M, yerel |
| `emulator/`, `rea/`, `scratch/` | Kullanıcı çalışma dizinleri (bu oturumda oluşturulmadı). | dokunulmadı |

## Kök dosyalar

| Dosya | Rol |
|-------|-----|
| `engine.py` | Dublaj hattı CLI (dump-ui / dump-dialogue / build-ui / build-iso). |
| `pyproject.toml` | Python paket + bağımlılıklar (ruff, pytest). |
| `Harry Potter...(Europe) (En,Fr,De).bin/.cue` | **Orijinal disk** (715MB). Portun kaynağı. |
| `Harry Potter...(Turkish).bin/.cue` | Full-dub patch'li disc (TR metin + TR ses). |
| `Harry Potter...(Turkce Altyazi).bin/.cue` | Sadece-altyazı patch'li disc (TR metin + EN ses). |
| `AGENTS.md`, `README.md`, `REVERSE_ENGINEERING_GUIDE.md` | Kurallar + rehber. |
| `BURROW_GARDEN_REMEDIATION.md` | Kovuk Bahçesi enjeksiyon referansı (Kategori A kapısı). |

## hp2recomp/ — native port projesi (detay)

```
hp2recomp/
├── game.toml              # Oyun config: disc yolu, hash'ler, [runtime] ayarları
├── CMakeLists.txt         # Build tanımı (psxrecomp_add_game_runtime)
├── seeds/ghidra_funcs.txt # 224 JAL fonksiyon seed'i (probe üretimi)
├── catalog_identity.json  # Disc kimlik metadata (probe)
├── disc_probe.json        # Disc probe çıktısı (header, LBA, digest)
├── psxrecomp@             # → ../psxrecomp symlink (framework)
│
├── generated/             # SLES_039.72 boot loader C (332 fonksiyon, 204K satır)
│   ├── SLES_039.72_dispatch.c
│   └── SLES_039.72_full_*.c
├── generated_euro1/       # EURO1.GAM tam C (2228 fonksiyon, 1.39M satır, KUSEG)
│   ├── EURO1.GAM_dispatch.c   # REFERANS — runtime'a linkli DEĞİL
│   └── EURO1.GAM_full_*.c     # (psxrecomp-game doğrudan çıktı)
├── aot_static/            # ★ Runtime'a LİNKLİ statik native overlay shard'ları
│   ├── overlays_static.c      # dispatcher (GAME_OVERLAY_STATIC_C bunu gösterir)
│   └── overlays_static_NNNN.c # 16 shard TU (KUSEG/KSEG1 dahil, capture'dan)
│
├── build/                 # Build çıktısı + ÇALIŞTIRILABİLİR binary
│   └── Harry_Potter_and_the_Chamber_of_Secrets_Recompiled
├── disc/                  # Stage'lenmiş disc kopyası (normalize cue+bin, 683M)
├── saves/                 # Memory card (card1.mcd, card2.mcd)
├── tools/level_monitor.py # Bölüm geçiş logger'ı (CD sektör→WAD→T1Lx)
└── debug/                 # Geçici debug log/capture (gitignore)
```

### Üretilmiş C dizinleri arasındaki fark (önemli)

- `generated/` = **SLES boot loader** C'si. Runtime'a linkli (GEN_FULL_GLOB).
- `generated_euro1/` = **EURO1.GAM'ın TAMAMI** (2228 fonksiyon). Doğrudan
  `psxrecomp-game EURO1.GAM` çıktısı. **Referans/arşiv** — runtime'a linkli
  değil (main-exe formatı, overlay shard değil).
- `aot_static/` = **Runtime'a linkli native overlay** shard'ları. Runtime
  capture'larından `compile_overlays.py --static` ile üretildi. KUSEG/KSEG1
  segmentli. **Şu an kapsanan kod = boot/menu/demo** (capture edilen ~60KB);
  kalanı interpreter fallback. `GAME_OVERLAY_STATIC_C` burayı gösterir.

## Çalıştırma

```bash
cd hp2recomp
PSX_DEBUG_SERVER=1 PSX_CD_EXPOSE_PENDING_FIFO=1 \
  build/Harry_Potter_and_the_Chamber_of_Secrets_Recompiled --debug-port 4731
```
`PSX_CD_EXPOSE_PENDING_FIFO=1` ZORUNLU (CD DRQSTS wedge quirk'i, PORT_STATUS §4).

## Build

```bash
cmake -S hp2recomp -B hp2recomp/build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DPSX_REWIND=OFF
cmake --build hp2recomp/build --target psx-runtime -j4
```

## Statik overlay yeniden üretimi (capture birikince)

```bash
# Oyunu oynat → build/overlay_captures.json birikir (KUSEG entry'ler)
python3 psxrecomp/tools/compile_overlays.py --static \
  --captures hp2recomp/build/overlay_captures.json \
  --game-toml hp2recomp/game.toml \
  --recompiler psxrecomp/recompiler/build/psxrecomp-game \
  --runtime-include psxrecomp/runtime/include \
  --project-root hp2recomp --out-dir hp2recomp/aot_static --gcc gcc --target-os linux
# sonra yeniden build → daha çok kod native
```
