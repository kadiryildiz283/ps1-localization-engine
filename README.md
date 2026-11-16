# PS1 Localization Engine

**Harry Potter and the Chamber of Secrets (PlayStation 1, Argonaut Games, 2002) için Türkçe yerelleştirme motoru, native port ve web paketleme araç seti.**

Bu depo dört ana iş kolunu bir arada barındırır:

1. **Dublaj ve Yerelleştirme Hattı (`tools/`, `engine.py`):** PS1 disk imajından metin çıkarma, çeviri yönetimi, sinir ağı tabanlı dublaj sentezi, Sony ADPCM (VAG) enjeksiyonu ve CD-ROM XA (Mode 2 Form 1) sektör yeniden inşası.
2. **PSXRecomp Native Port (`hp2recomp/`):** `SLES_039.72` + `EURO1.GAM` statik/dinamik MIPS→C derlemesi, runtime ve dil seçim ekranı için Türkçe bayrak menüsü modu (`hp2.tr-flag-menu`).
3. **Native Linux C Motoru (`linux_port/`):** Emülatör olmadan çıkarılmış varlıklar üzerinde çalışan C11 + SDL2 + OpenGL seviye/diyalog/ses motoru ve format RE araçları.
4. **Tarayıcı WASM Paketleyicisi (`ps1towasm/`):** Final `.bin`/`.cue` imajlarını `HTTP 206 Range` veya `chunked` akış modlarıyla tarayıcıda (`pcsx_rearmed` WASM) çalıştırılabilir statik web paketine dönüştüren araç zinciri.

> **Önemli:** Bu depo yalnızca **araç kodu, dokümantasyon, çeviriler ve metadata**
> içerir. Oyunun disk imajları, WAD dosyaları, ham sesleri, üretilmiş oyun C'si ve
> çalıştırılabilirleri telifli varlıklardır ve asla commit edilmez.

---

## Durum

| Alan | Durum |
|---|---|
| ISO / POTTER.DAT / WAD-LPSX okuma | ✅ Üretimde |
| UI & diyalog metin çıkarıcı | ✅ Üretimde |
| EN→TR çeviri hattı (~1.712 replik) | ✅ |
| XTTS-v2 karakter ses profilleri (11 karakter) | ✅ |
| Sony ADPCM kodlayıcı (Python + C) | ✅ |
| CD-ROM XA sektör yamalayıcı (EDC/ECC) | ✅ |
| `ps1towasm` tarayıcı WASM paketleyici (`range` / `chunked`) | ✅ |
| `linux_port` asset-tabanlı C11 + SDL2 + OpenGL motoru | ✅ 78 WAD / 7.239 diyalog doğrulandı |
| `hp2recomp` PSXRecomp native port + TR bayrak menüsü modu | 🚧 Boot / menü / demo doğrulandı ([PORT_STATUS](docs/PORT_STATUS.md)) |
| Multi-cue / 0xA800 split-stream enjeksiyonu | ⚠️ Yalnızca T1L2M001 doğrulandı |
| Karakter eşleştirme (speaker-id) | ⚠️ Havuz tabanlı, kritik repliklerde hatalı |
| Tam oyun dublajı | 🚧 Devam ediyor |

Detaylı dizin haritası ve iş kolları için: [docs/DIRECTORY_MAP.md](docs/DIRECTORY_MAP.md),
[docs/PORT_STATUS.md](docs/PORT_STATUS.md), [docs/GAMEPLAY_COVERAGE.md](docs/GAMEPLAY_COVERAGE.md).
Ses enjeksiyonu kök neden analizi için: [BURROW_GARDEN_REMEDIATION.md](BURROW_GARDEN_REMEDIATION.md)
ve [docs/ARGONAUT_STREAM_SPLIT_ARCHITECTURE.md](docs/ARGONAUT_STREAM_SPLIT_ARCHITECTURE.md).

---

## Hızlı Başlangıç

```bash
git clone https://github.com/kadiryildiz283/ps1-localization-engine.git
cd ps1-localization-engine
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Statik analiz + test
ruff check tools tests engine.py
pytest tests/ -m "not slow and not requires_assets"
```

Sentez (dublaj) için opsiyonel bağımlılıklar:

```bash
pip install -e ".[tts]"
```

---

## Mimari

```text
Europe.bin (kaynak disk)
   │
   ├─ engine.py dump-all-dialogues
   │     └─ tools/iso_fs.py → tools/dirdat.py → tools/wad_lpsx.py
   │           └─ translations/dialogue_*.json  (EN + TR)
   │
   ├─ tools/classify_dialogues_exact.py
   │     └─ audio/*_manifest.json  (cue → karakter → süre bütçesi)
   │
   ├─ tools/voice_cloner.py + tools/ingame_dubber.py
   │     └─ XTTS-v2 → audio/ingame_dub/*.wav
   │
   ├─ tools/audio_vag.py (+ vag_fast.c)
   │     └─ PCM → Sony ADPCM (16 bayt blok = 28 örnek)
   │
   ├─ tools/deterministic_audio_injector.py / inject_*.py
   │     └─ WAD XSPS ses tablosuna bayt-hizalı enjeksiyon
   │
   └─ tools/cd_patcher.py
         └─ Mode 2 Form 1 sektör yazımı (EDC/ECC yeniden hesaplı)
```

### Argonaut Ses Formatı — Kritik Sabitler

| Kavram | Değer | Anlamı |
|---|---|---|
| ADPCM blok | 16 bayt | 28 örnek |
| Ana cue frekansı | 22.050 Hz (`p2 = 0x0800`) | İlk / ana parça |
| Devam cue frekansı | 16.000 Hz (`p2 = 0x05CE`) | İkincil parça |
| Split offset | `0xA800` = 43.008 bayt | DE/EN paylaşımlı akış ayrımı |
| Split zaman eşiği | 3,4133 sn | İngilizce/Türkçe iğnesinin atladığı süre |
| Donanım bayrağı | `hw = 2` | Oyun içi konuşma kanalı |

---

## CLI

```bash
python engine.py dump-ui                     # UI metnini JSON'a çıkar
python engine.py dump-dialogue --wad T1L2M001
python engine.py dump-all-dialogues          # Tüm WAD diyalogları
python engine.py build-ui                    # JSON'dan UI bloğunu geri yaz
python engine.py build-iso                   # Disk imajını yeniden inşa et
```

Tüm komutlar için: `python engine.py --help`

---

## Diğer İş Kolları

| İş Kolu | Açıklama | Doküman |
|---|---|---|
| `hp2recomp/` | PSXRecomp MIPS→C native port (`psxrecomp/` ayrı checkout gerektirir) + `hp2.tr-flag-menu` modu | [docs/PORT_STATUS.md](docs/PORT_STATUS.md), [docs/DIRECTORY_MAP.md](docs/DIRECTORY_MAP.md) |
| `linux_port/` | Asset-tabanlı C11 + SDL2 + OpenGL native Linux motoru ve RE araçları | [linux_port/README.md](linux_port/README.md) |
| `ps1towasm/` | `.bin`/`.cue` imajlarını `pcsx_rearmed` WASM + HTTP Range web paketine dönüştürür | [ps1towasm/README.md](ps1towasm/README.md) |

---

## Katkı

Katkı süreci, PR kuralları ve commit standartları için
[CONTRIBUTING.md](CONTRIBUTING.md) dosyasına bakın. Kod kuralları ve mühendislik
ilkeleri [AGENTS.md](AGENTS.md) dosyasındadır.

Kısa özet:

1. Önce issue açın, sonra kod yazın.
2. Conventional Commits kullanın.
3. Küçük ve odaklı PR'lar açın.
4. Enjeksiyon içeren işlerde Kategori A koruma kapısı kanıtını ekleyin.

---

## Yasal / Legal

Bu proje **fan yapımı bir yerelleştirme aracı setidir**; Warner Bros., Electronic Arts,
Argonaut Games veya ilgili hak sahipleri tarafından onaylanmamıştır.

- Depodaki kod MIT lisanslıdır (bkz. `LICENSE`).
- Oyun içeriği, disk imajları, ses kayıtları ve metin varlıkları hak sahiplerine aittir
  ve bu depoda paylaşılmaz.
- Çeviri JSON'ları yalnızca araştırma ve yerelleştirme mühendisliği bağlamında
  yayınlanır.

Telifli varlıkları bu depoya eklemeyin. CI ve `.gitignore` bu dosyaları engeller.

---

## Lisans

Kod: [MIT](LICENSE)
