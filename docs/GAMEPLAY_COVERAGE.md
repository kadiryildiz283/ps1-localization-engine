# GAMEPLAY COVERAGE — HP2 Native Port (SLES-03972)

Amaç: master task bitiş kapısı — oyunun baştan sona oynanabilir olduğunun
kanıtı. Her bölüm için giriş, mekanikler, ilerleme tetikleyicileri, çıkış
ve özel sistemler test edilir. İlerlemeyi engelleyen hata = P0 blocker.

Kanıtlı mevcut durum (2026-11-15): boot → dil seçim → title → ana menü →
Quidditch demo + serbest oynanış (kullanıcı, "çok iyi çalışıyor").
**Tam bölüm hattı henüz sistematik doğrulanmadı.**

## Bölüm kimlikleri (disk verisinden, tahmin değil)

POTTER.DAT içindeki WAD adları `T{tier}L{level}M{map}` düzeninde:
- `T0I0M999` — title
- `T1I0M000/M001/M002/M004` — intro/ara sahne akışları
- `T1L1..T1L9` — 9 ana bölüm, her biri çok map (oda/alan)
- `FE3_SOND`, `FE3_WIZC`, `FE5_THND` — özel efekt projeleri (ses/büyü kartı/yıldırım)

İnsan-okunur bölüm adları (Hogwarts, Kovuk, vb.) oyun metninden/oynanıştan
gözlemlenip doldurulacak — diskte kod olarak yok, tahmin edilmiyor.

## Doğrulama yöntemi

3D platformer TCP ile kör oynanamaz. Yöntem: **enstrümantasyonlu insan
oynanışı** (master task gerçek kullanıcı oynanış testini açıkça kabul eder).

1. Oyun görünür pencere + quirk ile başlatılır (`docs/PORT_STATUS.md` §5).
2. `hp2recomp/tools/level_monitor.py` arka planda çalışır: CD sektör
   okumalarını POTTER.DAT WAD aralıklarına eşler, aktif `T1Lx` bölümünü
   ve geçişleri `hp2recomp/coverage_log.jsonl`'e frame+zamanla yazar.
3. Kullanıcı oynar; her bölüm geçişi/bulmaca/boss otomatik loglanır.
4. Sorun anında TCP snapshot (frame/PC/CD/GPU + screenshot OCR) alınır,
   kök neden bulunur, düzeltilir, yeniden koşulur.
5. Aşağıdaki tablo gözlenen kanıtla güncellenir.

Durum sütunu: `load` = verisi yükleniyor/render ediliyor; `play` =
gerçek oynanışla doğrulandı; `block` = ilerleme engeli var; `—` = henüz yok.

## Bölüm tablosu

| Kod | Map'ler | Ad (gözlem) | Durum | Kanıt (frame/log) | Not |
|-----|---------|-------------|-------|-------------------|-----|
| TITLE | T0I0M999 | Title/intro | play | boot_01.png, OCR "Select" | dil seçim + title |
| INTRO | T1I0M000/1/2/4 | EA intro + açılış | play | quirk_01..03, EA.STR MDEC | © 2002 EA + Quidditch demo |
| T1L1 | M000–M009 (10) | — | — | | |
| T1L2 | M001–M009 (9) | — | — | | |
| T1L3 | M000–M009 (10) | — | — | | |
| T1L4 | M001–M005,M007,M008 (7) | — | — | | |
| T1L5 | M001,M002,M004–M009 (8) | — | — | | |
| T1L6 | M002–M009 (8) | — | — | | |
| T1L7 | M001–M007 (7) | — | — | | |
| T1L8 | M001–M003,M005–M008 (7) | — | — | | |
| T1L9 | M001,M003–M008 (7) | — | — | | |
| SPECIAL | FE3_SOND/WIZC/THND | efekt projeleri | — | | |

## Sistemler (bölümler boyunca)

| Sistem | Durum | Kanıt |
|--------|-------|-------|
| Karakter hareketi | — | |
| Büyüler | — | |
| Kamera | — | |
| Etkileşim/NPC | — | |
| Bulmacalar | — | |
| Collectible | — | |
| Bölüm geçişi | — | level_monitor otomatik |
| Ara sahne (STR/MDEC) | load | EA.STR intro oynadı |
| Ses/XA müzik | load | intro sesi (headless audio=0 idi; pencere modunda doğrula) |
| Save/load (memcard) | — | card1.mcd yazıldı (oynanışta); yükleme doğrula |
| Final + jenerik | — | |

## Blocker günlüğü

- **ÇÖZÜLDÜ** frame-13624 CD DRQSTS wedge → `PSX_CD_EXPOSE_PENDING_FIFO`
  quirk (bkz. PORT_STATUS.md §4, issue #6).
