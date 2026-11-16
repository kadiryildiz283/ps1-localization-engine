# Harry Potter and the Chamber of Secrets (PS1) — Native Linux Portu

Emülatör kullanmayan, doğrudan orijinal PS1 disk dökümü (`POTTER.DIR` / `POTTER.DAT`) ve çıkarılmış varlıklar (`build_assets/`) üzerinde çalışan **C11 + SDL2 + OpenGL** native Linux oyun motoru.

## Derleme ve Çalıştırma

```bash
cd linux_port
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j4

# Tüm 78 WAD seviyesini ve 7.239 diyaloğu doğrula
./hp2_linux --test-all

# Oyunu / 3B seviye motorunu başlat (varsayılan: T1L2M001.WAD - Kovuk Bahçesi)
./hp2_linux
./hp2_linux T1L1M000.WAD
```

## Kontroller

| Tuş | İşlev |
|---|---|
| `W / A / S / D` veya Ok Tuşları | İleri / Geri / Sağa / Sola hareket |
| `Q / E` | Aşağı / Yukarı |
| `Shift` | Hızlı hareket |
| `Fare` (Sol tık sürükle veya `M` kilidi) | Kamera bakışı |
| `[` / `]` | Önceki / Sonraki seviye (78 WAD) |
| `Space` | Seviyedeki sıradaki ses (`WAV`) ve diyaloğu (`LPSX`) oynat |
| `R` | Kamerayı seviye merkezine sıfırla |
| `Tab` | HUD panelini aç/kapat |
| `Esc` | Çıkış |

## Dizin Yapısı

- `src/`, `include/`: C11 + SDL2 + OpenGL motoru (`dpsx.c`, `lpsx.c`, `audio_spu.c`, `render_gl.c`, `main.c`). Motor disc OKUMAZ; tüm assetleri `build_assets/` altındaki statik dosyalardan çağırır.
- `re/`: Python tersine mühendislik ve varlık dönüştürücüleri (`extract_all.py`, `textures.py`, `audio.py`, `str_video.py`, `level_geom.py`, `dem.py`)
- `analysis/`: `EURO1.GAM` statik analiz araçları (`mipsa.py`, `euro1_strings.txt`)
- `docs/`: Format ve mimari dokümantasyonu (`CONTEXT.md`, `formats/STR_VIDEO.md`)
- `dump/` (`.gitignore`): Orijinal PS1 disk dökümü (yalnızca çıkarım için kaynak; motor ihtiyaç duymaz)
- `build_assets/` (`.gitignore`): Çıkarılmış statik assetler (aşağıya bkz.)

## Statik Asset Hattı

`python re/extract_all.py` tüm oyun assetlerini `build_assets/`'a çıkarır; motor bunlardan çağırır:

| Klasör | İçerik | Motor kullanımı |
|---|---|---|
| `textures/IMG/*.png`, `textures/WAD/<w>/` | 246 IMG çizimi + 78 WAD doku bankası (`tpsx.bin`) | `tpsx_load` ← `tpsx.bin` |
| `levels/<w>/` | 78 map: `dpsx.bin` + okunabilir `mesh.obj` | `dpsx_load` ← `dpsx.bin` |
| `dialogues/<w>.json` + `<w>/lpsx.bin` | 78 diyalog tablosu (EN/FR/DE, 7.239 kayıt) | `lpsx_load` ← `lpsx.bin` |
| `audio/WAD/<w>/*.wav`, `audio/XA/*.wav` | 8.658 ses + XA müzik | `audio_play_wav` ← WAV |
| `video/*.rgb` (+`*.png`) | 100 STR karesi (ham RGB) + manifest | title intro `gl_video_frame` |
| `animations/<d>.json` + `.bin` | 11 DEM replay/kamera pisti | attract kamera ← `.bin` |
| `wads.txt` | 78 seviye kök adı | seviye listesi |

Doğrulama: `./hp2_linux --test-all` → `ok=78 fail=0 total_dialogues=7239` (disc olmadan, yalnız `build_assets` ile de çalışır).
