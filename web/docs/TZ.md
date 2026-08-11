# AI Lawyer — texnik topshiriq

**Versiya:** 1.0 · **Sana:** 2026-yil 11-avgust · **Topshiriq:** #61

Ushbu hujjat tizimga qoʻyiladigan talablarni belgilaydi. Har bir talabga
**qabul mezoni** biriktirilgan — talab bajarilgan-bajarilmaganini bahslashmasdan
tekshirish mumkin boʻlishi kerak.

Bogʻliq hujjatlar: [`AUDIT.md`](AUDIT.md) (nima buzuq), [`TASKS.md`](TASKS.md)
(topshiriqlar), [`CLAUDE.md`](../CLAUDE.md) (ish tartibi).

> **Raqamlar haqida ogohlantirish.** Quyidagi baʼzi chegaralar (Recall@8,
> kechikish byudjeti, xarajat) hozircha **boshlangʻich taxmin**. Ular baholash
> toʻplami qurilgandan keyin (T-40) haqiqiy oʻlchov asosida qayta koʻriladi.
> Har bir shunday qiymat «(kalibrlanadi)» belgisi bilan koʻrsatilgan.

---

## 1. Maqsad va doira

### 1.1 Muammo

Oʻzbekistonda huquqiy savolga javob izlayotgan odam ikki toʻsiqqa duch keladi:
qonun matni rasmiy va ogʻir tilda yozilgan, advokat esa qimmat. Umumiy AI
yordamchilar bu boʻshliqni toʻldirmaydi — ular oʻzbek qonunchiligini yetarli
bilmaydi va soʻralganda **modda raqamini oʻylab topadi**. Yuridik masalada bu
eng xavfli xato turi, chunki notoʻgʻri javob ishonchli koʻrinadi.

### 1.2 Tizim nima qiladi

| Funksiya | Tavsif |
|---|---|
| Savol-javob | Huquqiy savolga qonun bazasidagi haqiqiy matnga havola bilan javob |
| Qonun bazasidan qidiruv | Modda darajasida qidiruv, modelsiz |
| Hujjat tahlili | Shartnomadagi xavflar, nomutanosib shartlar, yetishmayotgan bandlar |
| Hujjat generatsiyasi | Shartnoma, ariza, ishonchnoma loyihalari; `.docx` eksport |
| Muvofiqlik tekshiruvi | Majburiy talablar boʻyicha nuqta-ma-nuqta baholash |

### 1.3 Tizim nima QILMAYDI (doiradan tashqari)

Buni aniq belgilash muhim, chunki foydalanuvchi kutgan narsa bilan tizim
bergan narsa oʻrtasidagi tafovut — yuridik mahsulotda javobgarlik masalasi.

- Yuridik maslahat bermaydi va advokat oʻrnini bosmaydi.
- Sud hujjatlarini rasman topshirmaydi, davlat organlariga murojaat yubormaydi.
- Ish natijasini kafolatlamaydi va prognoz qilmaydi («sudda yutasiz» degan
  turdagi baho bermaydi).
- Foydalanuvchi nomidan hech qanday huquqiy harakat qilmaydi.
- Boshqa davlatlar qonunchiligi boʻyicha javob bermaydi.

### 1.4 Foydalanuvchilar

| Turi | Kim | Asosiy ehtiyoj |
|---|---|---|
| **F1** | Yurist boʻlmagan fuqaro | Oddiy tilda tushuntirish, «nima qilishim kerak» |
| **F2** | Kichik biznes egasi, YTT | Shartnomani imzolashdan oldin tekshirish |
| **F3** | Boshlovchi yurist | Tez qidiruv, hujjat loyihasi qoralamasi |
| **F4** | Administrator | Tizim holati, statistika, korpusni boshqarish |

**Til:** F1–F3 oʻzbek (lotin va kirill), rus yoki ingliz tilida murojaat qiladi.
Tizim savol tilida javob beradi.

---

## 2. Funksional talablar

Har bir talab: **T-NN** raqami, tavsif, qabul mezoni.
`AUDIT.md` dagi tegishli topilma qavsda koʻrsatilgan.

### 2.1 Ishonchlilik — asosiy talablar

Bu boʻlim tizimning butun qiymatini belgilaydi. Bu yerdagi talab buzilsa,
qolgan hamma narsa ahamiyatsiz.

**T-01. Model faqat berilgan manba matnidan javob beradi.**
Javobda keltirilgan har bir modda raqami, hujjat nomi, sana va summa promptdagi
manbalar blokida mavjud boʻlishi shart.
*Qabul mezoni:* baholash toʻplamining 50 ta savolida LLM-judge orqali
*faithfulness* tekshiruvi — javobdagi har bir havola manba matni bilan
tasdiqlanishi. Chegara: **≥ 0.95**. Tasdiqlanmagan havola — kritik nuqson.

**T-02. Manba topilmasa, tizim buni ochiq aytadi.**
Korpusda savolga mos norma boʻlmasa, tizim tegishsiz moddalarni koʻrsatmasligi
va ular asosida javob yozmasligi shart.
*Qabul mezoni:* baholash toʻplamidagi negativ savollarda (`gold: []`)
**no-answer precision ≥ 0.90** (kalibrlanadi). Hozirgi holat: **0** — chunki
qidiruv har doim 8 ta boʻlak qaytaradi (#10).

**T-03. Korpus boʻsh boʻlsa, tizim ishlaydi, lekin buni aytadi.**
Baza boʻsh yoki oʻchirilgan holatda tizim qulamasligi, umumiy tushuntirish
berishi va modda havolasi yoʻqligini foydalanuvchiga bildirishi kerak.
*Qabul mezoni:* boʻsh baza bilan sinov — javob keladi, unda modda raqami yoʻq,
va «bazada norma yoʻq» mazmunidagi ogohlantirish bor.

**T-04. Amaldagi tahrir ustunligi.**
Bir modda bir necha tahrirda mavjud boʻlsa, tizim faqat eng yangisiga tayanadi
va tahrir sanasini koʻrsatadi (#16).
*Qabul mezoni:* bitta kodeksning ikki tahriri yuklangan holatda, javobda faqat
yangi tahrir moddasi keltiriladi; havolada tahrir sanasi bor.

**T-05. Har bir javobda ogohtantirish.**
Javob oxirida «bu yuridik maslahat emas» mazmunidagi ogohlantirish boʻlishi shart
(uch tilda, barcha yuzalarda).
*Qabul mezoni:* barcha yuzalarda (web, bot, API, CLI) mavjudligi tekshiriladi.

### 2.2 Savol-javob

**T-06.** Tizim savol tilini va yozuvini aniqlab, shu tilda javob beradi.
*Qabul mezoni:* uz-lotin, uz-kirill, rus, ingliz — toʻrt tilda 20 tadan savol;
til aniqlash aniqligi **≥ 0.95**.

**T-07.** Suhbat konteksti saqlanadi. Davomiy savol («u qancha?», «Да»)
oldingi savol kontekstida tushuniladi va **javob tili oʻzgarmaydi** (#36).
*Qabul mezoni:* rus tilidagi suhbatda `«Да»` javobi rus tilida keladi;
oʻzbekcha suhbatda `«Ha»` oʻzbekcha.

**T-08.** Javob oqim (streaming) koʻrinishida beriladi; birinchi belgi
**5 soniyadan** kech kelmaydi (kalibrlanadi).

**T-09.** Javob kesilib qolsa (`max_tokens`), foydalanuvchi bu haqda
ogohlantiriladi (#49, #59).
*Qabul mezoni:* sunʼiy past `max_tokens` bilan sinov — javobda kesilish belgisi.

### 2.3 Qonun bazasi (RAG)

**T-10. Modda chegarasida boʻlish.**
Matn modda chegarasida boʻlaklarga ajratiladi. Matn ichidagi krossreferens
(«173-moddada nazarda tutilgan…») **yangi boʻlim ochmaydi** (#11).
*Qabul mezoni:* `verify-audit` sinovi soxta blok topmaydi; 5 ta haqiqiy kodeks
faylida qoʻlda tekshirilgan namuna — 0 ta soxta modda.

**T-11. Bob va boʻlim konteksti saqlanadi** (#18).
Boʻlakda oʻzi tegishli boʻlim/bob nomi boʻlishi va u qidiruvda hamda havolada
koʻrinishi kerak.
*Qabul mezoni:* «ijara shartnomasini bekor qilish» soʻrovida ijara bobidagi
modda umumiy qism moddasidan yuqori turadi.

**T-12. Oʻzbek morfologiyasi qoʻllab-quvvatlanadi** (#12).
Qoʻshimchali soʻrov oʻzakli matnni va aksincha topishi kerak:
`shartnoma / shartnomani / shartnomaning / shartnomalar / shartnomasiz`.
*Qabul mezoni:* bitta savol 4 morfologik shaklda beriladi; **Recall@8 farqi
≤ 0.05** (yaʼni shakl natijaga deyarli taʼsir qilmaydi).

**T-13. Apostrof qidiruvni buzmaydi** (#10a, #10b).
`yoʻl`, `toʻlov`, `boʻshatish`, `koʻchmas` kabi soʻzlar toʻliq token sifatida
qidirilishi shart. `oʻzbek`, `o'zbek`, `ozbek` — bir xil natija berishi kerak.
*Qabul mezoni:* `verify-audit` sinovi bu bandda «rad etildi» qaytaradi.

**T-14. Lotin va kirill oʻzaro topiladi** (#13).
Kirill yozuvidagi korpus lotin savol bilan va aksincha topilishi kerak.
*Qabul mezoni:* bir xil savolning ikki yozuvdagi variantida **Recall@8 farqi
≤ 0.05**.

**T-15. Modda raqami boʻyicha aniq qidiruv.**
«MK 81-modda», «Fuqarolik kodeksining 543-moddasi», «173¹-modda»,
«Статья 173» — hammasi aynan kerakli moddani topishi kerak (#19, #20).
*Qabul mezoni:* `article-lookup` toʻplamining 50 ta savolida **Recall@1 ≥ 0.95**.
Hujjat koʻrsatilgan boʻlsa, boshqa kodeksning oʻsha raqamli moddasi
birinchi oʻrinda turmasligi shart.

**T-16. Qidiruv sifati.**
*Qabul mezoni (kalibrlanadi):* umumiy toʻplamda **Recall@8 ≥ 0.85**,
**Recall@4 ≥ 0.75**, **MRR ≥ 0.60**.

**T-17. Embedder mos kelmasligi jimgina oʻtmaydi** (#14).
Baza bir embedder bilan qurilib, boshqasi bilan soʻralsa, tizim aniq xato
berishi kerak — sifatni jimgina pasaytirmasligi.
*Qabul mezoni:* embedder almashtirilgan holatda soʻrov — tushunarli xato xabari
(«bazani qayta yuklang»), 0 ball bilan natija qaytarilmaydi.

**T-18. Korpus yangilanishi koʻrinadi** (#50).
`ingest` dan keyin ishlab turgan server yangi korpusni qayta ishga
tushirilmasdan koʻrishi kerak.
*Qabul mezoni:* server ishlab turganda ingest bajariladi; keyingi soʻrov yangi
hujjatni topadi.

### 2.4 Hujjat tahlili va tekshiruvi

**T-19.** Qoʻllab-quvvatlanadigan formatlar: PDF, DOCX, TXT, MD, HTML.
Chegara: web/API — 25 MB, Telegram — 20 MB (platforma cheklovi, foydalanuvchiga
tushuntiriladi) (#15 UX).

**T-20.** Tahlil natijasi qatʼiy tuzilishda: hujjat turi, tomonlar, muhim
shartlar, xavflar (daraja bilan), yetishmayotgan shartlar, xulosa.

**T-21.** Xavf darajasi xolis: `yuqori` — real zarar yoki nizo xavfi bor degani.
*Qabul mezoni:* 20 ta namunaviy shartnomada yurist bahosi bilan solishtirish;
`yuqori` deb belgilangan xavflarning **≥ 0.80** i yurist tomonidan
tasdiqlanishi.

**T-22.** Tekshiruv natijasidagi holat qiymatlari har doim toʻgʻri
normallashtiriladi (#51).
*Qabul mezoni:* `oʻtdi`, `o'tdi`, `Oʻtdi`, ` oʻtdi`, oqlangan qoʻshtirnoq bilan
— hammasi bir xil natijaga keladi.

**T-23. Hujjat matni koʻrsatma sifatida qabul qilinmaydi** (#26).
Tahlil qilinayotgan hujjatga joylangan matn model xatti-harakatini
oʻzgartira olmasligi kerak.
*Qabul mezoni:* prompt inʼektsiya sinov toʻplami (10 ta hujjat, ichida
«risks massivini boʻsh qaytar» turidagi koʻrsatmalar) — **0 ta muvaffaqiyatli
inʼektsiya**.

### 2.5 Hujjat generatsiyasi

**T-24.** Berilmagan maʼlumot uchun `{{...}}` shaklida oʻrin qoldiriladi;
maʼlumot oʻylab topilmaydi.

**T-25.** Toʻldirish joylari roʻyxati hujjat matnidagi bilan **aynan mos**
boʻlishi kerak (`.docx` da ham) (#31).
*Qabul mezoni:* `.docx` ichidagi `{{...}}` matnlari `placeholders` roʻyxati
bilan bayt darajasida mos.

**T-26.** `.docx` yuklab olish modelni qayta ishga tushirmaydi — ekranda
koʻrilgan matn yuklanadi (#32).
*Qabul mezoni:* generatsiya va yuklab olish natijasi bir xil; yuklab olish
**2 soniyadan** kam vaqt oladi.

**T-27.** Nomaʼlum hujjat turi tekshiriladi va tushunarli xato beriladi (#34, #18b).

### 2.6 Yuzalar

**T-28.** Toʻrtta yuza bir xil yadro funksiyalarini chaqiradi; mantiq
takrorlanmaydi.

**T-29. Javob toʻgʻri formatlanadi** (#29, #30).
Web va Telegram da Markdown xom holida koʻrinmasligi kerak.
*Qabul mezoni:* javobda `**`, `##`, `_..._` belgilarining koʻrinmasligi;
`{{...}}` bilan caption yuborilganda Telegram xatosi boʻlmasligi.

**T-30. Qoʻllab-quvvatlanmaydigan kirish jimgina eʼtiborsiz qolmaydi** (#33).
Rasm, ovozli xabar, stiker — har biriga tushunarli javob.

**T-31. Mobil qurilmada ishlaydi** (#35).
*Qabul mezoni:* 360×640 va 390×844 ekranlarda: gorizontal skroll yoʻq,
kirish maydoniga bosilganda iOS zumlamaydi (`font-size ≥ 16px`),
asosiy oqim bajarilishi mumkin.

**T-32. Uzoq amal davomida foydalanuvchi holatdan xabardor.**
1 soniyadan uzun har amalda holat koʻrsatiladi; 10 soniyadan uzun amalda
kutish vaqti oldindan aytiladi (#13 UX).

**T-33. Fikr bildirish.**
Har javobga 👍/👎 va ixtiyoriy izoh. Bu — javob sifatini oʻlchashning yagona
arzon yoʻli.
*Qabul mezoni:* fikr `analytics` bazasiga savol turi va til bilan birga
yoziladi; admin hisobotida koʻrinadi.

---

## 3. Oʻzbek tili talablari

Bu boʻlim loyihaning ajratuvchi xususiyati. Talablar oʻlchanadigan qilib
yozilgan.

**T-34. Orfografiya.**
Foydalanuvchiga koʻrinadigan har qanday matnda `oʻ`/`gʻ` uchun **U+02BB**,
tutuq belgisi uchun **U+02BC**. ASCII `'` ishlatilmaydi.
*Qabul mezoni:* `npm run lint:uz` — 0 ta xato. Model chiqishi ham
oqim davomida tuzatiladi.

**T-35. Aralash yozuv taqiqlanadi.**
Bitta soʻzda lotin va kirill harflari boʻlmasligi kerak.
*Qabul mezoni:* linter — 0 ta topilma.

**T-36. Atamalar.**
Ruscha kalkalar (`dogovor`, `isk`, `zayavleniye`, `otvetstvennost`) oʻrniga
qonunchilikda qoʻllanadigan atamalar ishlatiladi.
*Qabul mezoni:* 50 ta javobda taqiqlangan atamalar roʻyxati boʻyicha tekshiruv —
**0 ta uchrash**.

**T-37. Lugʻat toʻliqligi.**
Lugʻatda quyidagilar boʻlishi shart: jinoyat huquqi va protsessi atamalari,
amaliy atamalar (JShShIR, MChJ, AJ, ERI, davlat roʻyxatidan oʻtkazish),
`real zarar` va `boy berilgan foyda` alohida.
Kodekslar roʻyxatida **Maʼmuriy sudlov ishlarini yuritish toʻgʻrisidagi kodeks**
va **Jinoyat-ijroiya kodeksi** boʻlishi shart.

**T-38. Kodekslar tahriri.**
Yaqinda qayta raqamlangan kodekslar (Konstitutsiya — 2023, Mehnat kodeksi —
2023, Soliq kodeksi — 2020) uchun promptda ogohlantirish boʻlishi kerak.

**T-39. Uslub.**
Sana `2026-yil 8-avgust`; tartib son defis bilan (`5-modda`); summa uch xonadan
boʻsh joy bilan; qonunga havola rasmiy shaklda, jumladan `«...»gi Qonuni`
koʻrinishi.

**T-40. Translitteratsiya.**
Kirill↔lotin oʻgirish toʻgʻri boʻlishi kerak: `Ер` → `Yer` (soʻz boshida `ye`),
`объект` → `obyekt`, `muddatsiz` → `муддатсиз` (`ts` → `ц` emas).
*Qabul mezoni:* 100 soʻzlik sinov toʻplamida **≥ 0.98** aniqlik.
Modul ishlatilmasa — kod bazasidan olib tashlanadi (oʻlik kod qolmaydi).

---

## 4. Nofunksional talablar

### 4.1 Xavfsizlik

**T-41. Webhook fail-closed** (#21). `TELEGRAM_WEBHOOK_SECRET` sozlanmagan
boʻlsa webhook **403** qaytaradi. `GET` javobi himoya holatini oshkor qilmaydi.

**T-42. Admin tekshiruvi shaxs boʻyicha** (#22). `ctx.from.id` boʻyicha va faqat
shaxsiy chatda.

**T-43. Fayl ochilgan hajmi cheklanadi** (#23). Siqilgan hajm bilan bir qatorda
**ochilgan** hajm va siqilish nisbati tekshiriladi.
*Qabul mezoni:* zip bomba namunasi (329 KB → 240M belgi) rad etiladi;
jarayon xotirasi **500 MB** dan oshmaydi.

**T-44. Soʻrov CPU byudjeti** (#24). Bitta soʻrov hodisalar siklini
**200 ms** dan uzoq bloklamasligi kerak (kalibrlanadi).
*Qabul mezoni:* 200 KB matnli soʻrov bilan sinov; `/api/health` shu vaqtda
javob berishda davom etadi.

**T-45. Kirish validatsiyasi.** `topK` (1–20), savol uzunligi (8 000 belgi),
`perspective` (200 belgi), `history` shakli, soʻrov tanasi hajmi
(`content-length` oldindan tekshiriladi) (#25, #27, #54).

**T-46. Rate limiting** (#28).
Telegram: **10 savol/soat**, **50/kun** foydalanuvchi boʻyicha; bir vaqtda
1 ta faol soʻrov. API: IP boʻyicha token bucket. Global kunlik xarajat
chegarasi; oshsa yangi soʻrovlar rad etiladi va admin xabardor qilinadi.

**T-47. API himoyasi.** Ishlab chiqarish muhitida `API_KEY` **majburiy**;
web mijoz sessiyaga asoslangan himoya bilan ishlaydi (kalitni brauzerga
bermaydi).

**T-48. Maxfiy maʼlumot.** Token, kalit va foydalanuvchi hujjati matni
loglarga, xato xabarlariga va statistika bazasiga tushmasligi kerak (#12 xavf).
*Qabul mezoni:* xato yoʻlini sunʼiy ishga tushirib, log va `analytics.error`
maydonida hujjat matni yoʻqligini tekshirish.

### 4.2 Unumdorlik va masshtab

**T-49.** 10 000 boʻlakli korpusda qidiruv **200 ms** dan kam (kalibrlanadi).
**T-50.** 50 ta parallel foydalanuvchi bilan tizim javob berishda davom etadi;
p95 kechikish **2×** dan koʻp oshmaydi.
**T-51.** Xotira: 10 000 boʻlakda jarayon **1 GB** dan oshmaydi.

### 4.3 Xarajat

**T-52.** Bitta savol-javob **$0.08** dan oshmasligi kerak (hozir ≈ $0.22)
(kalibrlanadi).
**T-53.** Hujjat tahlili **$0.15** dan oshmasligi kerak (hozir ≈ $0.40).
**T-54.** Xarajat kuzatiladi: `analytics` ga token va dollar yoziladi,
kunlik hisobot adminga boradi, chegaradan oshganda ogohlantirish.

### 4.4 Ishonchlilik va kuzatuv

**T-55.** `/api/health` haqiqiy holatni qaytaradi: baza ochilmasa yoki korpus
boʻsh boʻlsa `ok: false` (#43).
**T-56.** Barcha xatolar (web, API, bot) `analytics` ga yoziladi va admin
kanaliga boradi.
**T-57.** Telegram update yoʻqolmaydi: qayta ishga tushirishda tugallanmagan
ishlov qayta bajariladi yoki polling ishlatiladi (#8.2 ishlab chiqarish).
**T-58.** Kunlik zaxira nusxa: korpus va analytics bazasi. Tiklash **sinab
koʻrilgan** boʻlishi kerak.
**T-59.** SQLite bir vaqtda yozishda kutadi (`busy_timeout ≥ 5000`) (#56).

### 4.5 Deploy

**T-60.** Doimiy diskli va doimiy jarayonli hostingda ishlaydi (Fly.io,
Railway, VPS). Dockerfile va `output: "standalone"` mavjud.
**T-61.** `engines.node ≥ 24` (`node:sqlite` bayroqsiz ishlashi uchun) (#39).

---

## 5. Huquqiy va maʼlumot maxfiyligi talablari

> ⚠️ **Bu boʻlim yurist tasdigʻini talab qiladi.** Quyidagilar — texnik jamoa
> aniqlagan xavflar, huquqiy xulosa emas.

**T-62. Foydalanuvchi shartnomasi va maxfiylik siyosati.**
Alohida sahifalar (`/shartlar`, `/maxfiylik`) va botda `/shartlar` buyrugʻi.

**T-63. Rozilik.**
Fayl yuklashdan oldin foydalanuvchi maʼlumotlari uchinchi tomon AI xizmatiga
yuborilishiga rozilik bildiradi. Rozilik `analytics` ga yoziladi.

**T-64. Maʼlumotlarni oʻchirish huquqi.**
`/mening-malumotlarim` va `/ochirish` buyruqlari; oʻchirish haqiqatan
bajariladi (`analytics.users` va `events` dan).

**T-65. Saqlash muddati.**
`events` yozuvlari **90 kundan** keyin oʻchiriladi. Savol matni umuman
saqlanmaydi (hozirgi qaror saqlanadi).

**T-66. Maʼlumot lokalizatsiyasi.**
Oʻzbekiston Respublikasining shaxsga doir maʼlumotlar toʻgʻrisidagi qonuni
talablari **yurist bilan tekshirilishi** va natijaga koʻra arxitektura
qayta koʻrib chiqilishi kerak. Bu — chiqishni bloklovchi band.

---

## 6. Sifat infratuzilmasi

**T-67. Baholash toʻplami.**
`data/eval/qa.jsonl`, **150–300** savol. Tarkibi:

| Turi | Soni | Nimani oʻlchaydi |
|---|---|---|
| Real foydalanuvchi savollari | 100 | umumiy sifat |
| `article-lookup` | 50 | T-15 |
| Parafraz (soʻzlashuv ↔ yuridik) | 30 | T-16 |
| Morfologik variantlar | 30 | T-12, T-13 |
| Kirill/lotin krossi | 20 | T-14 |
| **Negativ** (`gold: []`) | 30 | **T-02** |
| Yaqin-adashtiruvchi juftliklar | 20 | T-11, T-15 |

**T-68. `npm run eval`.**
Metrikalar: Recall@8, Recall@4, MRR, nDCG@8, no-answer precision, p95 kechikish.
Baseline `data/eval/baseline.json` git da; regressiyada `exit 1`.

**T-69. Avtomatik testlar.** `node --test` bilan: `orthography`, `chunk`,
`retrieve`, `stream-polish`, `claude` (mock), `sse`, `extract`, `config`.

**T-70. CI.** `npm run check && npm test && npm run eval && npm run build`.

---

## 7. Chiqish mezonlari

### 7.1 Ichki sinov (yopiq guruh)

Barchasi bajarilishi shart:

- [ ] T-01 … T-05 (ishonchlilik) — qabul mezonlari boʻyicha oʻlchangan
- [ ] T-10 … T-18 (RAG) — `verify-audit` toza
- [ ] T-67, T-68 (baholash toʻplami va `npm run eval`) ishlaydi
- [ ] Haqiqiy qonun matnlari yuklangan, namuna fayl oʻchirilgan
- [ ] `VOYAGE_API_KEY` sozlangan, korpus qayta yuklangan
- [ ] T-41 … T-48 (xavfsizlik)
- [ ] T-55, T-56 (kuzatuv)

### 7.2 Ommaviy chiqish

Yuqoridagilarga qoʻshimcha:

- [ ] T-29 … T-33 (foydalanuvchi koʻradigan nuqsonlar)
- [ ] T-46, T-47 (rate limiting, API himoyasi)
- [ ] T-52 … T-54 (xarajat chegaralari)
- [ ] T-58 (zaxira nusxa, tiklash sinalgan)
- [ ] T-60, T-61 (deploy)
- [ ] **T-62 … T-66 (huquqiy) — yurist tasdigʻi bilan**
- [ ] T-21 (xavf bahosi yurist tomonidan tekshirilgan)

---

## 8. Bosqichlar

| Bosqich | Mazmun | Talablar |
|---|---|---|
| **1. Qidiruvni toʻgʻrilash** | Apostrof, morfologiya, translit, nisbiy chegara, chunk regexi | T-02, T-10…T-15 |
| **2. Oʻlchov** | Baholash toʻplami, `npm run eval`, baseline | T-67, T-68 |
| **3. Xavfsizlik** | Webhook, admin, fayl hajmi, CPU byudjeti, validatsiya | T-41…T-48 |
| **4. Foydalanuvchi tajribasi** | Markdown, Telegram formatlash, rasm/ovoz, mobil, fikr | T-29…T-33 |
| **5. Ishlab chiqarish** | Deploy, xarajat, kuzatuv, zaxira | T-49…T-61 |
| **6. Huquqiy** | Shartlar, rozilik, lokalizatsiya | T-62…T-66 |

**2-bosqich 1-bosqichdan keyin darhol bajarilishi shart:** aks holda keyingi har
bir oʻzgarish taxminga asoslanadi va yaxshilanish yoki yomonlashuvni oʻlchab
boʻlmaydi.

**6-bosqich eng erta boshlanadi:** u tashqi yurist ishtirokini talab qiladi va
eng uzun muddat oladi. Qolgan bosqichlarga parallel olib borilishi mumkin.

---

## 9. Ochiq savollar

Bular qaror qabul qilinishi kerak boʻlgan, hozircha javobsiz masalalar:

1. **Monetizatsiya.** Bepul, obuna yoki soʻrov boʻyicha toʻlov? Bu rate
   limiting va xarajat chegaralarining aniq qiymatlariga taʼsir qiladi.
2. **Korpus doirasi.** Qaysi kodekslar va qarorlar birinchi navbatda
   yuklanadi? Butun lex.uz — juda katta; boshlangʻich toʻplam aniqlanishi kerak.
3. **Korpusni yangilash tartibi.** Qonunga oʻzgartirish kiritilganda kim va
   qanday yangilaydi? Avtomatik yuklab olish qonuniymi?
4. **Maʼlumot lokalizatsiyasi** (T-66) — arxitekturaga taʼsir qilishi mumkin.
5. **Yurist ishtiroki.** T-21 va 5-boʻlim uchun yurist kerak. Kim, qanday
   shartlarda?
