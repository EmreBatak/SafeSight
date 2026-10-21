# SafeSight — Proje Bağlamı (Claude Code için)

Bu dosya, projenin şimdiye kadarki tüm kararlarını tek yerde toplar. Yeni bir oturumda önce bunu oku.
Burada "karar" yazan şeyler kesinleşmiştir; "öneri" yazanlar henüz konuşulmadı, uygulamadan önce kullanıcıya sor.

## Çalışma tercihleri

- Kullanıcıyla **Türkçe** konuş, cevaplar **kısa ve net** olsun. Aşırı detaydan ve çok tablodan kaçın.
- Rapor ve literatür metinleri **İngilizce** yazılır.
- Büyük bir kararı (sınıflar, mimari, kapsam) değiştirmeden önce sor.
- Bir kaynağa bir iddia atfetmeden önce makalenin kendisinden kontrol et; kontrol edemediysen bunu açıkça söyle.

---

## 1. Proje nedir?

**SafeSight**: Maden sahası girişinde, işçinin **toz maskesini doğru takıp takmadığını** kamerayla kontrol eden bir giriş kapısı prototipi.

- Maske doğru takılıysa kapı açılır. Maske yoksa ya da yanlış takılıysa kapı kapalı kalır ve ekran nedenini söyler.
- Her karar işçinin kart numarasıyla kaydedilir ve bir web panelinde gösterilir. Aynı işçi üst üste reddedilirse iş güvenliği sorumlusuna uyarı düşer.
- Üniversite bitirme projesi (Işık Üniversitesi, Yönetim Bilişim Sistemleri). Ekip: Yunus Emre Köybaşı, Emre Batak.
- **Bu bir prototip.** Laptop ve laptop kamerasıyla çalışır. Raspberry Pi, Jetson ve gerçek turnike yok.

## 2. Kapsam (karar)

**Kapsamda:**

- Kullan-at toz maskeleri: **FFP2 / FFP3, N95 tipi**, ventilli ve ventilsiz.
- Girişte tek kişi, kameraya 1–3 m mesafe.

**Kapsam dışı:**

- Cerrahi maske, bez maske, bandana. Bunlar tespit hedefi değil.
- Yarım yüz ve tam yüz (kartuşlu) respiratörler.
- **Ferdi kurtarıcı.** Belde ya da omuzda taşınan, sadece acil durumda takılan oksijenli kaçış cihazı; kapıda "takılı mı" diye kontrol edilemez.
- Maske sızdırmazlık (fit) testi, saha içinde sürekli izleme, kask, yelek ve diğer KKD.
- Yüz tanıma. Kimlik QR kartla belirlenir.

## 3. Sınıflar ve karar kuralı (karar)

YOLO modeli 3 sınıf öğrenir. Hepsi toz maskesi için tanımlıdır.

| Sınıf | Anlamı |
|---|---|
| `mask_proper` | Burun ve ağız tamamen kapalı |
| `mask_improper` | Maske var ama burun ya da ağız açıkta (burun altında, çenede vb.) |
| `no_mask` | Maske yok |

**Kapı açılma kuralı (track bazında):**

1. ByteTrack her kişiye bir track ID verir. Karar motoru o track'in **son 15 gözlemini** tutar.
2. Kapı şu üç koşulun hepsi sağlanınca açılır (`OPEN`):
   - son 15 gözlemin **en az %80'i** `mask_proper`;
   - **son 5 gözlemin hepsi** `mask_proper`;
   - güven skoru **≥ 0.7** (daha düşük skorlu tespitler sayılmaz).
3. **Fail-closed:** emin olunamayan her durumda kapı kapalı kalır (`HOLD`).
4. **Tek kişi kuralı:** kadrajda birden fazla kişi varsa `HOLD` (reason: `multiple_people`).
5. Yüz bulunamazsa `HOLD` (reason: `no_face`).
6. Aynı işçi **üst üste 3 kez `HOLD`** alırsa `alerts` tablosuna uyarı yazılır.

Öneriler (henüz konuşulmadı):

- QR okunduktan sonra 10 sn içinde karar çıkmazsa `HOLD` (reason: `timeout`).
- ByteTrack'in `track_buffer` değerini kare sayısı yerine saniyeye göre ayarla (~2 sn). Laptop FPS'i benchmarklardan düşük olacak.

## 4. Mimari (karar)

```
Laptop webcam
  → YOLO11n (3 sınıf)            # Ultralytics
  → ByteTrack                     # model.track(..., tracker="bytetrack.yaml")
  → Karar motoru (kural, bkz. §3)
  → Ekran mesajı ("GEÇİŞ AÇIK" / "MASKENİ DÜZELT")
  → QR kart (OpenCV QRCodeDetector) ile işçi kimliği
  → FastAPI  → PostgreSQL (Docker)
  → Next.js panel (geçişler, retler, uyarılar, istatistik)
```

- **Model:** YOLO11n, tek model, 3 sınıf. Pose + sınıflandırıcı yolu ileride opsiyonel.
- **Eğitim:** Google Colab ya da Kaggle'ın ücretsiz GPU'su. Laptop CPU'su sadece çalıştırma (inference) için.
- **Panel:** Next.js (karar). Streamlit alternatif olarak konuşulmuştu ama Next.js'te kalındı.
- Not: YOLO11'in hakemli bir makalesi yok. Raporda seçim YOLO ailesi üzerine yapılmış çalışmalara dayandırılıyor.

### Önerilen klasör yapısı (öneri)

```
safesight/
  CLAUDE.md
  docs/                 # rapor (.docx), literatür tablosu (.xlsx)
  data/
    raw/                # indirilen datasetler (git'e girmez)
    yolo/               # images/{train,val,test}, labels/{train,val,test}
    data.yaml
  scripts/
    convert_kaggle_voc_to_yolo.py
    autolabel_mendeley_n95.py
    split_by_person.py
  src/
    gate/               # ana döngü: kamera, model, takip, ekran, QR
    decision/           # karar motoru (§3), birim testli
  api/                  # FastAPI
  dashboard/            # Next.js
  models/               # eğitilmiş ağırlıklar (git'e girmez)
  docker-compose.yml    # PostgreSQL
  tests/
```

## 5. Veritabanı (karar)

```sql
workers  (id, badge_no, name, department, active)
gates    (id, name, location)
passages (id, worker_id, gate_id, started_at, ended_at,
          decision,        -- 'OPEN' | 'HOLD'
          reason,          -- 'proper' | 'improper' | 'no_mask' | 'no_face' | 'multiple_people'
          proper_ratio, snapshot_path)
alerts   (id, worker_id, passage_id, type, created_at, acknowledged)
```

**API (karar):** `POST /passages`, `GET /stats`, kamera görüntüsü için bir MJPEG stream.
Panelin ihtiyaç duyacağı ek uçlar (`GET /passages`, `GET /alerts`) öneri.

## 6. Dataset planı (karar)

### 6.1 İlk eğitim: public veri

1. **Face Mask Wearing Image Dataset: Correct vs. Incorrect Usage** (Mendeley)
   - Link: https://data.mendeley.com/datasets/8pn3hg99t4/2
   - Makale: Suryawanshi, Y. C., Meshram, V. A., Meshram, V. V., Patil, K. R., & Chumchu, P. (2023). *Data in Brief, 51*, 109755. https://doi.org/10.1016/j.dib.2023.109755 (CC BY)
   - Yapı: `Correct/` ve `Incorrect/`, her birinin altında `Bandana`, `Cotton`, `N95`, `Surgical`, onların altında `Child`, `Male`, `Female`.
   - **Sadece `N95` klasörleri kullanılır.** N95, FFP2 toz maskesiyle aynı kap şeklinde. `Correct/N95` → `mask_proper`, `Incorrect/N95` → `mask_improper`.
   - **Kutu etiketi yok**, etiketler klasör bazında. Yüz kutuları bir yüz tespit modeliyle otomatik çıkarılır, sonra elle kontrol edilir. Maskeli yüzlerde tespit kaçabilir.
   - Lisans Mendeley sayfasında boş görünüyor. Makale CC BY; kullanırken atıf yapılacak.
   - N95 klasöründe kaç görüntü olduğu bilinmiyor; indirince sayılacak.
2. **Kaggle Face Mask Detection** (`no_mask` sınıfı için)
   - Link: https://www.kaggle.com/datasets/andrewmvd/face-mask-detection
   - 853 görüntü, CC0, PASCAL VOC (XML) formatında; YOLO formatına çevrilecek.
   - **Sadece `without_mask` yüzleri kullanılır**; cerrahi maskeli yüzler kullanılmaz.
   - **Dikkat:** Bir görüntüde hem maskeli hem maskesiz yüz varsa, maskeli yüzü silip görüntüyü tutma. Etiketsiz kalan yüzü model arka plan sanar. Ya sadece tüm yüzleri `without_mask` olan görüntüleri al, ya da yüzleri kırpıp kullan.

Kullanılmayanlar ve nedenleri:

- **FMR-DB / FMR-DBv2:** Respiratör türleri var ama herkese açık değil. Kurumsal e-posta ve imzalı lisans gerekiyor, veri sadece kurumdaki bilgisayarlarda tutulabiliyor; büyük ihtimalle takılma durumu etiketi de yok. İstenirse başvurulabilir, ama plan buna dayanmaz.
- **WWMR-DB:** COVID tipi maskeler.
- **Roboflow HalfFaceMask:** Yarım yüz respiratör içeriyor, kapsam dışı. Etiketleri de karışık; tam yüz maskeler "half-face" diye etiketlenmiş.
- **MaskTheFace (MIT lisanslı araç):** Maskesiz yüzlere yapay N95/KN95 giydiriyor. Veri az kalırsa opsiyonel.

### 6.2 Kendi verimiz (asıl test seti)

- Ventilli ve ventilsiz birkaç FFP2/FFP3 maske alınacak.
- 15–20 gönüllü, **yazılı onamla**, laptop kamerasıyla çekilecek. Üç durum çekilecek: doğru takılmış, yanlış takılmış (burun ya da çene açıkta), maske yok.
- Mesafe 1–3 m, farklı ışık koşulları, farklı açılar.
- Etiketleme Roboflow ya da CVAT ile.
- **Bölme kişiye göredir:** aynı kişi hem train hem test'te olmaz. Veri artırma (augmentation) **bölmeden sonra** ve sadece train'e uygulanır.
- Public datasetlerde kişi bilgisi yok. O yüzden public veri sadece train/val için kullanılır. **Raporlanan tüm sonuçlar kendi test setimizden gelir.**

### 6.3 Gizlilik (karar)

- Yüz tanıma yok; kimlik QR kartla.
- Panelde gösterilen ve saklanan fotoğraflar **yüzü bulanıklaştırılmış** olur.
- **Eğitim fotoğrafları bulanıklaştırılmaz.** Maske yüzün üstünde olduğu için bulanık görüntüyle model eğitilemez. Bunlar sadece onam veren gönüllülerden alınır, ayrı ve erişimi kısıtlı bir yerde saklanır.
- İşçiler bilgilendirilir, kayıtlar sınırlı süre tutulur.

## 7. Değerlendirme (karar)

- Her sınıf için precision ve recall.
- **Yanlış kabul oranı (FAR):** maske uygun değilken kapının açılması. **Yanlış red oranı (FRR):** maske doğruyken kapının kapalı kalması.
- Geçiş başına karar süresi ve laptoptaki FPS.
- Sonuçlar farklı mesafelerde ve gerçek ışık koşullarında da raporlanır.
- Öneri hedef: `no_mask` ve `mask_improper` sınıflarında recall ≥ %95.

## 8. Uygulama planı (sıra)

1. **Ortam ve demo (2–3 gün):** Python 3.11 sanal ortamı, `pip install ultralytics opencv-python`. Hazır YOLO11n'i webcam'de çalıştır.
2. **Veri hazırlama (1 hafta):** Mendeley N95 için otomatik etiketleme ve kontrol; Kaggle VOC → YOLO çevirme; `data.yaml`.
3. **İlk eğitim (2–3 gün):** YOLO11n, 3 sınıf, Colab/Kaggle GPU. Webcam'de çalışan bir demo çıkar; hocaya ilk gösterilecek şey bu.
4. **Takip ve karar motoru (1 hafta):** ByteTrack ve §3'teki kural. Karar motoru için birim testleri.
5. **Kendi verimiz (1–2 hafta, 3–4 ile paralel):** çekim, etiketleme, kişiye göre bölme, ince ayar eğitimi (fine-tune).
6. **QR, veritabanı ve panel (1–2 hafta):** OpenCV QR, PostgreSQL (Docker), FastAPI, Next.js.
7. **Test ve rapor (1 hafta):** §7'deki metrikler.

Ekip bölüşümü önerisi: veri ve model (2, 3, 5); takip ve karar motoru (4); backend ve panel (6).

---

## 9. Rapor durumu

- Dosya: `SafeSight_Project_Summary.docx`. İngilizce, yaklaşık 4 sayfa, **26 kaynak**, tablo yok.
- Bölümler: 1 The Project, 2 Scope, 3 How the Prototype Works, 4 Technology Choices (4.1–4.6), 5 Dataset, 6 Evaluation, 7 Limitations, References.
- Başlıkta sadece "Yunus Emre Köybaşı · Emre Batak | October 2026" yazıyor. Taha Öneş projede değil; danışman adı başlığa yazılmayacak.
- Kontrol edilmiş ve doğru olan, tekrar tartışılmasın:
  - **Wang (2025):** "AP50 4–7 puan düştü" iddiası **kask sınıfı** için geçerli (92,4 → 85,9–88,2, Tablo 11). Makale veriyi gerçekten rastgele bölmüş ("Data split", s.6).
  - **Santos ve ark. (2025):** Dahil edilen çalışmalarda madencilik yok; raporda "inşaat, imalat ve diğer riskli sektörler" diye geçiyor.
  - **Yang ve ark. (2022):** Genel nesne tanıma için. Yüz bulanıklaştırmanın maske/kask tespitine zararı için Wang ve ark. (2021) kullanılıyor (~%7 düşüş).
  - **Al-Bayati (2023)** rapordan çıkarıldı; tablodaki 4. satırda Mat Zin 2012 ile karışmış.
- Limitations: toz maskesi CO, metan ve oksijen eksikliğine karşı korumaz; sistem ferdi kurtarıcıyı kontrol etmez; sonuçlar prototip ölçeğinde.

## 10. Literatür durumu

**Kurallar:**

- Sadece Google Scholar'da bulunabilen **akademik** çalışmalar. Bilgi sitesi ve devlet rehberi kaynak olmaz.
- **Ücretsiz / açık erişim** olmalı.
- **2020 ve sonrası.**
- APA formatı.

**Tablo sütunları (bu sırayla, id yok):**
`adı | yazar | yılı | link | tipi | keywords | kısaca özeti | citiation | kullanılan dataset | kullanılan yöntemler`

- **yazar:** sadece isimler, kurum yazılmaz.
- **tipi:** açıkça mı belirtilmiş, çıkarım mı; kullanıcıya ayrıca söylenir.
- **keywords:** o çalışmanın alt başlığı.
- **kısaca özeti:** İngilizce, en fazla 2 kısa cümle, **parantez yok**.
- **dataset ve yöntemler:** kısa, 2–4 madde.

**Durum:** 45 çalışma tamam, hedef 50.

Alt başlıklar:

- "Occupational Safety" and PPE Compliance
- Fundamentals of Object Detection
- Vision-Based PPE Detection
- PPE Datasets and Small Object Detection
- PPE Non-Compliance and Mining Accidents
- Mining Accident Statistics and Causes
- Vision-Based PPE Detection in Mining
- Object Detection in Low-Light and Dusty Environments
- Multi-Object Tracking (31–35)
- Intelligent Safety Monitoring Systems and Privacy (36–40)
- Respirable Dust Exposure and Lung Disease in Mining (41–45)
- **Eksik: Face Mask and Respirator Wearing Detection (46–50).** 5 çalışma bulunacak. Aday: Suryawanshi ve ark. (2023), raporda zaten kullanılıyor.

Tabloda bilinen sorunlar (kullanıcı düzeltecek):

- 4. satır karışık: başlık Mat Zin 2012, künye Al-Bayati 2023.
- 13 ile 18 aynı çalışma, 15 ile 17 aynı çalışma.
- 29. satırın linki yanlış.
- 2020 öncesi satırlar var: 8, 23, 24.
