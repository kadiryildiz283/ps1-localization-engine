# HP2 PS1 → Linux native port: ortak bağlam (tüm RE ajanları için)

## Hedef
`/home/kadir/Projeler/PS1-Localization-Engine/linux_port/` altında, emülatör KULLANMAYAN, doğrudan disk varlıklarını
okuyan native (C11 + SDL2 + OpenGL) bir oyun motoru. Önce her varlık formatı tersine mühendislikle çözülür,
açık formatlara (PNG/WAV/OBJ/JSON/ikili spec) dönüştürülür; sonra C motoru bunları yükler.

## Elde olanlar (doğrulanmış)
- Orijinal Avrupa diski %100 dökülmüş: `linux_port/dump/` (bkz. `dump/manifest.json`)
  - `dump/disc/` : SYSTEM.CNF, SLES_039.72 (PS-X EXE, loader), EURO1.GAM (PS-X EXE, asıl oyun), POTTER.DIR/DAT,
    EA.STR (+ `EA.STR.raw2352`, Form2 sektörlü ham), 40MEG.RAW (0xFF dolgu)
  - `dump/potter/` : POTTER.DAT içindeki 357 girdi (355 benzersiz; T1L1M002.WAD ve T1L5M006.WAD ikişer kez, birebir aynı):
    81 `.WAD`, 248 `.IMG`, 14 `.BIN` (UI metin), 11 `.DEM`, 1 `.TXT`
- Dosya adı/ofset: `POTTER.DIR` = [u32 sayı] + sayı×{char[12] ad, u32 boyut, u32 ofset} (2048 hizalı ofset).
- WAD yapısı (doğrulandı, 78/81 dosya): ilk u32 = toplam boyut (+2048), sonra zincir: [4 bayt TERS ASCII tag][u32 boyut][payload].
  Tag'ler ters yazılı: `XSPT`→TPSX (doku), `SPSX`→SPSX (ses), `UNIF`, `LPSX` (metin, repo `tools/wad_lpsx.py` çözüyor),
  `DPSX` (seviye verisi, ana hedef), `PORT`, son chunk `" DNE"`→"END " (çoğu sıfır dolgu/akış alanı).
  `FE3_SOND.WAD`, `FE3_WIZC.WAD`, `FE5_THND.WAD` farklı yapıda (EURO1.GAM'da özel olarak adlandırılmış, "special project").
- Metin: `tools/text_bin.py` (ENGLISH.BIN Caesar -1), `tools/wad_lpsx.py`. Ses enjeksiyon referansı: `tools/audio_vag.py`, `docs/ARGONAUT_STREAM_SPLIT_ARCHITECTURE.md`.
- Kod analizi: `linux_port/analysis/mipsa.py` (capstone; `Exe(path)`, `exe.disasm(addr,n)`, `find_lui_refs(exe,lo,hi)`).
  ÖNEMLİ: EURO1.GAM yükleme adresi 0x80010000, boyut 0x6E000, giriş 0x80060B54. Kod KUSEG adresleri kullanır
  (`lui $v0,7` gibi 0x0007xxxx, 0x8007xxxx değil) — xref ararken `addr & 0x1FFFFFFF` kullan.
  EURO1.GAM'da dosya adı tablosu ~0x8007CA6C.., dosya yükleyici ~0x80010690..0x80010AEC (POTTER.DIR/DAT açan kod 0x800109F0/0x80010AEC).
- Python ortamı: `linux_port/.venv/bin/python` (capstone, numpy, pillow kurulu). Sistem Python 3.14 de var.
- Araçlar: gcc, clang, cmake, SDL2 2.32 mevcut. `rea` MCP MIPS/PS-X EXE açmıyor — capstone + el ile analiz kullan.

## Kurallar (AGENTS.md'den)
1. Önce sadelik: spekülatif soyutlama yok; çalışan en küçük kod.
2. Kanıt öncelikli: "oldu" demeden önce çalışan kanıt göster (PNG'yi `read_file` ile GÖR, WAV süresi/örnek sayısı, bayt-düzeyi doğrulama).
   Tahmin veya "muhtemelen" geçerli kanıt değildir.
3. Telifli veri (dump, çıktı PNG/WAV vs.) commit edilmez; sadece kod + doküman.
4. Başka ajanların dosyalarını DÜZENLEME. Sadece kendi dizininde çalış (aşağıda atanmış).
5. Her format için `linux_port/docs/formats/<AD>.md` yaz: bayt düzeni, alan anlamları, DOĞRULANMIŞ/VARSAYIM etiketli, kanıt komutu.
6. Çözülmeyen kısmı gizleme: ne çözüldü, ne çözülmedi açıkça yaz.
7. Çıktıları `linux_port/build_assets/<tür>/` altına yaz (C motoru buradan okuyacak). Dönüştürücüler idempotent olsun.

## Dil
Dokümanlar Türkçe, kod/yorum kısa; commit mesajı gerekmiyor (commit YOK).
