# EA.STR — PS1 STR video (BS v2, MDEC)

`dump/disc/EA.STR.raw2352` gerçekten videodur: **320×240, 100 kare, 15 fps (≈6,67 sn)**, standart Sony STR/BS **v2**
bitstream'i. Çözücü: [`re/str_video.py`](../../re/str_video.py) (saf Python + numpy; Pillow yalnız PNG yazmak için).

Üretim: `.venv/bin/python re/str_video.py` → `build_assets/video/EA_frame_0001..0030.png` + `EA_frame_0100.png`
(`--all` tüm 100 kare). İdempotent.

## 1. Dosya / sektör düzeni — DOĞRULANDI
- Dosya boyutu 2 349 648 B = 999 × 2352 (ham). (Görev metnindeki 2 045 952 = 999 × 2048 kullanıcı verisi boyutudur.)
- Her sektör: 12 B senkron (`00 FF×10 00`), 4 B adres/mod (mod 2), 8 B XA alt-başlık (4 B, tekrarlı), 2048 B veri (Form1) / 2324 B (Form2).
- Sektör türleri (alt-başlık submode `s[18]`):

| tür | submode | sayı | not |
|---|---|---|---|
| video | `0x48` (Form1 + data + RT), son sektör `0xC8` (EOF) | 875 | file=1, channel=0 |
| ses | `0x64` (Form2 + RT + audio), coding `0x01` | 75 | file=1, channel=1 |
| boş | `0x00` | 49 | veri alanı tamamen 0; sektör 607..991, 8'de bir |

(924 Form1 = 875 video + 49 boş; 75 Form2 = ses.)
- Sektör deseni: ilk 600 sektör `VVVVVVVA` (7 video + 1 ses) tekrarı (ses sektörleri 7,15,…,599); 600'den sonra ses sektörünün
  yerinde boş (submode 0) sektör bulunur. Frame'ler 10 sektör aralıklı (sabit): 150 sektör/sn ⇒ 15 fps.

## 2. STR video sektör başlığı (veri alanının ilk 32 B'ı) — DOĞRULANDI
```
+00 u32  0x80010160  magic
+04 u16  chunk no (0..n-1)           +06 u16 chunk sayısı (8 veya 9)
+08 u32  frame no (1..100)           +0C u32 demux boyutu (bayt, frame bitstream'i)
+10 u16  genişlik (320)              +12 u16 yükseklik (240)
+14 u16  MDEC kod sayısı (×2 B)      +16 u16 0x3800   +18 u16 quant=1   +1A u16 sürüm=2
+1C u32  0
```
- Her sektörde 2048−32 = **2016 B** yük. Bir frame = chunk'ların yükleri sırayla birleştirilip `demux boyutu` kadar kesilir.
  Çoğu frame'de son chunk'lar boş (yük 0'lı): bitstream küçük (4–7 KB/kare), sabit 9 sektör ayrılmış.
- Birleştirilen frame'in ilk 8 B'ı BS başlığı (`mdec_say, 0x3800, quant, sürüm`) — başlıktaki kopyayla aynı.
- 100/100 frame'de eksik chunk yok. Frame no 1..100, chunk sayısı son frame'de 8, diğerlerinde 9.

## 3. BS v2 bitstream → MDEC — DOĞRULANDI
Bayt 8'den itibaren: 16-bit **little-endian** kelimeler, her kelime içinde **MSB önce** bit okuma.
- Makroblok = 6 blok sırayla **Cr, Cb, Y1(sol-üst), Y2(sağ-üst), Y3(sol-alt), Y4(sağ-alt)**; makrobloklar **sütun öncelikli**
  (yukarıdan aşağı, sonra sağa). 20×15 = 300 MB = 1800 blok.
- Blok: 10 bit işaretli DC (qscale başlıktan: 1; DC için qscale yok) → AC kodları → `10` = EOB.
- AC Huffman (v1/v2/v3 ortak tablo; kodun tamamı koddur, sonra 1 işaret biti): `11s`→MDEC 0x0001 (run0,seviye1), `011s`→0x0401 (run1,seviye1), `010xs`→0x0002/0x0801 …;
  tablonun tamamı kodda `_AC_ROWS` (kaynak: psx-spx "Huffman codes for AC values BS v1/v2/v3"). Escape: `000001` + 16 bit ham MDEC değeri (üst 6 bit run, alt 10 bit işaretli seviye).
  MDEC değeri = `(run<<10)|seviye`; k += run+1.
- Dequant: DC = DC×QT[0]; AC = (seviye×QT[k]×qscale+4)/8; ±(−1024..1023) sınırlama. k zigzag sırası, blok `zagzig[k]` raster indisine yazılır.
  QT = PS1 varsayılan matris (2,16,19,22,26,27,29,34, …). **VARSAYIM:** oyunun MDEC(2) komutuyla yüklediği tablo EURO1.GAM'da
  aranıp bulunmadı (varsayılan tablo baytları ne raster ne de zigzag sırasında EURO1.GAM/SLES'te yok); ancak aşağıdaki
  ffmpeg karşılaştırması bu matrisin doğru olduğunu gösteriyor.
- IDCT: ortonormal 8×8 (`pix = Mᵀ·C·M`), YCbCr→RGB: R=Y+1.402Cr, G=Y−0.3437Cb−0.7143Cr, B=Y+1.772Cb, +128, kırp; chroma 2× en yakın komşu.

## 4. Kanıtlar (çalıştırılan)
- **Çözülen/toplam: 100/100 frame.** Her frame'de 1800. bloktan sonra bitstream'in tam sonunda (`≤ demux×8`, son <1 kelime dolgu)
  **frame-sonu işareti `0111111111`** (psx-spx "EOF DC") bulundu: 100/100 → bit akışı hizası ve Huffman tablosu kesin doğru.
- Bağımsız referans (`ffmpeg -f psxstr`, yalnızca karşılaştırma): 100 kare, çözünürlük aynı; PSNR(bizim, ffmpeg) min **47.0 dB**, ort **48.1 dB**
  (fark yalnız IDCT/renk yuvarlaması).
- Görsel (read_file): kare 30 = **EA GAMES logosu** (beyaz/mavi disk, siyah zemin); kare 15 = turkuaz silindirik 3B nesne (parlak zemin üstünde, anlamlı sahne);
  kareler 1, 5, 100 siyah (fade-in / fade-out; kare 1 ve 100 yakın-siyah gürültü).

## 5. Ses (yalnız not — ses ajanına)
75 Form2 sektör: file=1, channel=1, submode `0x64`, coding byte `0x01` ⇒ **XA-ADPCM, stereo, 37 800 Hz, 4-bit**. Sektör 7'den 599'a 8'de bir.
Süre ≈ 75 × 2016 / 37800 ≈ 4,0 sn/kanal (VARSAYIM: standart XA sektör başına 18 grup × 112 örnek/kanal hesabı); video 6,67 sn sürdüğünden
ses ilk 4 sn'yi kapsar. Çözülmedi (kapsam dışı).

## 6. Çözülmeyenler / sınırlar
- MDEC fixed-point yuvarlaması donanım-birebir değil (float IDCT) — görüntü PSNR ≈ 48 dB.
- Kare 1 ve 100 neredeyse siyah; içerik ilk 30 kare + son karenin dışında (31–99) PNG olarak yazılmadı (`--all` ile yazılır, 100/100 çözülüyor).
