# Katkı Rehberi

Bu projeye katkılarınızı görmek isteriz.

## Katkı Süreci

### Kod İncelemesi

Tüm gönderiler, proje üyeleri de dahil olmak üzere inceleme gerektirir.
Bunun için [GitHub pull request](https://docs.github.com/articles/about-pull-requests) kullanıyoruz.

### Pull Request Kuralları

PR'ınızı hızlı inceleyip birleştirebilmemiz için bu kurallara uyun. Bu standartları
karşılamayan PR'lar kapatılabilir.

#### 1. Mevcut Bir Issue'ya Bağlayın

Tüm PR'lar takipçideki mevcut bir issue'ya bağlanmalıdır. Böylece her değişiklik kod
yazılmadan önce konuşulmuş ve proje hedefleriyle uyumlu olmuş olur.

- **Hata düzeltmeleri:** PR, hata raporu issue'suna bağlanmalıdır.
- **Özellikler:** PR, bir bakıcı tarafından onaylanmış özellik isteği issue'suna bağlanmalıdır.

Değişikliğiniz için bir issue yoksa **önce bir tane açın** ve kod yazmaya başlamadan
önce geri bildirim bekleyin.

#### 2. Küçük ve Odaklı Tutun

Tek bir issue'yu çözen veya tek bir kendine yeten özelliği ekleyen küçük, atomik
PR'ları tercih ederiz.

- **Yapın:** Tek bir belirli hatayı düzelten veya tek bir özellik ekleyen PR.
- **Yapmayın:** İlişkisiz değişiklikleri (hata düzeltmesi + yeni özellik + refactor)
  tek PR'a yığmayın.

Kaba kural: ~1.200 değişen satırı aşan PR'ları bölmeye başlayın. ~2.000 satırı aşanlar
ya mantıksal olarak bağımsız birleştirilebilir küçük PR'lara bölünmeli ya da neden
birlikte inmesi gerektiği PR açıklamasında gerekçelendirilmelidir.

#### 3. Devam Eden İşler İçin Draft PR

Erken geri bildirim almak istiyorsanız GitHub'ın **Draft Pull Request** özelliğini
kullanın. Bu, PR'ın henüz resmi incelemeye hazır olmadığını belirtir.

#### 4. Tüm Kontrollerin Geçtiğinden Emin Olun

PR'ı göndermeden önce `ruff check` ve `pytest` komutlarının yeşil olduğundan emin olun:

```bash
ruff check tools tests engine.py
pytest tests/ -m "not slow and not requires_assets"
```

#### 5. Dokümantasyonu Güncelleyin

Kullanıcıya görünür bir değişiklik (yeni komut, değişen davranış) getiriyorsanız
`/docs` ve gerekirse `AGENTS.md` içeriğini de güncelleyin.

#### 6. Kanıt Ekleyin

İnceleyicilerin değişikliğinizi hızla anlaması için kanıt ekleyin:

- **Hata düzeltmesi:** önce/sonra davranışı
- **Yeni özellik:** özellik uçtan uca çalışırken
- **Refactor / yalnızca iç değişiklik:** demo bölümüne "N/A — kullanıcıya görünür değişiklik yok" yazın

Enjeksiyon içeren işlerde **Kategori A koruma kapısı** çıktısını ve varsa
`local == iso: True` doğrulamasını PR'a iliştirin.

#### 7. Açık Commit Mesajları ve İyi PR Açıklaması

[Conventional Commits](https://www.conventionalcommits.org/) standardını izleyin.

- **İyi PR başlığı:** `fix(inject): T1L2M001 multi-cue parça seslerini cue bazında yerleştir`
- **Kötü PR başlığı:** `Bazı değişiklikler yaptım`

PR açıklamasında değişikliğin "neden"ini anlatın ve ilgili issue'ya bağlayın
(örn. `Fixes #123`).

### Yeni Bir Ses Profili Ekleme

Ses profilleri, gerçek insan kayıtlarından türetilir ve XTTS-v2 latents dosyaları
içerir. Yeni bir karakter profili eklerken:

1. Referans kaydın temiz olduğundan (gürültü, yankı yok) emin olun.
2. `tools/build_profiles.py` veya `tools/build_enhanced_voice_profiles.py` ile üretin.
3. `audio/profiles/` altına `.wav` + `_latents.pt` ikilisi koyun (binary'ler git'e girmez;
   yalnızca manifest alanlarını güncelleyin).
4. `classify_dialogues_exact.py` içindeki havuz tanımını bilinçli güncelleyin.

## Geliştirme Ortamı ve İş Akışı

### Ön Gereksinimler

1. **Python** `>= 3.10`
2. **Git**
3. Opsiyonel sentez için: CUDA'lı PyTorch + Coqui TTS (`pip install -e ".[tts]"`)

### Kurulum

```bash
git clone https://github.com/kadiryildiz283/ps1-localization-engine.git
cd ps1-localization-engine
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Commit Mesajı Biçimi

```
<type>(<kapsam>): <açıklama>

[opsiyonel gövde]

[opsiyonel footer]
```

Tipler: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `ci`
Kapsamlar: `iso`, `text`, `tts`, `adpcm`, `inject`, `manifest`, `character`, `ci`, `docs`

## İlke

Bir PR'ı açmadan önce kendinize şunu sorun: "Bu değişiklik tek bir işi mi yapıyor ve
bir issue'yu mu kapatıyor?" Cevap hayırsa, bölün.
