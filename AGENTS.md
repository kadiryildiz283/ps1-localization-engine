# AGENTS.md

## Çalışma İlkeleri

### Önce Sadelik (Simplicity First)

**Problemi çözen en az kod. Spekülatif hiçbir şey yok.**
**(En çok önemsediğimiz ilke budur.)**

- İstenmeyen özellik yok.
- Tek kullanımlık kod için soyutlama yok.
- İstenmeyen "esneklik" / "yapılandırılabilirlik" yok.
- İmkânsız senaryolar için hata yakalama yok.
- 200 satır yazıp 50'ye inebiliyorsan yeniden yaz.

Kendine sor: "Kıdemli bir mühendis buna fazla karmaşık der miydi?" Evetse sadeleştir.

### Kanıt Öncelikli Kural

Bir şeyi "oldu" demeden önce **çalışan kanıt** göster:

- Enjeksiyon → `local == iso: True` bayt-düzeyi doğrulama
- Karakter ataması → orijinal sesin speaker-embedding benzerlik skoru
- Multi-cue → her alt-cue'nun ayrı ayrı Türkçesi ve SPU süre bütçesi
- Split-stream → `0xA800` ofsetinde Türkçe başlangıç (Whisper onset kapısı)

Tahmin, "muhtemelen olmuştur" veya geçmiş konuşma geçerli kanıt değildir.

### Kategori A Koruma Kapısı (Dokunulmaz)

Her enjeksiyon çalışması, diyalog **olmayan** ses slotlarını (ortam, SFX, müzik döngüsü)
orijinal Avrupa diskiyle karşılaştırmak zorundadır. %100 eşleşme sağlanmadan iş bitmiş sayılmaz.
Bkz. `BURROW_GARDEN_REMEDIATION.md` §4.3.

### Multi-Cue Dokunuşmazlığı

Argonaut motoru uzun diyalogları birden fazla cue'ya böler. Bir cümlenin **tamamını**
tek cue slotuna sıkıştırmak yasaktır. Her alt-cue kendi metin parçasını, kendi frekansında
ve kendi süre bütçesinde alır. Bkz. `docs/ARGONAUT_STREAM_SPLIT_ARCHITECTURE.md`.

### Karakter Eşleştirme

- `LINE_CHARACTER_MAP` yalnızca elle doğrulanmış cutscene satırları içindir.
- Havuz tabanlı atama (`hermione` = Hermione+Ginny+Myrtle vb.) **bilinçli bir kayıptır**;
  Ginny gibi kritik repliklerde akustik doğrulama + ayrı profil gerekir.
- Bir replik "yanlış kişi konuşuyor" semptomu veriyorsa önce havuz atamasını sorgula.

## Mimari

```
engine.py                  # CLI: dump-ui / dump-dialogue / build-ui / build-iso ...
tools/
  argonaut_xsp.py          # XSPS/SPU saf matematik + stream sınıflandırma (assetsiz)
  inject_dialogue.py       # Merkezî multi-cue / 0xA800 split-stream enjektör
  speaker_map.py           # speaker_id ↔ voice_profile (Ginny kimlik ayrımı)
  iso_fs.py                # PS1 ISO9660 / Mode2 Form1 okuyucu
  dirdat.py                # POTTER.DAT arşiv formatı
  text_bin.py              # ENGLISH.BIN UI metin bloğu
  wad_lpsx.py              # WAD LPSX diyalog kayıtları
  audio_vag.py             # PCM ↔ Sony ADPCM (VAG) kodlayıcı
  vag_fast.c               # Hızlı ADPCM kodlayıcı (C uzantısı)
  cd_patcher.py            # CD-ROM XA sektör yamalama (EDC/ECC)
  classify_dialogues_exact.py  # Karakter sınıflandırma
  voice_cloner.py          # XTTS-v2 sinir ağı ses motoru
  ingame_dubber.py         # Toplu sentez + SPU enjeksiyon
  deterministic_audio_injector.py
  inject_burrow_*.py       # Kovuk Bahçesi hedefli enjektörler (referans/fixtures)
docs/
  ARGONAUT_STREAM_SPLIT_ARCHITECTURE.md
tests/
translations/              # EN→TR diyalog JSON'ları
audio/*.json               # Manifestler (ses binary'leri depoya girmez)
```

## Sık Kullanılan Komutlar

```bash
# Ortam
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Statik analiz
ruff check tools tests engine.py
ruff format --check tools tests engine.py

# Testler (CI'da koşulan hızlı küme)
pytest tests/ -m "not slow and not requires_assets"

# Disk imajı gerektiren doğrulama testleri (yerel)
pytest tests/ -m requires_assets

# Multi-cue / split-stream plan (assetsiz sınıf + fixture)
python tools/inject_dialogue.py --plan --wad extracted/T1L2M001.WAD --regression-burrow

# CLI
python engine.py --help
python engine.py dump-all-dialogues --bin "Harry Potter and the Chamber of Secrets (Europe) (En,Fr,De).bin"
```

## Değişiklik Kuralları

1. **Issue bağlantısı zorunlu.** Issue'suz PR açılmaz.
2. **Conventional Commits:** `feat(adpcm): ...`, `fix(inject): ...`, `docs(argonaut): ...`
3. **Küçük PR:** Tek bir işi yapan, ~1.200 satırı aşmayan değişiklikler.
4. **Kanıt:** Kullanıcıya görünür değişiklikte önce/sonra veya doğrulama çıktısı.
5. **Kategori A kapısı** enjeksiyon içeren her PR'da yeniden çalıştırılır.
6. Telifli varlıklar (`.bin`, `.WAD`, ses) asla commit edilmez.

## Modül Bazlı Notlar

- `tools/audio_vag.py` + `vag_fast.c`: ADPCM blok yapısı 16 bayt = 28 örnek.
  Bayt hizası kutsaldır; off-by-one tüm seviyeyi bozar.
- `tools/cd_patcher.py`: Mode 2 Form 1 EDC/ECC yeniden hesaplanır;
  ham sektör yazmak imajı bozar.
- `tools/classify_dialogues_exact.py`: Yeni karakter havuzu eklemeden önce
  mevcut `LINE_CHARACTER_MAP` ve stem kural bloklarını oku.
