# 24 — Sprint 4: modda raqami va kechikish

**Sana:** 2026-08-18
**Manba:** `docs/23 § 6` — o'sha sprintda ochiq qoldirilgan uchta band.
Ikkitasi bajarildi (P1, P4), uchinchisi (P5) yuristsiz bajarilmaydi.

| Ish | Nega |
|---|---|
| **D1** `docs/23 § 2.2` tuzatilsin | O'sha bo'limdagi sabab tahlili noto'g'ri edi |
| **P1a** Parser: `«244 -3 -modda»` | Iqtibos noto'g'ri moddaga ishora qiladi |
| **P1b** `chunks_for_article()` | Turli ilovalardagi moddalarni jimgina aralashtiradi |
| **P4** BM25 kechikishi | p95 740 ms, maqsad 600 ms |

---

## 1. D1 — o'z xulosamni tuzatish

`docs/23 § 2.2` da `article` turidagi 3 794 to'qnashuv **parser
nuqsoniga** bog'langan edi. U bitta namunadan (`-111453:3`)
umumlashtirilgan xulosa edi.

To'liq tasnif o'tkazilganda ma'lum bo'ldiki, bu **noto'g'ri**:

| Sabab | Guruh | Ulush |
|---|---:|---:|
| Bir hujjatning boshqa bobida o'sha raqam | **1 745** | **75.5%** |
| Sarlavha ham bir xil (`«1.»`, `«2.»`) | 549 | 23.8% |
| Qo'shtirnoqli sarlavha | 10 | 0.4% |
| **Parser nuqsoni** (prim raqam) | **4** | **0.2%** |
| `«Qarang:»` izohi | 2 | 0.1% |

Parser nuqsoni sabablarning **eng kichigi** ekan. `docs/23 § 2.2`
o'lchangan tasnif bilan qayta yozildi va tuzatish izohi qo'yildi.

Xulosa metod haqida: bitta namunadan sabab chiqarish — shu
loyihaning o'zi qayta-qayta ushlagan naqsh (`docs/16`,
`hisobotlar/04`: «e'lon qilingan raqam amaldagi raqam emas»).
Bu safar naqsh **hisobotning o'zida** takrorlandi.

---

## 2. P1a — prim moddaning raqami

### 2.1 Sabab

`normalize.py` dagi naqsh:

```python
re.compile(r"(\d+(?:[-–]\d+)?)\s*[-–]?\s*modda", re.IGNORECASE)
```

Ichki guruh `[-–]\d+` bo'sh joydan o'ta olmaydi. Manbada bir xil
modda ikki ko'rinishda keladi:

```
«244-3-modda»    → 244-3   ✓
«244 -3 -modda»  → 3       ✗
```

Ikkinchi holatda 244-3-modda **«3-modda» deb iqtibos qilinardi** —
haqiqiy `source_url` va butunlay boshqa modda raqami bilan.

### 2.2 Tuzatish va nima uchun aynan shunday

```python
_PRIM = r"(?:\s*[-–]\d+)?"
```

Tire **oldidan** bo'sh joyga ruxsat beriladi, **keyinidan** yo'q.
Bu tasodifiy tanlov emas: kodda bu farq allaqachon ishlatiladi.
`_RUN_RANGE` diapazon ajratuvchisini aynan shu bilan aniqlaydi —
ikki tomonida ham bo'sh joy bo'lgan tire ajratuvchi, aks holda
prim qo'shimchasi.

Shuning uchun quyidagilar buzilmaydi:

| Kirish | Natija |
|---|---|
| `«24 — 35-moddalari»` | `35` (diapazon, `24-35` emas) |
| `«173-1 - 173-7-moddalar»` | `173-7` |
| `«65 va 66-moddalar»` | `66` |

### 2.3 O'lchov

Butun korpus qayta bo'laklandi va eski indeks bilan solishtirildi:

| Ko'rsatkich | Qiymat |
|---|---:|
| Modda raqami o'zgargan bo'lak | **4** |
| Boshqa o'zgarish | **0** |
| Noyob `chunk_id` | 48 527 (takror 0) |

```
'3'  →  '244-3'    -111453:244-3    Jinoyat kodeksi
'5'  →  '24-5'     -152653:24-5     Yer kodeksi
'2'  →  '56-2'     -97664:56-2      MJtK
'4'  →  '56-4'     -97664:56-4      MJtK
```

To'rtta bo'lak — kichik raqam, lekin bu **iqtibos to'g'riligiga**
tegadigan yagona ma'lum nuqson edi.

---

## 3. P1b — `chunks_for_article()` ilovalarni aralashtirardi

### 3.1 Muammo

Modda raqami hujjat ichida noyob **emas** (§ 1). Funksiya esa faqat
`doc_id` va `article` bo'yicha filtrlardi:

```python
found = [c for c in self._chunks.values()
         if c.doc_id == doc_id and c.article == article]
```

Ya'ni 1-ilovaning 5-moddasi va 2-ilovaning 5-moddasi **bitta
moddaning bo'laklari** sifatida qaytardi. Chaqiruvchi buni sezmasdi.

Eng jiddiy oqibat `collisions.py:121` da:

```python
chunks = self._source.chunks_for_article(doc_id, article, limit=1)
self._cache[key] = chunks[0].status if chunks else None
```

Saralash `(part, item, chunk_id)` bo'yicha, ya'ni `limit=1`
**qaysi ilova** birinchi kelishiga bog'liq. Amaldagi modda boshqa
ilovadagi bekor qilingan modda tufayli «bekor» deb belgilanishi
mumkin edi — va aksincha.

### 3.2 Yechim

Hujjat tartibida **birinchi** modda tanlanadi va faqat o'shanikilari
qaytadi. Modda kimligi `element_id` bilan aniqlanadi — u parserdan
keladigan element identifikatori, ya'ni moddaning o'zi.

```python
first = found[0].element_id          # fayl tartibi = hujjat tartibi
same = [c for c in found if c.element_id == first]
```

Tanlov endi **aniq**: ilgari ham bitta natija qaytardi, lekin u
saralash artefakti edi.

Noaniqlikning o'zi yo'qolmaydi — u ko'rinadigan qilindi:

| Yangi | Nima beradi |
|---|---|
| `article_variants(doc_id, article)` | Shu raqamni tashiydigan moddalarning bob yo'llari |
| `ambiguous_articles()` | Hujjat → noaniq raqamlar soni |

Tuzatilgan indeksda o'lchandi:

| Ko'rsatkich | Qiymat |
|---|---:|
| Noaniq modda raqami bor hujjat | **365** |
| Jami noaniq raqam | **2 638** |
| Eng ko'pi (`-8262661`, intellektual mulk xizmatlari) | 109 |

Ya'ni har oltinchi hujjatda kamida bitta modda raqami ikki ma'noli.
Bu korpusning xossasi, nuqson emas — lekin endi u **o'lchanadi**.

### 3.3 Nima QILINMADI

Iqtibos qidiruvi hamon **bitta** moddani tanlaydi. To'g'ri yechim —
foydalanuvchiga «bu hujjatda 5-modda ikkita: 1-ilovada va
2-ilovada» deb aytish. Bu interfeys qarori va u alohida ish
(`§ 6, P6`).

---

## 4. P4 — kechikish

### 4.1 Sabab

`BM25Index.search()` har atama uchun **butun korpusni** aylanardi:

```python
for term in terms:
    for i, freqs in enumerate(self.doc_freqs):   # 48 527 marta
        tf = freqs.get(term, 0)
        if tf == 0:
            continue                              # 99% shu yerda
```

Ish hajmi so'rovga emas, **korpus kattaligiga** bog'liq edi. Yuridik
atama esa korpusning kichik qismida uchraydi: «vindikatsiya» o'n
martacha, «modda» o'n minglab marta. Birinchisi uchun 48 527 ta
lug'at qidiruvining 48 517 tasi behuda edi.

Bo'lak soni 35 708 → 48 527 bo'lgach bu behuda ish 36% ga ko'paydi.
Lekin kechikishning **hammasi** shundan emas — `§ 5.1` ga qarang.

### 4.2 Yechim — teskari indeks

`term → [(bo'lak indeksi, chastota), …]`. Endi faqat atamani
**haqiqatan tashiydigan** bo'laklar aylanadi. Hujjat normalizatori
(`1 - b + b·len/avg`) ham qurish paytida bir marta hisoblanadi.

Pikel formati o'zgardi (`doc_freqs` → `postings`), lekin eski fayl
ham o'qiladi: `load()` `doc_freqs` ni ko'rsa teskari indeksni
o'zi yig'adi. Foydalanuvchini sababsiz qayta indekslashga majbur
qilish kerak emas.

### 4.3 O'lchov

Bir xil indeks, 36 ta gold so'rov, faqat BM25 (embedding va vektor
qidiruvisiz):

| | Median | p95 |
|---|---:|---:|
| Eski (chiziqli) | 62 ms | 108 ms |
| **Yangi (teskari indeks)** | **7 ms** | **22 ms** |
| | **8.9×** | **4.9×** |

**Natija bir xilligi tekshirildi:** 36 ta so'rovning hammasida
top-10 tartibi **aynan bir xil**, eng katta ball farqi **0.0**.
`df` va `len(postings)` 74 253 atamaning hammasida teng.

Ya'ni bu tezlik sifat hisobiga olinmagan.

---

## 5. To'liq qidiruv kechikishi

Korpus qayta indekslandi (48 527 noyob bo'lak, takror 0) va gold
to'plam qayta o'lchandi.

| O'lchov | Median | p95 |
|---|---:|---:|
| 2026-08-13 (35 708 bo'lak) | 264 ms | 453 ms |
| 2026-08-18, `docs/23` dan keyin | 473 ms | 740 ms |
| **2026-08-18, shu sprintdan keyin** | **126 ms** | **152 ms** |

Maqsad (600 ms p95) yopildi.

### 5.1 473 ms raqami ishonchsiz — buni aytish kerak

`docs/23 § 5.4` da 264 → 473 ms o'sishi **bo'lak sonining 36% ga
oshishiga** bog'langan edi. Bugungi o'lchovlar buni tasdiqlamaydi.

Taqsimot (ayni indeks, ayni mashina, 36 so'rov):

| Qism | Median |
|---|---:|
| BM25 (teskari indeks) | 7 ms |
| Qolgani (so'rov embeddingi + LanceDB + RRF) | ~119 ms |
| **Jami** | **126 ms** |

BM25 tuzatishi eski o'lchov bo'yicha 62 → 7 ms, ya'ni **~55 ms**
tejaydi. Ayni sharoitda eski BM25 bilan jami ~181 ms bo'lardi —
473 ms emas.

Farqning sababi o'lchov sharoitida: 473 ms o'n besh daqiqalik
indeks qurishdan **darhol keyin** olingan va GPU o'sha paytda hali
bo'shamagan edi (`_warn_if_vram_busy()` aynan shu holatni
tasvirlaydi). Ya'ni u toza asos emas.

Halol xulosa:

* **BM25 tezlanishi haqiqiy va o'lchangan** — 8.9×, natija bir xil;
* **473 ms → 126 ms deyish noto'g'ri bo'lardi** — uning katta
  qismi apparat bandligidan;
* Taqqoslash uchun yaroqli asos — 13-avgustdagi 264 ms. Unga
  nisbatan **2.1× tezroq**, ustiga indeks 36% kattaroq.

`docs/23 § 5.4` ga tuzatish izohi qo'yildi.

### 5.2 Sifat o'zgarmadi — va bu tekshirildi

| Metrika | Sprintdan oldin | Keyin |
|---|---:|---:|
| Recall@1 | 42% | 42% |
| Recall@3 | 64% | 64% |
| Recall@10 | 86% | 86% |
| MRR | 54% | 54% |
| Bekor qilingan norma sizishi | 0% | 0% |

Bu kutilgan: BM25 natijasi **bayt-bayt** bir xil (§ 4.3), P1a esa
4 ta bo'lakka tegadi va ularning hech biri gold to'plamda yo'q.

Metrikalarning qimirlamagani shu sprintda **kutilgan natija**, oldingi
sprintdagidek izohlanishi kerak bo'lgan hodisa emas.


---

## 6. Bu sprintga kirmaydi

| # | Nima | Nega |
|---|---|---|
| **P5** | `retrieval-gold-v1` matn to'g'riligini o'lchamaydi | A3 — yurist ekspert kerak |
| **P6** | Noaniq modda raqamida foydalanuvchiga tanlov ko'rsatilsin | Interfeys qarori (§ 3.3) |
| **P7** | `«1.»` sarlavhali 549 element modda emas, band | Parser tuzilma masalasi, o'z o'lchoviga muhtoj |
