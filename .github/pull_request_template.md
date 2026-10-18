<!--
Bakıcılar net bir inceleme test planı olan PR'lara öncelik verir — yoksa inceleme gecikebilir.

Paragrafları sert satır sonuyla bölmeyin: GitHub tek satır sonlarını <br> gibi işler,
böylece sarılmış metin dar bir sütun gibi görünür. Her paragrafı tek uzun satır yazın.
-->

## Bu PR ne yapıyor

<!-- Değişikliği dosya/fonksiyon adlarıyla değil, düz anlatımla açıklayın. -->

## Neden gerekli

<!-- Motivasyon, çözülen problem veya kullanıcıya faydası. -->

## İnceleme Test Planı

<!--
Bir inceleyicinin bu PR'ı nasıl doğrulayacağı: yeniden üretme adımları, beklenen vs
görülen davranış ve kanıt. CI Linux'ta çalışır — "Test edildi" sizin yerelde
doğruladığınız ortamdır.

Kullanıcıya görünür / TUI: önce-sonra ekran görüntüsü, log veya kısa kayıt.
Kullanıcıya görünmez (refactor, tip, docs): komut ve çıktı; önce-sonra yerine N/A yazın.
-->

### Nasıl doğrulanır

<!-- Yeniden üretme adımları, beklenen/görülen davranış. Sonuçlara odaklanın. -->

### Kanıt (Önce & Sonra)

<!-- Kullanıcıya görünür değişiklikler: önce-sonra ekran görüntüsü, log veya video.
Diğerleri (docs, refactor): N/A -->

### Test edilen ortam

| Ortam | Durum |
| :---: | :---: |
| 🐧 Linux |  |
| 🍏 macOS |  |
| 🪟 Windows |  |

<!-- ✅ test edildi · ⚠️ test edilmedi · N/A -->

### Enjeksiyon kanıtı (varsa)

<!-- Kategori A koruma kapısı, `local == iso: True`, Whisper onset çıktısı. -->

## Risk & Kapsam

- Ana risk / tradeoff:
- Doğrulanmayan / kapsam dışı:
- Kırıcı değişiklik / geçiş notları:

## Bağlı Issue'lar

<!--
Closes #N / Fixes #N / Resolves #N otomatik kapatır.
Aksi halde anahtar kelimesiz referans verin.
-->
