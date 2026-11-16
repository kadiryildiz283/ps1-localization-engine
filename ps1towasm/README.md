# ps1towasm

Final PS1 `.bin`/`.cue` disk imajlarını (2352 bayt/sektör Mode 2 Form 1/2 XA dahil) doğrudan web tarayıcısında (PC ve mobil) çalışabilen statik bir WebAssembly (`pcsx_rearmed`) paketine dönüştüren araç zinciri. (İlgili issue: [#5](https://github.com/kadiryildiz283/ps1-localization-engine/issues/5))

---

## Mimari ve Özellikler

- **Ham 2352 Bayt Sektör Koruması ([cue_iso.py](cue_iso.py)):** `.cue` track düzenini ayrıştırır, sektör 16 ISO9660 PVD ve `SYSTEM.CNF` (`BOOT` executable) doğrulaması yapar; Mode 2 Form 1 ve Form 2 (`0xA800` XA ses akışları) verisini kayıpsız korur.
- **İki Web Akış Modu ([compiler.py](compiler.py), [web/runtime.js](web/runtime.js)):**
  - `range` (**önerilen**): Açılışta tüm diski indirmez. Emscripten `FS.createDataFile` üzerine kurulu `mountRangeDiscFile()` katmanı sayesinde yalnızca okunan 512 KiB blokları `HTTP 206 Partial Content` ile talep üzerine çeker (RAM'de en fazla ~16 MiB önbellek tutar).
  - `chunked`: Diski SHA-256 doğrulamalı ~2 MiB'lık parçalara (`chunks/chunk_XXXX.bin`) böler.
- **Web Çalışma Zamanı ([web/index.html](web/index.html), [web/runtime.js](web/runtime.js)):**
  - `Nostalgist.js` (`pcsx_rearmed` WASM) ile tarayıcıda tam ekran (`100vw × 100dvh`) çalışır; `canvas#screen` boyutu `devicePixelRatio` geri besleme döngüsüne karşı kilitlidir.
  - Mobilde ve PC'de ekran üzeri çoklu dokunmatik PS1 kontrolcüsü (`D-Pad`, `△ ○ ✕ □`, `L1/L2/R1/R2`, `SELECT/START`), yüzen HUD (`⏸`, `💾`, `📂`, `🎮`, `⛶`) ve `audio_latency: 160` ses tamponu ayarı içerir.
- **COOP/COEP & Range Sunucusu ([server.py](server.py), [web/coi-serviceworker.js](web/coi-serviceworker.js)):** `SharedArrayBuffer` başlıkları (`Cross-Origin-Opener-Policy: same-origin`, `Cross-Origin-Embedder-Policy: require-corp`) ve `HTTP Range` (`206`) desteği sunar.

---

## Kullanım

```bash
# 1. Disk imajını ve SYSTEM.CNF bilgisini doğrula
python3 -m ps1towasm inspect \
  --bin "Harry Potter and the Chamber of Secrets (Turkish).bin" \
  --cue "Harry Potter and the Chamber of Secrets (Turkish).cue"

# 2. Oynadıkça akış (Range) modunda web paketi üret
python3 -m ps1towasm build \
  --bin "Harry Potter and the Chamber of Secrets (Turkish).bin" \
  --cue "Harry Potter and the Chamber of Secrets (Turkish).cue" \
  --bios emulator/bios/scph1001.bin \
  --mode range \
  --out ps1towasm/dist

# 3. Yerel ağda / PC'de sun
python3 -m ps1towasm serve ps1towasm/dist --host 0.0.0.0 --port 8080
```

Ardından tarayıcıda `http://127.0.0.1:8080` (veya aynı ağdaki telefondan `http://<LAN-IP>:8080`) adresini açın.

---

## Klavye Eşlemesi

| PS1 Tuşu | Klavye |
|---|---|
| D-Pad | Ok Tuşları (`ArrowUp/Down/Left/Right`) |
| `✕` / `○` / `□` / `△` | `Z` / `X` / `A` / `S` |
| `L1` / `R1` / `L2` / `R2` | `Q` / `W` / `1` / `2` |
| `START` / `SELECT` | `Enter` / `Sağ Shift` |

---

## Test ve Doğrulama

```bash
ruff check ps1towasm tests/test_ps1towasm.py
ruff format --check ps1towasm tests/test_ps1towasm.py
python3 -m unittest tests/test_ps1towasm.py -v
```

> **Telif Notu:** `ps1towasm/dist/`, `.bin`, `.cue` ve BIOS dosyaları `.gitignore` kapsamındadır; yalnızca kaynak kod ve web kabuğu depoya eklenir.
