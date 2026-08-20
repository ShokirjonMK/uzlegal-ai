# 23 — Sprint 3: `chunk_id` noyobligi

**Sana:** 2026-08-18
**Manba:** `docs/22 § 9` — PM tekshiruvida topilgan, o'sha sprintga
aloqasi bo'lmagan nuqson. O'shanda alohida sprintga qoldirilgan edi,
chunki tuzatish `chunk_id` sxemasini o'zgartiradi va to'liq qayta
indekslashni talab qiladi.

| Ish | Nega |
|---|---|
| **C1** Chunkerda noyoblik kafolati | Sabab shu yerda |
| **C2** `index build` noyob sonni ko'rsatsin | E'lon qilingan raqam amaldagi raqam bo'lsin |
| **C3** `store` takrorni jimgina yutmasin | Eski indeks ochilganda ham ko'rinsin |
| **C4** Testlar | Oltala yo'l uchun |
| **C5** Qayta indekslash va o'lchov | Tuzatish faylga tushsin |
| **C6** Hisobotlardagi raqamlar | Yozilgani o'lchanganiga mos bo'lsin |

---

## 1. Nuqson `docs/22` da yozilganidan og'irroq

`docs/22 § 9` xulosasi shunday edi: «korpusning 26.4% i yuklashda
jimgina tashlab yuboriladi». O'lchov to'g'ri, lekin **oqibat noto'g'ri
baholangan**.

### 1.1 Yo'qotish emas — almashtirish

`index/store.py` ni oxirigacha o'qiganda ko'rinadi: `build()` vektor
jadvalini ham, BM25 ni ham **hamma 48 527 satr** uchun quradi.

```python
# store.py — qurish
self.doc_ids = [c.chunk_id for c in chunks]          # BM25: 48 527
rows = [{"chunk_id": c.chunk_id, "vector": …} …]     # LanceDB: 48 527

# store.py — yuklash
self._chunks[chunk.chunk_id] = chunk                 # lug'at: 35 708
```

Ya'ni yutilgan 12 819 bo'lak indeksdan **chiqib ketmagan** — ular
qidiruvda qatnashadi va ball oladi. Faqat matnni ko'rsatish paytida
lug'atga murojaat qilinadi:

```python
# store.py:411 — vektor qidiruvi
chunk = self._chunks.get(row["chunk_id"])
# store.py:472 — leksik qidiruv
chunk = self._chunks.get(chunk_id)
```

Lug'atda esa o'sha identifikator ostida **oxirgi** nusxa turadi.

Natija zanjiri:

```
so'rov  →  BM25 «-6811936:35:2» ga yuqori ball berdi
           (1-nusxa: maktabgacha ta'lim tashkilotlari)
        →  lug'atdan «-6811936:35:2» olinadi
           (187-nusxa: sport jihozlari xaridi)
        →  foydalanuvchiga 187-nusxaning matni ko'rsatiladi,
           haqiqiy `source_url` va haqiqiy modda raqami bilan
```

Bu **yo'qotish emas, noto'g'ri iqtibos**. Iqtibosga asoslangan
yuridik tizimda bu og'irroq nuqson turi: yo'qolgan bo'lak «topilmadi»
deydi, almashtirilgani esa ishonchli ko'rinadi.

### 1.2 Nima uchun buni hech kim sezmagan

`index build` chiqishida `48 527 chunk` yozilardi, `index-meta.json`
ham shu raqamni saqlardi, `index stats` esa metani qaytarardi. Uch
joyda ham **fayldagi satr soni**. Noyob sonni hech qaysi vosita
o'lchamasdi.

Bu loyihaning takrorlanuvchi naqshi (`docs/16`, `hisobotlar/04`):
**e'lon qilingan raqam amaldagi raqam emas.** Shuning uchun C2 va C3
tuzatishning o'zi qadar muhim.

---

## 2. C1 — to'qnashuv qayerdan keladi

O'lchandi (2026-08-14 korpusi, 4 484 takrorlangan identifikator):

| Bo'lak turi | Satr | Sabab |
|---|---:|---|
| `part` | 8 668 | Bir modda ichida `1.` `2.` raqamlash qayta boshlanadi |
| `article` | 3 794 | Ikki element bir xil `article_number` oladi |
| `item` | 225 | Bir qismda `a) b) … a)` ro'yxati qaytadi |
| `merged` | 132 | Yuqoridagilardan meros |

### 2.1 `part` — eng ko'p uchraydigani

`-6811936:35:2` — **187 marta**. Bu «O'zbekiston — 2030» davlat
dasturi: bitta elementning tanasida `1.` `2.` `3.` raqamlash har
bo'lim boshida qaytadan boshlanadi. `split_by(_PART_RE, …)` ularning
hammasini topadi va har biriga `{doc}:{num}:{mark}` beradi.

Bu **parser xatosi emas**: matn haqiqatan shunday raqamlangan.
Identifikator sxemasi «bir moddada bir marta `2.` qism bo'ladi» deb
faraz qilgan, dastur turidagi hujjatda esa bu faraz o'rinli emas.

### 2.2 `article` — bir hujjatda bir raqam bir necha marta

> **Tuzatish (2026-08-18, keyinroq).** Bu bo'limning birinchi
> tahririda `article` turidagi 3 794 satr **parser nuqsoniga**
> (`«244 -3 -modda»` dan `3` ajratilishi) bog'langan edi. U bitta
> namunadan umumlashtirilgan xulosa edi va **noto'g'ri**. Quyida
> to'liq tasnif keltirilgan; parser nuqsoni atigi 4 ta guruhga
> tegadi.

2 310 ta `article` guruh (6 104 satr, ortiqchasi 3 794) sabab
bo'yicha tasniflandi:

| Sabab | Guruh | Ulush |
|---|---:|---:|
| Bir hujjatning **boshqa bobida** o'sha raqam | **1 745** | **75.5%** |
| Sarlavha ham bir xil (`«1.»`, `«2.»` — raqamlangan bandlar) | 549 | 23.8% |
| Qo'shtirnoqli sarlavha (tahrir matni ichidagi modda) | 10 | 0.4% |
| **Prim raqam** — `«244 -3 -modda»` | **4** | 0.2% |
| `«Qarang:»` izohi element sifatida ajralgan | 2 | 0.1% |

### 2.2.1 Asosiy sabab — sxemada bob yo'q

Ustunlikdagi holat parser xatosi emas. O'zbek qonunchiligida
bitta hujjat bir nechta ilovadan iborat bo'ladi va **har ilova
moddani 1 dan qayta sanaydi**:

```
-8262661  «Intellektual mulk sohasidagi ayrim davlat xizmatlari…»
          1-ilova   →  1-modda, 2-modda, …
          2-ilova   →  1-modda, 2-modda, …   ← o'sha raqamlar
```

`{doc_id}:{article_number}` sxemasida bob/ilova komponenti yo'q,
shuning uchun bunday hujjatda to'qnashuv **muqarrar**.

Ta'sirlangan 348 hujjatning turi:

| `doc_type` | Guruh |
|---|---:|
| `boshqa` (nizom, tartib, ilova) | 2 197 |
| `qonun` | 35 |
| `plenum` | 30 |
| `VMQ` | 30 |
| `PF` | 12 |
| **`kodeks`** | **6** |

Ya'ni kodekslar — savol-javob yo'lining asosiy nishoni — deyarli
toza. Muammo ko'proq me'yoriy-tartib hujjatlarida.

`_enforce_unique_ids()` identifikator to'qnashuvini yopadi, lekin
**`chunks_for_article()` hamon aralashtiradi**: u `doc_id` va
`article` bo'yicha filtrlaydi, bob esa hisobga olinmaydi. Bu
alohida ish sifatida `§ 6, P1b` da qayd etilgan.

### 2.2.2 Prim raqam — kichik, lekin haqiqiy

`-111453:3` — Jinoyat kodeksining 3-moddasi va **244-3-moddasi**.
Sabab `normalize.py:236` dagi naqshda va u aniq:

```python
re.compile(r"(\d+(?:[-–]\d+)?)\s*[-–]?\s*modda", …)
```

Ichki guruh `[-–]\d+` bo'sh joydan **o'ta olmaydi**. Manba matnida
raqam bilan prim qo'shimchasi orasida bo'sh joy bo'lsa naqsh butun
raqamni emas, oxirgi bo'lagini oladi:

```
«244-3-modda»    → 244-3   ✓
«244 -3 -modda»  → 3       ✗
```

Atigi 4 ta bo'lak, lekin oqibati identifikatordan kattaroq:
iqtibos `«3-modda»` deb ko'rsatiladi, matn esa 244-3-moddaniki.
Iqtibos to'g'riligiga tegadigan nuqson — shuning uchun tuzatiladi
(`§ 7`).

### 2.3 Yechim — chiqish nuqtasida kafolat

`_enforce_limit()` bilan bir xil naqsh. Identifikator yasaydigan yo'l
oltita bo'lgani uchun har tarmoqqa alohida tekshiruv qo'yish —
unutib bo'ladigan yondashuv.

```python
def chunk_document(self, doc):
    …
    return _enforce_unique_ids(_enforce_limit(self._merge_tiny(chunks)))
```

Kafolat **eng oxirida** turadi: `_split_oversized()` va
`_enforce_limit()` tayyor identifikatorga `:{n}` qo'shadi, ya'ni
ulardan oldin tekshirish bo'linishdan chiqqan parchalarni qamramaydi.

Birinchi uchragan bo'lak identifikatorini **o'zgarishsiz** saqlaydi,
keyingilariga `#2`, `#3` qo'shiladi:

```
-6811936:35:2      ← 1-nusxa, eski qiymat
-6811936:35:2#2    ← 2-nusxa
…
-6811936:35:2#187
```

Nima uchun aynan shunday:

* **Eski havolalar buziladi emas.** To'qnashmagan 35 708 identifikator
  (korpusning 92%) o'z qiymatida qoladi, ya'ni audit jurnalidagi va
  imzolangan javob pasportlaridagi havolalar qayta indekslashdan
  keyin ham ishlaydi.
* **`#` bo'sh belgi.** Korpusda `#` bilan identifikator umuman yo'q
  edi (o'lchandi: 0 ta), `:` va `+` esa allaqachon band.
* **Deterministik.** Tartib hujjat ichidagi bo'lak tartibiga
  bog'liq, u esa parser chiqishi bilan bir xil.
* **Hech qanday kod `chunk_id` ni ajratmaydi.** Butun `src/` va
  `web/` bo'ylab tekshirildi: `chunk_id.split(":")` faqat bitta
  testda uchraydi, ishlab chiqarish kodida yo'q. Ya'ni yangi belgi
  hech nimani buzmaydi.

---

## 3. C2, C3 — raqam ko'rinadigan bo'ldi

| Joy | Ilgari | Endi |
|---|---|---|
| `index build` | `Jami 48 527 chunk` | `Jami 48 527 noyob chunk · 792 hujjat` |
| `index build` | takror sezilmasdi | embeddingdan **oldin** to'xtatadi |
| `store.build()` | takror bilan quraverardi | `ValueError` |
| `store.read_chunks()` | jimgina yutardi | `WARNING` + `duplicate_rows` |
| `index stats` | metadagi raqam | `noyob` va `takror` qatorlari |

Ikki joyda tekshirish takrorlanish emas: `index build` dagisi
embeddingdan oldin turadi (o'n daqiqani tejaydi va hujjatlar
**orasidagi** to'qnashuvni ushlaydi), `store.build()` dagisi esa
kutubxona sifatida chaqirilganda ham ishlaydi.

`read_chunks()` `load()` dan ajratildi: takrorni sanash uchun na
LanceDB, na BM25 kerak. Bu testni yengillashtiradi va `index stats`
ga vektor jadvalini ochmasdan hisob berish imkonini beradi.

---

## 4. C4 — testlar

`tests/unit/test_chunk_id_unique.py`, 12 test:

| Test | Nimani ushlaydi |
|---|---|
| `bir_xil_modda_raqami_toqnashmaydi` | Yo'l 1 — `{doc}:{num}` |
| `takroriy_qism_belgisi_toqnashmaydi` | Yo'l 2 — `{doc}:{num}:{mark}` |
| `takroriy_band_belgisi_toqnashmaydi` | Yo'l 3 — band |
| `bolingan_bolaklar_ham_qamrab_olinadi` | Yo'l 4 va 6 — bo'linish |
| `birlashtirilgan_bolak_toqnashmaydi` | Yo'l 5 — `_merge_tiny` |
| `toqnashmagan_identifikator_ozgarmaydi` | Eski havolalar ishlashda qolsin |
| `tartib_deterministik` | Ikki marta qurish farq qilmasin |
| `faqat_identifikator_ozgaradi` | Mazmun, sana, tur o'zgarmasin |
| `duplicate_ids_kamayish_tartibida` | Diagnostika to'g'ri tartibda |
| `takror_bilan_indeks_qurilmaydi` | Buzuq indeks yozilmasin |
| `read_chunks_takrorni_sanaydi` | Eski indeks ochilsa — ovoz bilan |
| `tuzatilgan_indeksda_takror_yoq` | Yangi indeks toza |

Testlar bo'sh emasligi tekshirildi: kafolat olib tashlanganda
ulardan **yettitasi yiqiladi**, qaytarilganda hammasi o'tadi.

---

## 5. C5 — qayta indekslash va o'lchov

Korpus 2026-08-18 da to'liq qayta indekslandi: 863 xom fayl → 792
hujjat, RTX 4060 Ti, fp16, 60.1 mln belgi, **~15 daqiqa**.

### 5.1 Oldin va keyin

| Ko'rsatkich | Oldin | Keyin |
|---|---:|---:|
| `chunks.jsonl` satri | 48 527 | 48 527 |
| **Qidiruvdagi noyob bo'lak** | **35 708** | **48 527** |
| Takrorlangan identifikator | 4 484 | **0** |
| Yutilgan satr | 12 819 (26.4%) | **0** |
| Tartib raqami olgan bo'lak | — | 12 819 |

Tartib raqami olganlar turi bo'yicha — `§ 2` dagi taqsimot bilan
**aynan** mos: `part` 8 668, `article` 3 794, `item` 225,
`merged` 132. Ya'ni kafolat aynan o'sha to'qnashuvlarni yopdi va
boshqa hech nimaga tegmadi.

### 5.2 Zarar haqiqatan sodir bo'lganmi

Takrorlangan identifikatorning o'zi hali zarar emas: nusxalar matni
bir xil bo'lsa, ustiga yozish hech nimani o'zgartirmaydi. Shuning
uchun zaxira nusxa (`chunks.jsonl.20260818.bak`, tuzatishdan oldingi
holat) bo'yicha alohida o'lchov o'tkazildi:

| Ko'rsatkich | Qiymat | Ulush |
|---|---:|---:|
| Takror guruh, nusxalar matni **har xil** | **4 451** | **99.3%** |
| Takror guruh, nusxalar matni bir xil | 33 | 0.7% |
| Almashtirish tegadigan satr | **12 784** | 26.3% |
| Nusxalarning `article` maydoni ham har xil | **6** | 0.1% |

Ya'ni 12 819 yutilgan satrdan 12 784 tasida foydalanuvchi
**boshqa matnni** ko'rardi. § 1.1 dagi baho tasdiqlandi.

### 5.3 Nima uchun baholash buni ko'rsatmagan

Oxirgi qator eng muhimi: takror guruhlarning atigi **6 tasida**
nusxalarning modda raqami farq qilgan. Deyarli hamma almashtirish
**bitta moddaning ichida** sodir bo'lgan — bir bandning matni
o'rniga boshqa bandniki.

`eval/retrieval_eval.py` esa `case.matches(chunk)` orqali **modda
raqami va hujjatni** taqqoslaydi, matnni emas. Shuning uchun
`retrieval-gold-v1` bu nuqsonni **printsipial ravishda ko'ra
olmaydi** — va ko'rmagan ham:

| Metrika | 2026-08-13 (buzuq indeks) | 2026-08-18 (tuzatilgan) |
|---|---:|---:|
| Recall@1 | 42% | 42% |
| Recall@3 | 64% | 64% |
| Recall@10 | 86% | 86% |
| MRR | 54% | 54% |
| Bekor qilingan norma sizishi | 0% | 0% |
| Kechikish (median) | 264 ms | **473 ms** |
| Kechikish (p95) | 453 ms | **740 ms** |

Bu xulosa metrikalar to'g'risida ham, tuzatish to'g'risida ham:

* **Tuzatish keraksiz emas edi.** 12 784 satrda noto'g'ri matn
  ko'rsatilardi; baholash to'plami shu turdagi zararni o'lchamaydi,
  o'lchamagani esa zarar yo'q degani emas.
* **To'plamda teshik bor.** Hozirgi holatlar «to'g'ri moddaga
  ishora qilindimi» degan savolga javob beradi. «Ko'rsatilgan matn
  o'sha moddaniki mi» degan savol **umuman o'lchanmaydi**. Bu
  A3 (yurist ekspert) doirasidagi ish: gold setga matn darajasidagi
  tekshiruv qo'shilishi kerak.

### 5.4 Kechikish ikki baravar oshdi

264 → 473 ms median. Sabab shu tuzatish: qidiriladigan bo'lak soni
35 708 → 48 527 (+36%), `BM25Index.search()` esa butun korpus
bo'ylab Python'da chiziqli o'tadi.

Bu **yo'qotish emas**: o'sha bo'laklar ilgari ham qidirilardi va ball
olardi — faqat natijada boshqa matn ko'rsatilardi. Endi ish haqiqatan
bajarilmoqda.

Lekin p95 740 ms maqsad (600 ms) dan yuqori va buni yopish kerak.
Bu alohida ish: `§ 6, P4`.

> ⚠️ **Tuzatish (2026-08-18, keyinroq).** Yuqoridagi izoh — 264 →
> 473 ms o'sishini bo'lak sonining ortishiga bog'lash — **to'liq
> to'g'ri emas**. Taqsimot o'lchanganda BM25 ning ulushi atigi ~55 ms
> chiqdi. 473 ms o'n besh daqiqalik indeks qurishdan darhol keyin,
> GPU hali bo'shamagan holda olingan va **toza asos emas**.
> Teskari indeksdan keyin ayni to'plamda 126 ms median / 152 ms p95.
> Batafsil: `docs/24 § 5.1`.

---

## 6. Bu sprintga kirmaydi

| # | Nima | Holat |
|---|---|---|
| **P1a** | `article_number` parseri `«244 -3 -modda»` dan `3` ajratadi | ✅ `docs/24 § 2` — 4 ta bo'lak tuzatildi |
| **P1b** | `chunks_for_article()` bir xil raqamli moddalarni aralashtiradi | ✅ `docs/24 § 3` — `element_id` bo'yicha ajratildi |
| **P2** | — | P1b bilan birlashtirildi |
| **P3** | Yorliq qism belgisi takrorlanganda ham bir xil ko'rinadi | ✅ `docs/25 § 3` — 19 024 bo'lak (39.2%) ta'sirlangan ekan; `citation_label` da tartib raqami qo'shildi (`heading` da emas — `docs/25 § 4`) |
| **P4** | Kechikish p95 740 ms, maqsad 600 ms | ✅ `docs/24 § 4` — BM25 teskari indeksga o'tdi (8.9×) |
| **P5** | `retrieval-gold-v1` matn to'g'riligini o'lchamaydi | ⏸ ochiq — A3 (yurist ekspert) doirasida |

> **Diqqat:** `§ 2.2` ning birinchi tahriri P1 ni to'qnashuvlarning
> **asosiy sababi** deb ko'rsatgan edi. To'liq tasnif buni rad etdi —
> parser nuqsoni 2 310 guruhdan atigi 4 tasiga tegadi. Tuzatilgan
> tahlil `§ 2.2` da, sabab esa `docs/24 § 1` da.
