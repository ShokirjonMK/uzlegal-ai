# 22 — Sprint 2: korpus chuqurligi, havola nazorati va Nazorat moduli

**Sana:** 2026-08-14
**Manba:** bosh reja — himoya devori tahlili. Xulosa aynan shunday edi:
uzoq turadigan ustunliklar *korpus versiyalash* va *o'lchov*, tez
yemiriladiganlari esa AI imkoniyatlari. Sprint shu xulosaga bo'ysunadi.

| Ish | Nega | Devor muddati |
|---|---|---|
| **S1** Korpus sana qamrovi | W1 vaqt mashinasini haqiqatan ishlaydigan qiladi | 24+ oy |
| **S2** Havola nazorati | Iqtibos grafi — raqiblarda yo'q | 24+ oy |
| **S3** Nazorat moduli CLI | Qurish emas, qadoqlash — B2G kirish nuqtasi | — |

---

## 1. S1 — korpus sana qamrovi

### 1.1 Ildiz sabab aniqlandi

Muammo: 48 527 bo'lakning 36 160 tasida (74.5%) `valid_from` yo'q.
Sabab **ikkita mustaqil nuqsonda**, ikkalasi ham aniq:

**Nuqson 1 — sana parserdan chiqib ketadi.**
`ingest/parsers/lex_uz.py:390` `_document_title()` sahifadagi
`ACT_TITLE` blokini afzal ko'radi va faqat u bo'lmasa `<title>`
tegiga tushadi. `ACT_TITLE` da sana **hech qachon yo'q**, `<title>`
tegida esa **doim bor**:

```
<title> O‘RQ-982-сон 25.10.2024. Oʻzbekiston Respublikasi
        Vazirlar Mahkamasi toʻgʻrisida</title>
```

O'lchandi: **863/863 xom faylda (100%)** `<title>` dan sana ajratiladi.
`normalize.py:347` `extract_date()` bu formatni allaqachon tushunadi —
**yangi sana parseri yozish kerak emas**.

**Nuqson 2 — hujjat sanasi bo'lakka o'tmaydi.**
`index/chunker.py:340-356` `_base()` `valid_from` ni **faqat**
`article.valid_from` dan oladi, u esa versiyalash tomonidan
o'zgartirish izohlaridan to'ldiriladi. Izohsiz hujjatda sana umuman
bo'lmaydi. `doc.adopted_at` ga **fallback yo'q**.

### 1.2 Talab

| # | Nima |
|---|---|
| **S1-A** | `_document_title()` sanani `<title>` tegidan ajratsin va `adopted_at` ga yozsin |
| **S1-B** | `doc.title` ga raqam va sana prefiksi **tushmasin** (§1.3 sabab) |
| **S1-C** | `chunker._base()` da fallback: `valid_from = article.valid_from or doc.adopted_at` |
| **S1-D** | Kelajakdagi sana `valid_from` ga **yozilmasin** (§1.4) |
| **S1-E** | Mavjud indeksni qayta embeddingsiz to'ldiruvchi buyruq |
| **S1-F** | Qamrov oldin/keyin o'lchansin va hujjatlashtirilsin |

### 1.3 S1-B nima uchun majburiy — yashirin bog'liqlik

`ingest/linking.py:208` `_code_registry()` **hujjat sarlavhasi
bo'yicha** kodeks nomlarini indekslaydi va tashqi havolalarni shunga
qarab hal qiladi. Agar `doc.title` ga `«O‘RQ-982-сон 25.10.2024. »`
prefiksi qo'shilsa, `linking.py:191` dagi `_TITLE_NOISE` tozalash
buziladi va **`refs.jsonl` tarkibi siljiydi**.

Ya'ni sarlavha o'zgarishi S2 ning ma'lumot bazasini o'zgartiradi.
Shuning uchun: sana **faqat `adopted_at` ga**, sarlavha toza qolsin.

### 1.4 S1-D nima uchun majburiy — jimgina yo'qotish

`retrieval/hybrid.py:172` `version_filter` da:
`valid_from > bugun` → bo'lak **chiqarib tashlanadi**.

Korpusda kelajak sanali hujjatlar bor (masalan `2026-08-01`,
`2026-04-21`). Agar `valid_from = adopted_at` ko'r-ko'rona yozilsa,
bunday hujjatlar **barcha so'rovlardan yo'qoladi**.

`versioning.py:376` `_apply_edition` bu tuzoqni allaqachon biladi va
kelajak sanani `pending_from` ga yozadi. Backfill **xuddi shu
semantikaga** amal qilsin.

### 1.5 S1-E — qayta embedding shart emas, lekin ehtiyot bilan

`index/store.py` da hamma narsa `chunk_id` bo'yicha kalitlangan:
`chunks.jsonl` — haqiqat manbai, LanceDB qatorlari faqat
`chunk_id` + vektor uchun ishlatiladi, BM25 esa matndan quriladi.
Demak `valid_from` ni `chunks.jsonl` da yangilash **xavfsiz** —
`chunk_id`, `heading`, `content` tegilmasa.

**Ammo:** `chunker.py:517-523` `_merge_tiny()` bo'laklarni
`(valid_from, valid_to, status)` bo'yicha guruhlaydi. Ya'ni sanalar
o'zgargach, **to'liq `index build` boshqa `chunk_id` lar hosil
qiladi** va metama'lumot patchi bilan bir xil natijaga kelmaydi.

Qaror: sprint **ikkalasini ham** yetkazadi — parser/chunker tuzatishi
(haqiqat manbai) va patch buyrug'i (darhol foyda). Patch chiqishida
ochiq yozilsin: keyingi to'liq `index build` uni bekor qiladi.

Buyruq: `uzlegal pipeline dates` (`cli/pipeline.py` ga qo'shilsin —
u arxiv ustida ishlaydigan, tarmoqsiz buyruqlar uyi).

```
uzlegal pipeline dates            # faqat o'lchov, hech narsa yozmaydi
uzlegal pipeline dates --apply    # chunks.jsonl ni yangilaydi
```

### 1.6 Aniqlik qamrovdan muhimroq

Noto'g'ri `valid_from` vaqt mashinasini **jimgina** buzadi: javob
ishonchli ko'rinadi, lekin noto'g'ri sanadagi tahrirni keltiradi.

Shuning uchun qamrovni oshirish **yetarli emas** — aniqlik
o'lchanishi shart. Qabul mezoni §5 da: 20 hujjatlik namuna xom
`<title>` ga qarab qo'lda tekshiriladi.

---

## 2. S2 — havola nazorati

### 2.1 Doira ataylab toraytirildi — sabab

Dastlabki g'oya «kolliziya detektori: zid normalarni topish» edi.
**Bu iqtibos grafi bilan bajarilmaydi.** Graf faqat «A hujjat B ga
havola qiladi» deydi; u «A B ga **zid**» degan ma'noni bermaydi.
Ziddiyatni aniqlash semantik tahlil, graf yurish emas.

`prompts/roles/professor.uz.md:62` buni allaqachon to'g'ri qo'ygan:

> Kolliziya "topish" uchun uni o'ylab topmaysan.

Determinstik yo'l bilan **haqiqatan** aniqlanadigan narsa — havola
yaxlitligining buzilishi. Bu kamtarona ko'rinadi, lekin amalda
qimmatroq: bu qonun matnidagi **haqiqiy nuqson** va uni
qonunchilikni takomillashtirish organi tuzatishi mumkin.

### 2.2 Aniqlanadigan uch sinf

| Sinf | Ta'rif | Nega muhim |
|---|---|---|
| **Uzilgan havola** | `to_doc`/`to_article` mavjud, lekin korpusda bunday modda **yo'q** | Qonun matni mavjud bo'lmagan moddaga yo'llaydi |
| **Bekor qilinganga havola** | Nishon modda `status != in_force` | Amaldagi norma bekor qilinganga tayanadi |
| **Hal qilinmagan havola** | `kind = "unresolved"` — 29 365 dan **5 710 tasi (19.4%)** | Havola matni tanildi, nishon topilmadi |

Ziddiyat aniqlash **chiqarilmaydi**. Chiqadigan narsa —
*nomzodlar ro'yxati*, uni professor agenti yoki yurist baholaydi.

### 2.3 Joylashuv

Yangi modul: **`src/uzlegal/index/collisions.py`**.

`pyproject.toml` `[tool.importlinter]` qatlam shartnomasi bo'yicha
`index` `ingest` dan yuqorida va undan yuqoridagilar hammasi uni
import qila oladi. Shartnomaga o'zgartirish **kerak emas**.

### 2.4 Buyruq

```
uzlegal index refcheck             # hisobot
uzlegal index refcheck --json      # mashina uchun
uzlegal index refcheck --kind uzilgan
```

### 2.5 S1 dan keyin bajarilsin

S1 `doc.title` ga tegsa `_code_registry()` o'zgaradi va `refs.jsonl`
qayta quriladi. Shuning uchun **S1 avval, keyin `refs.jsonl` qayta
hosil qilinadi, keyin S2 o'lchanadi**.

S1-B aynan shu siljishni oldini olish uchun qo'yilgan — lekin
tekshirilsin: S1 dan keyin `kind` taqsimoti o'zgardimi?

Boshlang'ich holat (S1 dan oldin o'lchangan):
`internal` 19 100 · `external` 4 555 · `unresolved` 5 710 · jami 29 365.

---

## 3. S3 — Nazorat moduli CLI

### 3.1 Mavjud holat — kutilganidan ko'proq tayyor

| Yuza | Holat |
|---|---|
| `POST /v1/integrity/check` | ✅ mavjud (`api/app.py:537`) |
| `POST /v1/integrity/profile` | ✅ mavjud (`api/app.py:555`) |
| Autentifikatsiya va reja chegarasi | ✅ ulangan |
| `detect_from_text(text)` | ✅ mavjud (`integrity/detector.py:427`) |
| **CLI** | ❌ **umuman yo'q** |

Ya'ni «qadoqlash» amalda bitta narsani anglatadi: **CLI yuzasi va
o'qiladigan hisobot**. Model chaqirilmaydi — chiqish to'liq
deterministik va shuning uchun testlanadigan.

### 3.2 Talab

```
uzlegal nazorat check <fayl>            # bitta qaror
uzlegal nazorat check <fayl> --json
uzlegal nazorat profile <katalog>       # bir sudya bo'yicha to'plam
uzlegal nazorat profile <katalog> --judge "A. Karimov"
```

Fayl o'qish namunasi `cli/pipeline.py:164` `redact()` da bor —
mavjudlik tekshiruvi, `typer.Exit(4)`, `--out`. Shu shakl
takrorlansin.

### 3.3 Hisobot ko'rinishi

O'zbek tilida, terminalda o'qiladigan: xavf darajasi va yorlig'i,
belgilar toifa bo'yicha guruhlangan, har biri uchun dalil satri.
Oxirida `JudgeProfile.disclaimer` **majburiy** chiqsin — bu yuridik
javobgarlik matni va uni o'chirib bo'lmaydi.

---

## 4. Chegaralar — bu sprintga kirmaydi

- To'liq `index build` yugurtirish — bu ops qarori, ~48k bo'lak qayta embedding
- Semantik ziddiyat aniqlash — §2.1 sabab
- To'lov shlyuzi — alohida sprint, haqiqiy merchant hisobi kerak
- Kechikish optimizatsiyasi — apparat masalasi
- `tests/e2e/` tiklash
- `test_api_auth.py` sekinligi (fixture `TestClient` ni 21 marta quradi)

---

## 5. Qabul mezonlari

### S1

- [x] **A1** `_document_title()` sanani `<title>` dan ajratadi; `kb parse` da `qabul` sanasi ko'rinadi
- [x] **A2** `doc.title` da raqam/sana prefiksi **yo'q** — test buni tekshiradi
- [x] **A3** `chunker._base()` `doc.adopted_at` ga fallback qiladi
- [x] **A4** Kelajak sanali hujjat `valid_from` olmaydi — test bilan qoplangan
- [x] **A5** `uzlegal pipeline dates` o'lchov beradi, `--apply` yozadi
- [x] **A6** `--apply` `chunk_id`, `heading`, `content` ni **o'zgartirmaydi**
- [x] **A7** Qamrov oldin/keyin o'lchandi va raqamlar hujjatga yozildi
- [x] **A8** **Aniqlik:** 20 hujjatlik namuna xom `<title>` bilan solishtirildi; noto'g'ri sana **0** bo'lsin

### S2

- [x] **B1** `index/collisions.py` uch sinfni aniqlaydi (§2.2)
- [x] **B2** `uzlegal index refcheck` ishlaydi; `--json` va `--kind` filtri bor
- [x] **B3** Hisobot **ziddiyat** deb da'vo qilmaydi — «nomzod» tili ishlatiladi
- [x] **B4** S1 dan keyin `kind` taqsimoti o'zgarganmi — o'lchandi va yozildi
- [x] **B5** Bo'sh yoki buzuq `refs.jsonl` da yiqilmaydi

### S3

- [x] **C1** `uzlegal nazorat check <fayl>` ishlaydi
- [x] **C2** `uzlegal nazorat profile <katalog>` ishlaydi
- [x] **C3** `--json` chiqishi `model_dump()` ga mos
- [x] **C4** Fayl topilmasa `typer.Exit(4)`, xato matni o'zbekcha
- [x] **C5** Disclaimer **har doim** chiqadi
- [x] **C6** Model chaqirilmaydi — test buni tasdiqlaydi

### Umumiy

- [x] **D1** `ruff check` va `ruff format --check` toza
- [x] **D2** `mypy --strict src/uzlegal` — 0 xato
- [x] **D3** `lint-imports` — 0 buzilish
- [x] **D4** `pytest tests/unit tests/integration` — **1 061 test yashil** (`test_api_auth.py` siz), to'liq yugurishda **1 082**; S3 41 test qo'shdi
- [x] **D5** Yangi testlar nomi o'zbekcha
- [x] **D6** Hech bir mavjud test o'chirilmagan

---

## 6. Eng katta risk

S1 `chunks.jsonl` ga tegadi — bu **butun qidiruvning ma'lumot
bazasi**. Noto'g'ri backfill 48 527 bo'lakning sanasini buzadi va
buni sezish qiyin, chunki qidiruv baribir natija qaytaraveradi.

Shuning uchun:

1. `--apply` dan oldin **majburiy** quruq yugurish (`--apply` siz)
2. `--apply` eski faylning zaxira nusxasini olsin
3. A8 (aniqlik namunasi) A7 (qamrov) dan **muhimroq** — QA shuni
   birinchi tekshirsin

Tezlik uchun iteratsiyada: `--ignore=tests/unit/test_api_auth.py`
(u ~10 daqiqa oladi). Yakuniy yugurish to'liq bo'lsin.

---

## 7. S1 — bajarilgan ish va o'lchov

O'lchov sanasi: **2026-08-14**, korpus `kb/current` — 48 527 bo'lak,
792 hujjat (indeksda faqat o'zbekcha nashrlar), arxivda 863 xom fayl.

### 7.1 O'zgargan joylar

| Fayl | Nima |
|---|---|
| `ingest/parsers/lex_uz.py` | `title_tag_parts()` va `title_tag_date()`; `_document_title()` endi `(sarlavha, sana)` juftligini qaytaradi |
| `index/chunker.py` | `_document_valid_from()` — modda sanasi bo'lmasa `doc.adopted_at`, kelajak sana rad etiladi |
| `cli/pipeline.py` | `uzlegal pipeline dates` (+ `--apply`, `--index`, `--as-of`) |
| `scripts/check-date-accuracy.py` | A8 aniqlik namunasi |
| `scripts/check-dates-apply.py` | A6 tekshiruvi (zaxira ↔ yangi fayl) |

### 7.2 Sana `<title>` ning **prefiksidan** olinadi, butun tegdan emas

`<title>` ikki qismdan iborat va ular uzilmas bo'sh joy (`&nbsp;`) bilan
ajratilgan: metama'lumot prefiksi (`OʻRQ-982-сон 25.10.2024.`) va hujjat
nomi. Sana faqat **prefiksdan** o'qiladi.

Sabab o'lchandi: butun tegga `extract_date()` qo'llansa, 863 fayldan
**15 tasida** noto'g'ri sana chiqadi — nom ichidagi «2020-yil
22-iyundagi» kabi boshqa hujjatga tegishli havola ustun keladi
(`extract_date()` avval so'zli shaklni qidiradi). Masalan:

| Hujjat | Butun tegdan | To'g'ri (prefiksdan) |
|---|---|---|
| `-8055472` | 2020-06-22 | 2026-02-17 |
| `-7206686` | 1970-06-24 | 2024-11-07 |
| `-8376893` | 2020-08-24 | 2026-08-04 |

Sarlavhaning o'zi (`doc.title`) `ACT_TITLE` blokidan olinadi va **toza**
qoladi — S1-B talabi (§ 1.3). `ACT_TITLE` bo'lmagan 2 hujjatda `<title>`
ning faqat **nom** qismi olinadi, prefiks tashlanadi.

### 7.3 Qamrov — A7

| O'lchov | Oldin | Keyin |
|---|---|---|
| `valid_from` bor **bo'lak** | 12 367 / 48 527 (**25.5%**) | 48 527 / 48 527 (**100.0%**) |
| kamida bitta sanali bo'lagi bor **hujjat** | 214 / 792 (**27.0%**) | 792 / 792 (**100.0%**) |
| **to'liq** sanali hujjat (barcha bo'lagi) | 0 / 792 (**0.0%**) | 792 / 792 (**100.0%**) |

`--apply` to'ldirdi: **36 160** bo'lak. Kelajak sana tufayli o'tkazib
yuborildi: **0**. Arxivda sanasi topilmagan hujjat: **0**.
Zaxira: `kb/current/chunks.jsonl.20260814.bak`.

`--apply` ta'siri butun fayl bo'yicha tekshirildi
(`scripts/check-dates-apply.py`): 48 527 bo'lakdan `chunk_id`, `heading`,
`content`, `doc_id`, `status`, `valid_to` maydonlarida farq **0**,
mavjud sana ustidan yozilgan holat **0** — A6 bajarildi.

### 7.4 Kelajak sana qopqoni — A4

Bugungi sanada (2026-08-14) korpusdagi eng kech qabul sanasi
2026-08-07, ya'ni kelajak sanali hujjat qolmagan va o'tkazib yuborilgan
bo'lak **0**. Qopqonning haqiqatan ishlashini ko'rsatish uchun o'lchov
o'tmishdagi sana bilan qaytarildi:

```
uzlegal pipeline dates --as-of 2026-01-01
→ To'ldiriladi 24 186 · kelajak sana tufayli o'tkazildi 11 974
```

Ya'ni ko'r-ko'rona `valid_from = adopted_at` yozilganda o'sha kuni
**11 974 bo'lak** `version_filter` tomonidan barcha so'rovlardan
chiqarib tashlangan bo'lardi (§ 1.4). Indeksdagi eng kech `valid_from`
tekshirildi: 2026-08-08 ≤ bugun.

### 7.5 Aniqlik — A8

`scripts/check-date-accuracy.py` parser ajratgan `adopted_at` ni xom
HTML `<title>` tegidagi sana bilan solishtiradi. Etalon **mustaqil**
regex bilan o'qiladi (tegdagi birinchi `KK.OO.YYYY`), ya'ni skript
parser mantiqini takrorlamaydi.

| Namuna | Tekshirildi | Noto'g'ri sana | Sanasiz | Sarlavhada prefiks |
|---|---|---|---|---|
| 20 tasodifiy hujjat (`--sample 20 --seed 22`) | 20 | **0** | 0 | 0 |
| Butun arxiv (`--all`) | 863 | **0** | 0 | 0 |

Talab qilingan mezon — noto'g'ri sana 0 — bajarildi; qo'shimcha ravishda
u butun arxivda ham tasdiqlandi.

### 7.6 Eslatma S2 uchun

`doc.title` 863 hujjatning 861 tasida o'zgarmadi. `ACT_TITLE` bloki
bo'lmagan 2 hujjatda (`-6708359`, `-6708366` — iqtisodiy ish qarorlari)
sarlavhadan raqam/sana prefiksi olib tashlandi. Ikkalasi ham kodeks
emas, shuning uchun `_code_registry()` ga kirmaydi — lekin B4 o'lchovida
`refs.jsonl` qaytadan hosil qilinganda shu ikki hujjat nazarda tutilsin.

---

## 8. S2 — bajarilgan ish va o'lchov

O'lchov sanasi: **2026-08-14**, korpus `kb/current` — 48 527 bo'lak,
792 hujjat. `refs.jsonl` S1 dan **keyin** qayta hosil qilindi (§ 2.5).

### 8.1 O'zgargan joylar

| Fayl | Nima |
|---|---|
| `index/collisions.py` | Yangi modul: uch sinf, `TargetLookup` keshi, `RefCheckReport` |
| `index/store.py` | `article_labels()` — birlashgan bo'lak yorliqlari (§ 8.4) |
| `cli/main.py` | `uzlegal index refcheck` (+ `--json`, `--kind`, `--limit`, `--rebuild`) |
| `tests/unit/test_refcheck.py` | 32 test — B1..B5 |

### 8.2 B4 — S1 refs.jsonl ni o'zgartirdimi

Boshlang'ich holat (§ 2.5) **20 hujjatdan** o'lchangan edi: eski
`refs.jsonl` da atigi 20 xil `from_doc` bor. Shuning uchun to'g'ridan-
to'g'ri taqqoslash S1 ni emas, korpus o'sishini o'lchagan bo'lardi.

Nazorat tajribasi o'tkazildi: **ayni o'sha 20 hujjat**, S1 dan keyingi
parser bilan qayta ajratildi.

| Tur | Oldin (S1 gacha) | Keyin (ayni 20 hujjat) |
|---|---|---|
| `internal` | 19 100 | **19 100** |
| `external` | 4 555 | **4 555** |
| `unresolved` | 5 710 | **5 710** |
| jami | 29 365 | **29 365** |

Fayl `cmp` bilan solishtirildi — **bayt-bayt bir xil**. Ya'ni S1 havola
grafini **umuman o'zgartirmadi**; S1-B (§ 1.3) o'z vazifasini bajardi.

Butun korpus uchun qayta qurilgan yangi asos (761 hujjatda havola bor):

| Tur | Miqdor | Ulush |
|---|---|---|
| `internal` | 26 321 | 55.5% |
| `external` | 6 871 | 14.5% |
| `unresolved` | 14 196 | 30.0% |
| **jami** | **47 388** | |

O'sish sababi — hujjatlar soni (20 → 761), parser emas. Buni ham
tekshirish mumkin: to'liq qayta qurilishda o'sha 20 hujjatning
`external` i 4 555 → 4 615 (+60), `unresolved` i 5 710 → 5 650 (−60)
bo'ldi. Sabab aniq: `_code_registry()` endi 20 emas, 792 hujjat
sarlavhasini ko'radi va 60 ta tashqi havola nishonini topdi.

Eski fayl saqlandi: `kb/current/refs.jsonl.20260814.bak`.

### 8.3 Nomzodlar — uch sinf

`uzlegal index refcheck`, 23.5 s (47 388 havola, 8 962 xil nishon):

| Sinf | Nomzod | Ulush |
|---|---|---|
| `uzilgan` | 2 543 | 5.4% |
| `bekor` | 4 | 0.008% |
| `hal-qilinmagan` | 14 196 | 30.0% |
| **jami** | **16 743** | **35.3%** |

`bekor` sinfi kichik va aynan shuning uchun qimmatli — ular qo'lda
ko'riladigan darajada kam:

```
-2851499:33  → -2851499:32   [repealed]
-2851499:168 → -2851499:16   [repealed]
-2851499:168 → -2851499:33   [repealed]
-97664:245   → -97664:241-9  [repealed]
```

`uzilgan` tarkibi (2 543): nishon hujjati korpusda umuman yo'q — **992**;
nishon raqami tireli (`993-995`, `241-9`) — **254**; qolgani — modda
raqami hujjatda topilmadi. Manba bo'yicha: ichki 1 360 · tashqi 1 183.

### 8.4 Nima uchun `article_labels()` qo'shildi

Birinchi o'lchovda `uzilgan` **3 425** chiqdi. Tekshirilganda ularning
**882 tasi (25.8%) o'z chunkerimiz artefakti** bo'lib chiqdi:
`chunker._merge_tiny()` kichik moddalarni birlashtiradi va bo'lakka
«18-19» yorlig'ini beradi, `chunks_for_article()` esa aniq tenglik
bo'yicha izlaydi. Ya'ni 19-modda korpusda **bor**, lekin topilmasdi.

`TargetLookup` endi aniq nom topilmaganda oraliq yorliqlarini ham
ko'radi va bo'lakning holatini o'sha yerdan oladi. Natija: 3 425 → 2 543.

Nishon raqamining o'zi tireli bo'lsa (254 holat) kengaytirilmaydi:
o'zbek qonunchiligida `241⁹` kabi modda raqami haqiqiy va uni
`241-9` shaklida oraliqdan ajratib bo'lmaydi. Bu — `ingest/linking.py`
dagi run kengaytirishning shovqini va u alohida ish.

### 8.5 B3 — hisobot nima demaydi

Modul lug'atida ham, CLI chiqishida ham «ziddiyat» yoki «kolliziya»
so'zi yo'q; buni test ushlab turadi
(`test_refcheck_hisoboti_ziddiyat_deb_da_vo_qilmaydi`). Hisobot
oxirida doimiy izoh chiqadi:

> Bu ro'yxat — nomzodlar, ziddiyat xulosasi emas. Har biri yurist yoki
> professor agenti tomonidan baholanishi kerak.

§ 8.4 buning nega shunday ekanini ko'rsatadi: birinchi o'lchovdagi
«uzilgan havola» larning chorak qismi qonun matnining nuqsoni emas,
bizning indekslash usulimizning izi edi.

### 8.6 B5 — buzuq refs.jsonl

`KnowledgeIndex.reference_graph()` xatoda `None` qaytaradi, `refcheck`
esa bo'sh hisobot va sabab izohini chiqarib **0 kod bilan** tugaydi —
graf ixtiyoriy qatlam, usiz qidiruv to'liq ishlaydi. Uch holat test
bilan qoplangan: bo'sh fayl (nol havolali graf), yarim yozilgan JSONL
va maydonlari yetishmagan yozuv.

---

## 9. S3 — bajarilgan ish

Qurish emas, qadoqlash: `integrity/` moduli va uning API yuzasi
o'zgarmadi — `detect_from_text()`, `build_profile()` va
`POST /v1/integrity/*` bir baytga ham tegilmadi.

### 9.1 O'zgargan joylar

| Fayl | Nima |
|---|---|
| `cli/nazorat.py` | Yangi sub-app: `check` va `profile`, o'zbekcha hisobot, `--json`, `--out` |
| `cli/main.py` | `nazorat` sub-app ro'yxatga qo'shildi |
| `tests/unit/test_nazorat_cli.py` | 41 test — C1..C6 |

```
uzlegal nazorat check <fayl> [--json] [--out FAYL]
uzlegal nazorat profile <katalog> [--judge NOM] [--pattern NAQSH]
                                  [--limit N] [--json] [--out FAYL]
```

### 9.2 Disclaimer bitta manbadan keladi — C5

`IntegrityProfile` da `disclaimer` maydoni yo'q, `JudgeProfile` da bor.
CLI matnni ko'chirib yozmaydi (ikki nusxa vaqt o'tib uzoqlashadi), balki
`JudgeProfile` dan o'qiydi va `check --json` chiqishiga ham qo'shadi.
Ya'ni yuridik izoh to'rt yo'lda ham chiqadi: matnli hisobot, `--json`
(`model_dump()` ichida), `--out` fayli va `--out` bilan ekran. Oxirgisi
ataylab: `--out` izohni chetlab o'tishning yo'li bo'lmasin.

### 9.3 Nima uchun hisobot bezaksiz chiqadi

Dalil satrlari qaror matnidan olinadi va ularda `[` bo'lishi mumkin —
rich uni uslub tegi deb o'qib yuboradi (`index refcheck` da ham shu
muammo bor edi). Shuning uchun hisobot `markup=False` bilan chiqadi.
`soft_wrap=True` esa satr terminal kengligiga qarab sinmasligini
ta'minlaydi: ekrandagi hisobot `--out` fayli bilan bayt-bayt bir xil
bo'lsin.

### 9.4 `--judge` filtrlaydi, faqat yorliq emas

Katalogda bir necha sudyaning qarori bo'lishi mumkin. `--judge` bilan
faqat o'sha sudyaning qarorlari olinadi (nom `fold()` orqali
solishtiriladi). `--judge` berilmasa va katalogda bir nechta sudya
topilsa, hisobot buni ochiq aytadi — aks holda statistika bir necha
odamning qarorlarini bitta odamniki kabi ko'rsatadi.

### 9.5 C6 — model chaqirilmasligi test bilan qo'riqlanadi

`test_check_model_chaqirmaydi` va `test_profile_model_chaqirmaydi`
`inference.backend.create_backend` va `load_builtin_backends` ni
yiqiladigan funksiyaga almashtiradi: agar biror joy model yuklashga
urinsa, test qizil bo'ladi. Bunga qo'shimcha
`test_check_chiqishi_deterministik` bir buyruqni ikki marta yugurtirib
chiqishni bayt-bayt solishtiradi.

---

## 8. PM ning mustaqil tekshiruvi

Quyidagi raqamlar agent hisobotidan emas — PM tomonidan qayta
yugurtirilgan buyruqlardan.

| Tekshiruv | Natija |
|---|---|
| `pytest` (tez, `test_api_auth` siz) | **1 061 o'tdi**, 0 yiqildi |
| `ruff check` / `format --check` | Toza · 131 fayl |
| `mypy --strict src/uzlegal` | **0 xato**, 91 fayl |
| `lint-imports` | 1 shartnoma saqlandi, 0 buzildi |
| Sana aniqligi (mustaqil usul) | 53 hujjat tekshirildi · **0 nomuvofiqlik** |
| `chunks.jsonl` yaxlitligi | `chunk_id` to'plami **o'zgarmagan**; `heading`/`content`/`doc_id`/`status`/`valid_to` farqi **0** |
| Sana qamrovi | 792/792 hujjat (**100%**) |
| Yangi buyruqlar | `uzlegal nazorat` va `uzlegal index refcheck` ro'yxatdan o'tgan va ishlaydi |

---

## 9. ⚠️ Tekshiruvda topilgan ALOHIDA nuqson — bu sprintga aloqasiz

PM tekshiruvi paytida **oldindan mavjud bo'lgan** jiddiy nuqson
aniqlandi. U bu sprint tomonidan keltirib chiqarilmagan: zaxira
nusxada (`chunks.jsonl.20260814.bak`, sprintdan oldingi holat)
ko'rsatkichlar **aynan bir xil**.

### Nima topildi

| Ko'rsatkich | Qiymat |
|---|---|
| `chunks.jsonl` satrlari | 48 527 |
| **Noyob `chunk_id`** | **35 708** |
| Takrorlangan `chunk_id` | 4 484 ta identifikator |
| **Yo'qoladigan satr** | **12 819 (26.4%)** |

### Nima uchun bu muhim

`index/store.py:277-279`:

```python
self._chunks = {}
for line in self.chunks_path.read_text(...).splitlines():
    chunk = Chunk(**json.loads(line))
    self._chunks[chunk.chunk_id] = chunk      # ← oxirgisi g'olib
```

Bo'laklar `chunk_id` bo'yicha lug'atga yig'iladi. Takrorlangan
identifikator ustiga yoziladi, ya'ni **korpusning 26.4% i yuklashda
jimgina tashlab yuboriladi**.

Amalda: indeks **48 527 emas, 35 708 bo'lakdan** iborat. Barcha
hisobotlardagi «48 527 bo'lak» raqami — shu jumladan oldingi
hujjatlarimizdagi — indeksni **26% ga oshirib ko'rsatadi**.

Takror namunalari: `-111453:3` (×2), `-111453:50:0:a` (×3),
`-111453:50:0:b` (×3) — ya'ni `chunker` bir xil `(doc, modda, band)`
uchun bir nechta bo'lak yasaganda identifikator to'qnashadi.

### Bu loyihaning o'z naqshi

Bu aynan `docs/16` va `hisobotlar/04` da hujjatlashtirilgan nosozlik
turi: **e'lon qilingan raqam amaldagi raqam emas**. Vosita
muvaffaqiyat haqida xabar beradi, lekin ishning bir qismi
bajarilmaydi.

### Tavsiya — alohida sprint

1. `chunker` da `chunk_id` hosil qilishga tartib raqami qo'shilsin
   (`-111453:50:0:a#2` kabi) yoki mavjud sxema takrorlanmasligi
   kafolatlansin
2. `index build` chiqishida **noyob** bo'lak soni ko'rsatilsin
3. `store.load()` takrorni sezsa **ogohlantirsin**, jimgina
   yutmasin
4. Barcha hisobotlardagi korpus raqamlari qayta hisoblansin

Bu sprintga **kiritilmadi**: u `chunk_id` sxemasini o'zgartiradi,
ya'ni to'liq qayta indekslashni talab qiladi va alohida rejalashtirilishi
kerak.

> ✅ **Hal qilindi (2026-08-18)** — `docs/23`. Tekshiruvda nuqsonning
> ta'siri yana bir pog'ona og'irroq ekani aniqlandi: yo'qotish emas,
> **noto'g'ri iqtibos**. To'rtala tavsiya bajarildi va korpus qayta
> indekslandi.
