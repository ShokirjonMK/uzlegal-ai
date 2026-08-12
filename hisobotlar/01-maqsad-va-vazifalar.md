# 1. Nima uchun bu tizim kerak

Oʻzbekistonda huquqiy maʼlumotga ehtiyoj katta, lekin unga kirish qiyin:

- qonunchilik **doimiy oʻzgaradi** — bitta kodeksda 89 tagacha tahrir boʻlishi mumkin;
- odam qaysi norma **hozir amalda** ekanini bilishi qiyin;
- yurist maslahati qimmat va hamma uchun ochiq emas;
- umumiy AI chatbotlar oʻzbek qonunchiligini bilmaydi va **moddalarni oʻylab topadi**.

Oxirgi nuqta eng xavflisi. Oddiy til modeli «Fuqarolik kodeksining
234-moddasiga koʻra…» deb ishonch bilan yozadi — va oʻsha modda umuman
boshqa narsa haqida boʻlishi yoki **mavjud boʻlmasligi** mumkin.
Foydalanuvchi buni sezmaydi.

**UzLegal-AI aynan shu muammoni hal qilish uchun qurilgan.**

---

# 2. Asosiy tamoyil: iqtibossiz javob yoʻq

Tizimning butun arxitekturasi bitta qoida atrofida qurilgan:

> **Har bir huquqiy daʼvo real hujjatga havola bilan qaytariladi.
> Havola bilan tasdiqlanmagan daʼvo javobdan avtomatik chiqariladi.**

Bu shior emas — bu kodda majburlangan mexanizm (`groundedness gate`).
Uch bosqichda ishlaydi:

| Bosqich | Nima tekshiriladi | Qaror |
|---|---|---|
| 1 | Daʼvoda iqtibos bormi | Yoʻq boʻlsa — **oʻchiriladi** |
| 2 | Iqtibos haqiqiy manbagami | Soxta boʻlsa — **oʻchiriladi** |
| 3 | Modda raqami iqtibosga mos keladimi | Mos kelmasa — **oʻchiriladi** |
| 4 | Manba matni daʼvoni qoʻllab-quvvatlaydimi | Shubhali boʻlsa — **«noaniq» deb belgilanadi** |

Toʻrtinchi bosqich oʻchirmaydi, **belgilaydi** — chunki u leksik va xato
qilishi mumkin. Toʻgʻri daʼvoni oʻchirish notoʻgʻrisini qoldirishdan
qimmatroq.

**Model bilmasa — «bilmayman» deydi.** Bu xato emas, toʻliq huquqli javob.

---

# 3. Beshta yuridik rol

Tizim bitta chatbot emas. U bitta masalani **turli nuqtai nazardan** hal
qiladi va soʻng ularni muvozanatga soladi:

| Rol | Nima qiladi | Foydalanuvchiga nima beradi |
|---|---|---|
| **Yurist** | Faktlarni ajratadi, tegishli normalarni topadi | Neytral huquqiy tahlil |
| **Advokat** | Mijoz foydasiga eng kuchli pozitsiya | Himoya argumentlari, protsessual imkoniyatlar |
| **Prokuror** | Qarama-qarshi pozitsiya | Zaif nuqtalar — sudda kutilayotgan hujum |
| **Professor** | Doktrina, kolliziyalar | Nazariy asos, ilmiy sharh |
| **Sudya** | Dalillarni tortadi | Asoslangan, muvozanatli xulosa |

Nima uchun bu **tasodifiy emas**: bu real sud jarayonining strukturasini
takrorlaydi. Bitta model bir tomonlama javob berishga moyil — advokat
ham, prokuror ham gapirsa, foydalanuvchi **ikkala tomonni** koʻradi.

---

# 4. Tizim nimalarni hal qiladi

## 4.1 Huquqiy savolga javob

Savol oddiy tilda beriladi, javob esa qonun moddasiga havola bilan
qaytadi.

> **Savol:** «Mehnat shartnomasida sinov muddati eng koʻpi bilan necha oy?»
>
> **Javob:** Mehnat kodeksining 130–131-moddasiga koʻra dastlabki sinov
> muddati uch oydan, rahbarlar uchun esa olti oydan oshmasligi kerak.
> `[C1] lex.uz/uz/docs/-6257288#-6260649`

## 4.2 Qonun bazasidan qidiruv

Modelsiz, tez va arzon. Gibrid qidiruv: **semantik** (maʼno boʻyicha) +
**leksik** (aniq soʻz) + **aniq moslik** (modda raqami boʻyicha).

Foydalanuvchi «ishdan boʻshatish» desa, matnda «mehnat shartnomasini
bekor qilish» yozilgan boʻlsa ham topiladi.

## 4.3 Hujjat tahlili

Shartnoma yoki boshqa hujjat yuklanadi — tizim xavflarni, bir tomonlama
shartlarni va qonunga zid bandlarni koʻrsatadi.

## 4.4 Hujjat tayyorlash

Mehnat shartnomasi, ijara shartnomasi, daʼvo arizasi, ishonchnoma,
pretenziya va boshqalar — toʻldirish joylari bilan `.docx` faylida.

## 4.5 Sud qarori tahlili

Qaror matni tahlil qilinadi: protsessual buzilishlar, asoslanish
sifati, nomutanosiblik belgilari.

## 4.6 Sud jarayoniga tayyorgarlik

Advokat, prokuror yoki sudya nuqtai nazaridan strategiya; qarshi tomon
beradigan savollar roʻyxati.

## 4.7 Taʼlim

Oʻquv dasturi, leksiya materiali va testlar — yuridik fakultet
talabalari va malaka oshirish uchun.

---

# 5. Qanday ishlatiladi

Tizim **bitta yadro** ustiga qurilgan va oltita usulda ishlatiladi:

| Usul | Kim uchun |
|---|---|
| **Telegram bot** | Oddiy foydalanuvchi — eng qulay yoʻl |
| **Web ilova** | Oddiy foydalanuvchi va yurist |
| **Terminal (CLI)** | Yurist, dasturchi |
| **REST API** | Boshqa tizimlarga ulash |
| **SDK** (Python/TS) | Dasturchi |
| **MCP server** | Claude Code, IDE va boshqa AI vositalari |

Muhim: **hammasi bir xil yadroni chaqiradi.** Bu shuni anglatadiki, web
va Telegram bir savolga **bir xil javob** beradi — ikkita mustaqil
dvigatel muqarrar ravishda ajralib ketardi.

---

# 6. Nima qilmaydi — ochiq aytiladi

| Nima | Nega |
|---|---|
| Yuridik maslahat **bermaydi** | Bu tadqiqot vositasi. Har qanday xulosa malakali yurist tomonidan tasdiqlanishi shart |
| Sudda vakillik qilmaydi | Bu odamning ishi |
| Kafolat bermaydi | Javob toʻgʻriligi manbadan tekshirilishi kerak |
| Bilmagan narsasini oʻylab topmaydi | Bazada yoʻq boʻlsa — ochiq aytadi |

Bu ogohlantirish **har bir javobda** koʻrsatiladi va uni oʻchirib
boʻlmaydi: `ConsultResult` obyekti disclaimersiz umuman qurilmaydi.

---

# 7. Texnik maqsadlar va oʻlchanadigan mezonlar

| Mezon | Maqsad | Nima uchun shu raqam |
|---|---|---|
| Recall@10 | ≥ 90% | Toʻgʻri norma kontekstga tushmasa, gate uni tasdiqlay olmaydi — bu butun zanjirning shifti |
| Deprecated leak | **0%** | Bekor qilingan normaga havola — eng xavfli xato turi |
| Hallucination | ≤ 1% | Gate ning asosiy vazifasi |
| Kechikish (p95) | ≤ 45 s | Foydalanuvchi kutishga tayyor boʻlgan chegara |
| Rad etish darajasi | oʻlchanadi | «Bilmayman» — muvaffaqiyat, nosozlik emas |

---

# 8. Kimlar uchun

| Auditoriya | Qanday foyda |
|---|---|
| **Fuqarolar** | Huquqini bilish; yuristga borishdan oldin masalani tushunish |
| **Yuristlar va advokatlar** | Tadqiqot vaqtini qisqartirish; qarshi pozitsiyani oldindan koʻrish |
| **Tadbirkorlar** | Shartnoma xavflarini tekshirish; hujjat tayyorlash |
| **Talabalar** | Oʻqish materiali, testlar, amaliy misollar |
| **Davlat organlari** | Ichki huquqiy tahlil; **air-gapped** rejimda maxfiy maʼlumot bilan |
| **IT kompaniyalar** | API orqali oʻz mahsulotiga huquqiy modul qoʻshish |

---

# 9. Nima uchun mahalliy model

Tizim **oʻz serveringizda** ishlashi mumkin — bu tasodifiy tanlov emas:

| Sabab | Izoh |
|---|---|
| **Maxfiylik** | Mijoz shartnomasi uchinchi tomon serveriga chiqmaydi |
| **Qonuniy talab** | «Shaxsga doir maʼlumotlar toʻgʻrisida»gi qonun lokalizatsiyani talab qiladi |
| **Xarajat** | Bulut API da bitta savol ≈ $0.22; oʻz modelida — faqat elektr |
| **Mustaqillik** | Tashqi xizmat narxi yoki siyosati oʻzgarsa tizim toʻxtamaydi |
| **Air-gapped** | Internetsiz, izolyatsiya qilingan tarmoqda ishlaydi |
