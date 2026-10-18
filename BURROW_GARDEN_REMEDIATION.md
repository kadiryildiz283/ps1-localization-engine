# Kovuk Bahçesi (The Burrow Garden — T1L2M001) Dublaj İyileştirme ve Multi-Cue Raporu

**Tarih:** 10 Eylül 2026  
**Hedef Seviye:** `T1L2M001.WAD` (Kovuk Bahçesi / The Burrow Garden)  
**Hedef İmaj:** `Harry Potter and the Chamber of Secrets (Turkish).bin`  

---

## 1. Tespit Edilen Kök Sorunlar (Root Cause Analysis)

Kullanıcı deneyiminde yaşanan iki temel kriz çözülmüştür:

### A. Karakter Eşleştirme Hatası (Molly Weasley'nin Ron Sesiyle Konuşması)
- **Sorun:** Molly Weasley'nin pencereden bahçeye bağırdığı replik (`#14#`, Cue 20: *"Ronald Weasley! Sana o hortlağın bu kadar patırtı yapmasını..."*), seviye bazlı kaba varsayım nedeniyle Ron sesiyle (`ron`) seslendiriliyordu.
- **Akustik Doğrulama (Ground Truth):** Orijinal Avrupa diski `Europe.bin` üzerinden çıkarılan Cue 20 ses örneği, Coqui XTTS hoparlör gömme vektörleriyle (speaker embeddings) karşılaştırıldı.
  - `mrs_weasley` kosinüs benzerliği: **%85.4 (0.854)**
  - `ron` kosinüs benzerliği: **%28.1 (0.281)**
- **Sonuç:** Orijinal sesin matematiksel olarak Molly Weasley olduğu kesinleştirildi ve replik `mrs_weasley` profiliyle yeniden üretildi.

### B. Cümlenin Ortasından Konuşma / Araya İngilizce Girmesi (Multi-Cue Sorunu)
- **Sorun:** Oyunun bazı diyalogları Argonaut motoru tarafından birden fazla alt parçaya bölünmüştür (Multi-Cue).
- **Hatalı Uygulama:** Önceki enjektör, tüm Türkçe cümleyi yalnızca ilk cue slotuna (`#B#` = Cue 11) sıkıştırmış, cümlenin devamı olan Cue 12 slotunu ise orijinal İngilizce bırakmıştı.
- **Sonuç:** Oyuncu ilk parçada aşırı hızlı (atempo) Türkçe duyuyor, hemen ardından motor Cue 12'yi tetiklediğinde araya orijinal İngilizce ses giriyordu.

---

## 2. Argonaut Motoru Çoklu Dil & Multi-Cue Çözümlemesi

Orijinal WAD içindeki `XSPS` ses tablosu incelendiğinde repliklerin donanımsal yapısı çözümlenmiştir:

1. **Donanım Frekans Registerı ($p_2$):**
   - $p_2 \land \text{0xFFFF} = \text{0x0800}$ (2048) $\rightarrow$ **22,050 Hz** (İlk / Ana Cue)
   - $p_2 \land \text{0xFFFF} = \text{0x05CE}$ (1486) $\rightarrow$ **16,000 Hz** (Devam / İkincil Cue)
   - $(p_2 \gg 16) \land \text{0xFFFF} = 2$ $\rightarrow$ Oyun içi konuşma kanalı (Hardware Flag 2)

2. **SPU Bellek Hesap Formülleri:**
   $$\text{Blok Sayısı} = \frac{\text{Boyut (Bayt)}}{16}$$
   $$\text{Toplam SPU Örneği} = \text{Blok Sayısı} \times 28$$
   $$\text{Maksimum Süre (sn)} = \frac{\text{Toplam SPU Örneği}}{\text{Örnekleme Frekansı}}$$

---

## 3. Kovuk Bahçesi 6 Replik / 11 Alt-Cue Matematiksel Tablosu

| No | Diyalog ID | Cue ID | Karakter | Frekans | Boyut | SPU Blok | Maks. Süre | Türkçe Metin Parçası |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| **1.1** | ID 71 | Cue 02 | `ron` | 22,050 Hz | 51,200 B | 3,200 | 4.06 s | *"Merhaba Harry!"* |
| **1.2** | ID 71 | Cue 03 | `ron` | 16,000 Hz | 26,624 B | 1,664 | 2.91 s | *"Evime hoş geldin,"* |
| **1.3** | ID 71 | Cue 04 | `ron` | 16,000 Hz | 40,960 B | 2,560 | 4.48 s | *"pek gösterişli sayılmaz ama."* |
| **2.1** | ID 89 | Cue 49 | `harry` | 22,050 Hz | 26,624 B | 1,664 | 2.11 s | *"Bence harika!"* |
| **3.1** | ID 72 | Cue 05 | `ron` | 22,050 Hz | 32,768 B | 2,048 | 2.60 s | *"Sağ ol Harry,"* |
| **3.2** | ID 72 | Cue 07 | `ron` | 16,000 Hz | 22,528 B | 1,408 | 2.46 s | *"biz buraya 'Kovuk' deriz."* |
| **4.1** | ID 73 | Cue 08 | `ron` | 22,050 Hz | 59,392 B | 3,712 | 4.71 s | *"Hadi Harry, hortlak tavan arası kapısını yine kilitlediyse"* |
| **4.2** | ID 73 | Cue 09 | `ron` | 16,000 Hz | 55,296 B | 3,456 | 6.05 s | *"içeri girmenin başka bir yolunu bulmalıyız."* |
| **5.1** | ID 74 | Cue 11 | `ron` | 22,050 Hz | 88,064 B | 5,504 | 6.99 s | *"Babam bahçeye birkaç sandık koymuş."* |
| **5.2** | ID 74 | Cue 12 | `ron` | 16,000 Hz | 57,344 B | 3,584 | 6.27 s | *"Neden onları çatıya tırmanıp açık tavan arası penceresinden içeri girmek için kullanmıyoruz?"* |
| **6.1** | ID 77 | Cue 20 | `mrs_weasley` | 22,050 Hz | 137,216 B | 8,576 | 10.89 s | *"Ronald Weasley! Sana o hortlağın bu kadar patırtı yapmasını engellemeni söylemiştim sanıyordum! Tavan arası zeminine hala borular düşürüp duruyor! Beni deli edecek!"* |

---

## 4. Uygulanan Mühendislik Aşamaları

1. **Yapay Zeka Sentezi (`tools/synthesize_burrow_exact.py`):**
   - Coqui XTTS-v2 sinir ağı ile 11 parça bağımsız olarak üretildi.
   - Molly Weasley'nin uzun tiradında modelin token tekrarına girmemesi için `enable_text_splitting=True` aktif edildi; cümle başlangıcındaki *"Ronald..."* hitabı kusursuz korundu.
   - Cue 09'da son ek yuvarlama sorunu fonetik optimizasyonla çözüldü.

2. **Whisper Fonetik Başlangıç Kapısı (Speech Onset Verification):**
   - Üretilen her WAV dosyası OpenAI Whisper modeli ile test edildi.
   - İlk kelimenin beklenen Türkçe fonemle başladığı, kırpılma veya gecikme olmadığı kanıtlandı.
   - Sürelerin SPU donanım kotasını aşmadığı doğrulandı.

3. **Hedefli ADPCM Enjeksiyonu (`tools/inject_burrow_exact.py`):**
   - Temel olarak `extracted_text_only/T1L2M001.WAD` (özgün sesler + Türkçe font/altyazılar) kullanıldı.
   - 11 diyalog parçası `encode_pcm_to_vag` ile kodlandı, bitişine tek bir sessizlik mute bloğu (`0x01`) eklenerek bayt-bayt enjekte edildi.
   - **Kategori A Koruma Kapısı:** WAD içindeki diğer 89 ses slotu (ortam sesleri, büyüler, müzik döngüleri) orijinal Avrupa dosyasıyla karşılaştırıldı: **%100 eşleşme (0 bozulma)**.

4. **CD-ROM XA Sektör Yamalama (`tools/patch_t1l2_to_iso.py`):**
   - `Harry Potter and the Chamber of Secrets (Turkish).bin` imajında `T1L2M001.WAD`'a ait LBA 86,655 - 90,801 aralığı (4,146 sektör) Mode 2 Form 1 (EDC/ECC) standartlarında güncellendi.
   - Geri okuma testi ile diske yazılan verinin yerel dosya ile bit-düzeyinde özdeş olduğu (`local == iso: True`) onaylandı.

---

## 5. İlgili Araçlar ve Dosyalar

- **Sentez Aracı:** [`tools/synthesize_burrow_exact.py`](file:///home/kadir/PS1-Localization-Engine/tools/synthesize_burrow_exact.py)
- **Enjektör:** [`tools/inject_burrow_exact.py`](file:///home/kadir/PS1-Localization-Engine/tools/inject_burrow_exact.py)
- **Hızlı ISO Yamalayıcı:** [`tools/patch_t1l2_to_iso.py`](file:///home/kadir/PS1-Localization-Engine/tools/patch_t1l2_to_iso.py)
- **Detaylı Matematiksel Şema & Mermaid:** [`burrow_mathematical_schema.md`](file:///home/kadir/.gemini/antigravity-cli/brain/e49b9bd1-90d9-4d07-b300-eb51d0e8e350/burrow_mathematical_schema.md)
