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

**SafeSight**: Maden sahası girişinde, işçinin **toz maskesini doğru takıp takmadığını** kamerayla kontrol eden bir **kontrol istasyonu** prototipi. Turnike/kapı yok; model karar verir, şüpheli kayıtları **insan inceler** (human-in-the-loop).

- Her işçinin kendine ait bir QR'ı var (bir kişi, bir QR); QR ekipmanın üstünde durur (yeri açık, bkz. §3). İşçi QR ile tanınır, sonra maskesi taranır.
- Maske doğruysa kayıt `APPROVED` olur. Değilse ekran hemen "maskeni düzelt" der ve deneme hakkı verir; denemeler bitince kayıt `REJECTED` olur, fotoğrafıyla birlikte panele düşer.
- İş güvenliği sorumlusu panelde reddedilen kayıtları inceler: modelin kararını onaylar ya da düzeltir (model hata yapabilir).
- **Kimin geldiği görülebilmeli:** Biri işe alınıp yerine başkasını (ekipmanını vererek) gönderebilir. Bu yüzden kontrol fotoğrafı, işçinin kayıtlı referans fotoğrafıyla yan yana gösterilir; karşılaştırmayı insan yapar.
- **Yaptırım sistemin dışındadır** (karar). Sistem kayıt üretir, insan onaylar; ne yapılacağına şirket kendi prosedürüyle karar verir. Raporda "ceza" değil "inceleme ve geri bildirim" diye çerçevelenir.
- Üniversite bitirme projesi (Işık Üniversitesi, Yönetim Bilişim Sistemleri). Ekip: Yunus Emre Köybaşı, Emre Batak.
- **Bu bir prototip.** Laptop ve laptop kamerasıyla çalışır. Raspberry Pi, Jetson ve turnike yok.
- Repo: https://github.com/EmreBatak/SafeSight (private).

## 2. Kapsam (karar)

**Kapsamda:**

- Kullan-at toz maskeleri: **FFP2 / FFP3, N95 tipi**, ventilli ve ventilsiz.
- İstasyonda tek kişi, kameraya 1–3 m mesafe.
- Reddedilen kayıtlar için panelde insan incelemesi.

**Kapsam dışı:**

- Cerrahi maske, bez maske, bandana. Bunlar tespit hedefi değil.
- Yarım yüz ve tam yüz (kartuşlu) respiratörler.
- **Ferdi kurtarıcı.** Belde ya da omuzda taşınan, sadece acil durumda takılan oksijenli kaçış cihazı; istasyonda "takılı mı" diye kontrol edilemez.
- Maske sızdırmazlık (fit) testi, saha içinde sürekli izleme, kask, yelek ve diğer KKD.
- Fiziksel turnike/kapı kontrolü.
- **Otomatik yüz tanıma / yüz doğrulama.** Kimlik QR ile belirlenir, kişi kontrolünü insan referans fotoğrafa bakarak yapar. Otomatik yüz tanıma biyometrik veri işlemedir (KVKK'da özel nitelikli kişisel veri; açık rıza ve ek önlem ister) ve ikinci bir model demek. Raporda "ileride yapılabilir" diye geçer.
- Yaptırım / disiplin işlemleri (şirketin kendi prosedürü).

## 3. Sınıflar ve karar kuralı (karar)

YOLO modeli 3 sınıf öğrenir. Hepsi toz maskesi için tanımlıdır.

| Sınıf | Anlamı |
|---|---|
| `mask_proper` | Burun ve ağız tamamen kapalı |
| `mask_improper` | Maske var ama burun ya da ağız açıkta (burun altında, çenede vb.) |
| `no_mask` | Maske yok |

**Onay kuralı (track bazında, bir deneme için):**

1. ByteTrack her kişiye bir track ID verir. Karar motoru o track'in **son 15 gözlemini** tutar.
2. Deneme şu üç koşulun hepsi sağlanınca başarılıdır (`APPROVED`):
   - son 15 gözlemin **en az %80'i** `mask_proper`;
   - **son 5 gözlemin hepsi** `mask_proper`;
   - güven skoru **≥ 0.7** (daha düşük skorlu tespitler sayılmaz).
3. **Fail-closed:** emin olunamayan her durum başarısız denemedir. Kesin `REJECTED` olunca insan incelemesine gider.
4. **Tek kişi kuralı:** kadrajda birden fazla kişi varsa başarısız (reason: `multiple_people`).
5. Yüz bulunamazsa başarısız (reason: `no_face`).

**Kontrol akışı (istasyon):**

1. `IDLE`: QR beklenir.
2. QR okununca ekranda işçinin adı ve referans fotoğrafı görünür (yanındakiler de kimin geldiğini görür); maske taraması başlar (`SCANNING`).
3. Deneme başarılıysa → `APPROVED`, fotoğraf çekilir, kaydedilir, ekran "GEÇEBİLİRSİN" der.
4. Başarısızsa → ekran nedeni söyler ("MASKENİ DÜZELT", "deneme 1/3") ve yeni deneme başlar.
5. **En fazla 3 deneme** (ayarlanabilir). Hepsi başarısızsa → `REJECTED`, fotoğraf çekilir, kayıt panele `pending` olarak düşer.
6. Aynı işçi **üst üste 3 kez `REJECTED`** alırsa `alerts` tablosuna uyarı yazılır.

Öneriler (henüz konuşulmadı):

- Bir denemede 10 sn içinde karar çıkmazsa başarısız say (reason: `timeout`).
- ByteTrack'in `track_buffer` değerini kare sayısı yerine saniyeye göre ayarla (~2 sn). Laptop FPS'i benchmarklardan düşük olacak.
- Eşikler (0.7, %80, 15 ve 5 gözlem, 3 deneme) koda sabit yazılmaz; bir ayar dosyasında durur ve doğrulama setinde ayarlanır. Kendi ortamımızda 0.7 kimseyi onaylamayabilir (FRR ve inceleme yükü artar).
- `no_face` = "güven eşiğini geçen, 3 sınıftan hiçbir tespit yok". Modelde ayrı bir "yüz" sınıfı yok.
- **QR'ın yeri (açık):** Elde kart, maskeyi kapattığı için elendi. Öneri: yelekte göğüste büyük QR (10–15 cm; düz yüzey, yüzle aynı karede, QR ve maske aynı anda okunur). Alternatif: kask (daha kişisel ama küçük ve kavisli yüzey). 1. adımda basılı QR ile kask ve göğüs 1/2/3 m'den denenip karar verilecek. QR uzaktan okunmazsa yedek: AprilTag/ArUco işaretleri (OpenCV `cv2.aruco`).
- Onaylanan kayıtların incelenmesi iki aşamalı olsun:
  - **Test/pilot döneminde onaylananların hepsi incelenir.** FAR (maske yanlışken onay) ancak böyle ölçülür.
  - **Normal kullanımda:** eşiğe yakın onaylar (ör. `proper_ratio` sınırda) ve küçük bir rastgele örnek (ör. %5) incelemeye düşer; hepsini incelemek modeli anlamsızlaştırır, sorumlu her gün herkese bakmak zorunda kalır. Onaylananlar yine de 7 gün panelde listelenir. Oranlar ayar dosyasında.

## 4. Mimari (karar)

```
Laptop webcam
  → Kişiye özel QR (OpenCV QRCodeDetector) ile işçi kimliği
  → YOLO11n (3 sınıf)            # Ultralytics
  → ByteTrack                     # model.track(..., tracker="bytetrack.yaml")
  → Karar motoru (kural + deneme hakkı, bkz. §3)
  → Ekran mesajı ("GEÇEBİLİRSİN" / "MASKENİ DÜZELT")
  → FastAPI  → PostgreSQL (Docker)
  → Next.js panel (kontroller, inceleme kuyruğu, uyarılar, istatistik)
```

- **Model:** YOLO11n, tek model, 3 sınıf. Pose + sınıflandırıcı yolu ileride opsiyonel.
- **Eğitim:** Google Colab ya da Kaggle'ın ücretsiz GPU'su. Laptop CPU'su sadece çalıştırma (inference) için.
- **Panel:** Next.js (karar). Streamlit alternatif olarak konuşulmuştu ama Next.js'te kalındı.
- **İstasyon uygulaması:** Python masaüstü uygulaması, **PySide6** (karar). Kamera + model + takip ayrı bir `QThread`'de; arayüz sadece gösterir. Karar motoru Qt'den bağımsız saf Python. Panel Next.js'te kalır (masaüstüne taşınmaz).
- Öneri: Next.js'e süre yetmezse yedek plan olarak FastAPI'nin sunduğu basit bir HTML sayfası.
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
  pyproject.toml        # paket + bağımlılıklar; `pip install -e .[dev]`
  src/
    station/            # PySide6 istasyon uygulaması; `python -m station`
      app.py            #   giriş noktası, argümanlar
      worker.py         #   QThread: kamera + model (+ ileride takip, QR)
      ui/               #   pencereler ve ekran mesajları
    decision/           # karar motoru (§3), birim testli, Qt'den bağımsız
  api/                  # FastAPI
  dashboard/            # Next.js
  models/               # eğitilmiş ağırlıklar (git'e girmez)
  docker-compose.yml    # PostgreSQL
  tests/
```

## 5. Veritabanı (karar)

```sql
workers  (id, badge_no, name, department, active,
          reference_photo_path)  -- işe kayıtta onamla çekilen fotoğraf
stations (id, name, location)
checks   (id, worker_id, station_id, started_at, ended_at,
          attempts,        -- kullanılan deneme sayısı
          decision,        -- 'APPROVED' | 'REJECTED'
          reason,          -- 'proper' | 'improper' | 'no_mask' | 'no_face' | 'multiple_people'
          proper_ratio, snapshot_path,
          review_status,   -- NULL (APPROVED) | 'pending' | 'confirmed' | 'overturned'
          reviewed_by, reviewed_at, review_note)
alerts   (id, worker_id, check_id, type, created_at, acknowledged)
```

- `confirmed`: sorumlu modelin reddini onayladı. `overturned`: model yanılmış, maske aslında doğru.

**API (karar):** `POST /checks`, `PATCH /checks/{id}/review` (inceleme sonucu), `GET /stats`, kamera görüntüsü için bir MJPEG stream.
Panelin ihtiyaç duyacağı ek uçlar (`GET /checks`, `GET /alerts`) öneri.

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
- **WWMR-DB** (Marceddu vd., 2022; tabloda 43): 42 gönüllüden 1.222 selfie, 8 takılma sınıfı (burun altı, çene altı vb.), ventilli/ventilsiz respiratör de var, YOLO etiketli, IEEE DataPort'ta açık. Önceki "sadece COVID tipi maske" notu yanlıştı. **Öneri:** `mask_improper` için gerçekçi ek doğrulama verisi olarak değerlendirilebilir (lisans ve içerik indirip kontrol edilmeli; bilgi tablodaki özetten, makaleden değil).
- **Roboflow HalfFaceMask:** Yarım yüz respiratör içeriyor, kapsam dışı. Etiketleri de karışık; tam yüz maskeler "half-face" diye etiketlenmiş.
- **MaskTheFace (MIT lisanslı araç):** Maskesiz yüzlere yapay N95/KN95 giydiriyor. Veri az kalırsa opsiyonel. Dikkat: Marceddu vd. (2022), sentetik maskeli veriyle eğitilen modelin gerçek selfie'lerde yaklaşık dörtte bir doğruluğa düştüğünü gösteriyor.

Öneriler (henüz konuşulmadı):

- Mendeley otomatik etiketleme için 1 hafta iyimser. Önce 50 görüntüyle dene, otomatik kutuların ne kadarının işe yaradığını ölç, plana ona göre karar ver.
- Kaggle'daki maskesiz yüzler kalabalık fotoğraflarda küçük; 1–3 m tam kare görüntüye benzemez. `no_mask` ağırlıklı olarak kendi verimizle ya da tek kişinin yakından göründüğü maskesiz yüz verisiyle eğitilsin (maskesiz yüzde yüz tespit modelleri iyi çalışır, otomatik etiketlemesi kolay).
- **Etiket kutusu yüzü kapsar** (maskeyi değil), çünkü `no_mask`'ta kutulanacak maske yok. Tüm datasetlerde aynı kural.

### 6.2 Kendi verimiz (asıl test seti)

- Ventilli ve ventilsiz birkaç FFP2/FFP3 maske alınacak.
- 15–20 gönüllü, **yazılı onamla**, laptop kamerasıyla çekilecek. Üç durum çekilecek: doğru takılmış, yanlış takılmış (burun ya da çene açıkta), maske yok.
- Mesafe 1–3 m, farklı ışık koşulları, farklı açılar.
- Etiketleme Roboflow ya da CVAT ile.
- **Bölme kişiye göredir:** aynı kişi hem train hem test'te olmaz. Veri artırma (augmentation) **bölmeden sonra** ve sadece train'e uygulanır.
- Public datasetlerde kişi bilgisi yok. O yüzden public veri sadece train/val için kullanılır. **Raporlanan tüm sonuçlar kendi test setimizden gelir.**

Öneriler (henüz konuşulmadı):

- 15–20 gönüllü kişiye göre bölününce test'e 3–4 kişi kalır; az. 25–30 gönüllü hedeflensin, her kişi iki farklı gün ve ışıkta çekilsin.
- Kişiye göre çapraz doğrulama (ör. 5 kat) ile sonuçlar daha güvenilir raporlanır.
- Kendi veri toplama §8'deki 5. adıma bırakılmasın, 2. adımla paralel başlasın (maske alımı ve onam formları zaman alır).

### 6.3 Gizlilik (karar)

- Otomatik yüz tanıma yok; kimlik QR ile, kişi kontrolü insan gözüyle.
- **İnceleme fotoğrafları bulanıklaştırılmaz.** İnceleyen kişi hem maskeyi hem kimin geldiğini görmeli; tüm yüz ya da göz bölgesi bulanıklaştırma ikisini de bozuyordu. Gizlilik bulanıklaştırmayla değil şunlarla sağlanır:
  - fotoğrafları sadece yetkili sorumlu görür, her erişim loglanır;
  - fotoğraflar **7 gün** saklanır, sonra silinir; inceleme bu süre içinde yapılır, karar kaydı fotoğrafsız kalır;
  - fotoğrafların dışarı verilmesi, dışa aktarılması ya da başka amaçla kullanılması **yasaktır**;
  - kadrajdaki diğer kişiler bulanıklaştırılır.
- **Eğitim fotoğrafları** sadece onam veren gönüllülerden alınır, ayrı ve erişimi kısıtlı bir yerde saklanır.
- İşçiler bilgilendirilir. Referans fotoğraf işe kayıtta onamla çekilir.
- Not (hukuki görüş değil): fotoğrafa insanın bakıp karşılaştırması genelde biyometrik veri işleme sayılmaz; otomatik tanıma sayılır. Raporda bu ayrım yazılır.
- Öneri: incelenen kayıtlar (özellikle `overturned`) yeni etiketli veri olur ve modeli yeniden eğitmekte kullanılabilir; ama işçi fotoğrafıyla eğitim için ayrıca onam gerekir.

## 7. Değerlendirme (karar)

- Her sınıf için precision ve recall.
- **Yanlış kabul oranı (FAR):** maske uygun değilken `APPROVED`. **Yanlış red oranı (FRR):** maske doğruyken `REJECTED`.
- **İnceleme yükü:** insanın incelemesi gereken kayıt oranı (FRR doğrudan sorumlunun iş yüküne dönüşür) ve incelemede `overturned` oranı.
- Kontrol başına karar süresi, ortalama deneme sayısı ve laptoptaki FPS.
- Sonuçlar farklı mesafelerde ve gerçek ışık koşullarında da raporlanır.
- Öneri hedef: `no_mask` ve `mask_improper` sınıflarında recall ≥ %95.

## 8. Uygulama planı (sıra)

1. **Ortam ve demo (2–3 gün):** Python 3.11 sanal ortamı, `pip install -e .[dev]`. Hazır YOLO11n'i PySide6 penceresinde webcam'de çalıştır.
2. **Veri hazırlama (1 hafta):** Mendeley N95 için otomatik etiketleme ve kontrol; Kaggle VOC → YOLO çevirme; `data.yaml`.
3. **İlk eğitim (2–3 gün):** YOLO11n, 3 sınıf, Colab/Kaggle GPU. Webcam'de çalışan bir demo çıkar; hocaya ilk gösterilecek şey bu.
4. **Takip ve karar motoru (1 hafta):** ByteTrack, §3'teki kural, deneme hakkı ve istasyon akışı. Karar motoru için birim testleri.
5. **Kendi verimiz (1–2 hafta, 3–4 ile paralel):** çekim, etiketleme, kişiye göre bölme, ince ayar eğitimi (fine-tune).
6. **QR, veritabanı ve panel (1–2 hafta):** OpenCV QR, PostgreSQL (Docker), FastAPI, Next.js; panelde inceleme kuyruğu (onayla / düzelt).
7. **Test ve rapor (1 hafta):** §7'deki metrikler.

Ekip bölüşümü önerisi: veri ve model (2, 3, 5); takip ve karar motoru (4); backend ve panel (6).

---

## 9. Rapor durumu

- Dosya: `SafeSight_Project_Summary.docx`. İngilizce, yaklaşık 4 sayfa, **26 kaynak**, tablo yok.
- **Güncellenmeli:** Rapor hâlâ kapı/turnike modelini anlatıyor; kontrol istasyonu + insan incelemesine (§1, §3) göre düzeltilmeli.
- Bölümler: 1 The Project, 2 Scope, 3 How the Prototype Works, 4 Technology Choices (4.1–4.6), 5 Dataset, 6 Evaluation, 7 Limitations, References.
- Başlıkta sadece "Yunus Emre Köybaşı · Emre Batak | October 2026" yazıyor. Taha Öneş projede değil; danışman adı başlığa yazılmayacak.
- Kontrol edilmiş ve doğru olan, tekrar tartışılmasın:
  - **Wang (2025):** "AP50 4–7 puan düştü" iddiası **baretsiz (non-helmet) sınıfı** için geçerli (92,4 → 85,9–88,2, Tablo 11); makale non-PPE sınıflarını tespit ediyor, raporda "kask sınıfı" denmesin. Makale veriyi gerçekten rastgele bölmüş ("Data split", s.6).
  - **Santos ve ark. (2025):** Dahil edilen çalışmalarda madencilik yok; raporda "inşaat, imalat ve diğer riskli sektörler" diye geçiyor.
  - **Yang ve ark. (2022):** Genel nesne tanıma için. Yüz bulanıklaştırmanın maske/kask tespitine zararı için Wang ve ark. (2021) kullanılıyor (~%7 düşüş).
  - **Al-Bayati (2023)** rapordan çıkarıldı; tablodaki 4 numarada Mat Zin & Ismail ile karışmış.
- Limitations: toz maskesi CO, metan ve oksijen eksikliğine karşı korumaz; sistem ferdi kurtarıcıyı kontrol etmez; sonuçlar prototip ölçeğinde. Eklenecek: ekipman/QR başkasına verilebilir (kişi kontrolü insana bağlı, otomatik yüz doğrulama ileride); gerçek sahada QR tozlanıp okunamayabilir.

## 10. Literatür durumu

**Kurallar:**

- Sadece Google Scholar'da bulunabilen **akademik** çalışmalar. Bilgi sitesi ve devlet rehberi kaynak olmaz.
- **Ücretsiz / açık erişim** olmalı.
- **Tercihen 2020 ve sonrası.** Kesin şart değil; 1–2 istisna olabilir.
- APA formatı.

**Tablo sütunları (bu sırayla):**
`adı | yazar | yılı | link | tipi | keywords | kısaca özeti | citiation | kullanılan dataset | kullanılan yöntemler`

- **yazar:** sadece isimler, kurum yazılmaz.
- **tipi:** açıkça mı belirtilmiş, çıkarım mı; kullanıcıya ayrıca söylenir.
- **keywords:** o çalışmanın alt başlığı.
- **kısaca özeti:** İngilizce, kısa, yaklaşık 2 cümle (biraz uzun olması sorun değil), parantezden kaçın.
- **dataset ve yöntemler:** kısa, 2–4 madde.

**Durum:** 50 çalışma tamam (dosya: `Proje Literature Review.xlsx`). Numaralar tablodaki `id` sütunudur.

Alt başlıklar (keywords sütununa göre):

- "Occupational Safety" and PPE Compliance: 1, 4, 6, 9, 10
- Fundamentals of Object Detection: 2, 3, 5, 7, 8
- Vision-Based PPE Detection: 11–15
- PPE Datasets and Small Object Detection: 16–20
- PPE Non-Compliance and Mining Accidents: 21, 22, 24, 27, 28, 29
- Mining Accident Statistics and Causes: 23
- Vision-Based PPE Detection in Mining: 25, 26
- Object Detection in Low-Light and Dusty Environments: 30
- Multi-Object Tracking: 31–35
- Intelligent Safety Monitoring Systems and Privacy: 36–40
- Face Mask and Respirator Wearing Detection: 41–43
- Lightweight Real-Time Object Detection: 44, 45
- Respirable Dust Exposure and Lung Disease in Mining: 46–50

Not: Suryawanshi ve ark. (2023) raporda kullanılıyor ama tabloda yok.

Tablonun biçim düzeltmeleri kullanıcıya ait (tez yazımında); kod çalışmasında gündeme getirme.
