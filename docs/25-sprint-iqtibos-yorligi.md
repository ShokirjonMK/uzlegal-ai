# 25 — Sprint 5: iqtibos yorlig'ining aniqligi

**Sana:** 2026-08-18
**Manba:** `docs/24 § 6` — P3 va P7. Ikkalasi ham «kichik band» deb
yozilgan edi. O'lchov ikkalasi ham korpusning uchdan bir qismiga
tegishini ko'rsatdi.

| Ish | Nega |
|---|---|
| **P7** Farmon bandi «modda» deb iqtibos qilinadi | 16 877 bo'lak (34.8%) noto'g'ri birlik |
| **P3** Iqtibos yorlig'i takrorlanadi | 19 024 bo'lak (39.2%) bir xil nom ostida |

---

## 1. Nima uchun yorliq muhim

`citation_label` — bu shunchaki ko'rinish emas. `retrieval/hybrid.py`
modelga beriladigan kontekst bloklarini aynan shu nom bilan
belgilaydi:

```python
f"=== [{tag}] {chunk.citation_label} ===\n"
```

Model iqtibosni shu nomdan ko'chiradi. Ya'ni yorliqdagi xato
to'g'ridan-to'g'ri **javobdagi iqtibosga** o'tadi. Xuddi shu nom
CLI da (`main.py:1127`), MCP serverida (`server.py:117`) va
ta'lim modullarida ishlatiladi.

Bu `chunk_id` muammosining (`docs/23`) **ko'rinadigan yuzi**:
identifikator darajasida to'qnashuv yopilgan edi, foydalanuvchi va
model ko'radigan darajada esa yo'q.

---

## 2. P7 — «modda» va «band»

### 2.1 Muammo

Sarlavhasi faqat raqamdan iborat element (`1.`, `2.`, `12)`) —
**17 304 ta**, korpusning 35.7% i. Bular modda emas: farmon, qaror
va nizomning raqamlangan bandlari.

`ingest/types.py` da xarita bor va u to'g'ri, lekin standart qiymat
«modda»:

```python
_UNIT_BY_DOC_TYPE = {"kodeks": "modda", "qonun": "modda",
                     "PF": "band", "PQ": "band", "VMQ": "band", …}

def unit_label(doc_type):
    return _UNIT_BY_DOC_TYPE.get(doc_type or "", "modda")
```

Korpusda hujjatlarning katta qismi `doc_type = "boshqa"` (nizom,
tartib, ilova) va ular standart qiymatga tushardi:

| `doc_type` | Ilgari | Bo'lishi kerak | Bo'lak |
|---|---|---|---:|
| `boshqa` | modda | **band** | 16 453 |
| `qonun` | modda | **band** | 379 |
| `VMQ` | band | **modda** | 45 |
| | | **Jami** | **16 877** |

Diqqat: oxirgi qator teskari yo'nalishda. `VMQ` turidagi hujjatda
haqiqiy «244-modda. …» sarlavhali element bor edi va u «band» deb
atalardi.

`unit_label()` ning o'z izohi buni allaqachon aytgan:

> «Farmonning 3-moddasi» degan havolani yurist izlab topa olmaydi —
> u yerda modda yo'q, band bor.

Izoh to'g'ri edi, qamrovi tor edi.

### 2.2 Yechim — dalil hujjat turida emas, element sarlavhasida

```python
def unit_for(doc_type: str, element_title: str | None) -> str:
    if _BARE_NUMBER_TITLE.match(title):   # «1.», «12)», «7-1.»
        return "band"
    if _ARTICLE_TITLE.search(title):      # «244-modda. …»
        return "modda"
    return unit_label(doc_type)           # zaxira
```

Elementning o'z sarlavhasi hujjat turkumidan **aniqroq dalil**:
sarlavha `1.` bo'lsa bu band, `244-modda.` bo'lsa modda — hujjat
qanday turkumlangani ahamiyatsiz. Turkum faqat sarlavha jim
qolganda ishlatiladi.

Natija `Chunk.unit` maydonida saqlanadi va `citation_label` o'shani
o'qiydi.

---

## 3. P3 — bir yorliq, ko'p bo'lak

### 3.1 Muammo

**19 024 bo'lak (39.2%)** kamida bitta boshqa bo'lak bilan bir xil
iqtibos yorlig'iga ega edi. Eng og'iri:

```
«Davlat dasturi, 35-modda, 2-qism»   ← 187 xil matn
```

Model shu nom ostida 187 xil kontekst blokini oladi va javobda ham
shu nomni qaytaradi. Foydalanuvchi iqtibosni tekshirmoqchi bo'lsa
qaysi matn nazarda tutilganini **aniqlay olmaydi**.

### 3.2 Ikki sabab, biri `#` bilan qoplanmagan

| Sabab | Bo'lak | `chunk_id` da |
|---|---:|---|
| Takrorlangan raqamlash | 12 815 | `#2`, `#3`, … |
| O'lchamga ko'ra bo'linish | ~6 200 | `:2`, `:3` |

Ikkinchisi muhim: `_split_oversized()` va `_enforce_limit()` bitta
moddaning matnini bo'ladi. `chunk_id` har xil bo'ladi, modda, qism
va band esa **bir xil qoladi** — ya'ni yorliq ham.

Shuning uchun raqamlash `chunk_id` dan emas, **yorliq kalitidan**
(`doc_id`, `article`, `part`, `item`) yuritiladi.

### 3.3 Yechim

`_number_occurrences()` — chunkerning chiqish nuqtasidagi uchinchi
kafolat, `_enforce_limit()` va `_enforce_unique_ids()` dan keyin:

```python
return _number_occurrences(
    _enforce_unique_ids(_enforce_limit(self._merge_tiny(chunks)))
)
```

Birinchi bo'lak yorlig'i **o'zgarmaydi**, keyingilariga tartib
raqami qo'shiladi:

```
Davlat dasturi, 35-modda, 2-qism
Davlat dasturi, 35-modda, 2-qism (2-bo'lak)
Davlat dasturi, 35-modda, 2-qism (3-bo'lak)
```

Bu `docs/23` dagi `#N` bilan bir xil tamoyil: takrorlanmagan yorliq
qanday bo'lsa shundayligicha qoladi, ya'ni eski iqtiboslarning
ko'pchiligi o'z ko'rinishida saqlanadi.

---

## 4. `heading` ataylab tegilmadi

P3 dastlab «`heading` takrorlanadi» deb yozilgan edi. Tuzatish
`heading` da emas, `citation_label` da qilindi. Sabab:

```python
@property
def indexed_text(self) -> str:
    return f"{self.heading}\n\n{self.content}"
```

`heading` embedding va BM25 matniga **kiradi**. Unga tartib raqami
qo'shish 12 819 bo'lakning embeddingiga ma'nosiz token qo'shardi va
qidiruv sifatiga ta'sirini oldindan aytib bo'lmasdi — hech qanday
foyda evaziga, chunki foydalanuvchi ham, model ham iqtibosni
`citation_label` dan oladi.

`heading` — tuzilma yo'li (`[Hujjat > bob > modda > qism]`).
`citation_label` — nom. Aniqlik nomga kerak edi.

---

## 5. API

`/v1/search` javobiga uchta maydon qo'shildi:

| Maydon | Nima |
|---|---|
| `citation` | To'liq iqtibos nomi — birlik va tartib raqami bilan |
| `unit` | `modda` yoki `band` |
| `occurrence` | Yorliqdagi tartib raqami (1 — takrorlanmagan) |

`heading` o'z ma'nosida qoldi.

---

## 6. O'lchov

Korpus qayta indekslandi: 48 527 noyob bo'lak, 792 hujjat.

### 6.1 P7 — birlik

| Birlik | Bo'lak | Ulush |
|---|---:|---:|
| `band` | **26 869** | 55.4% |
| `modda` | 21 658 | 44.6% |

Tuzatishdan oldin `band` deb atalganlari atigi 10 kichik guruh edi
(`PF`, `PQ`, `VMQ`, `plenum`, `qaror` turlari). Endi korpusning
yarmidan ko'pi — to'g'ri birlik bilan.

Namunalar:

```
-1347565:1   → «ADVOKATURA INSTITUTINI … TO'G'RISIDA, 1-band»
-111453:3    → «JINOYAT KODEKSI, 3-modda»
```

Farmon endi «1-modda» demaydi, kodeks esa «3-band» demaydi.

### 6.2 P3 — yorliq to'qnashuvi

| Ko'rsatkich | Oldin | Keyin |
|---|---:|---:|
| Tartib raqami olgan bo'lak | — | 13 688 |
| **Qolgan yorliq to'qnashuvi** | 19 024 | **0** |

### 6.3 Sifat o'zgarmadi — va o'zgarmasligi shart edi

| Metrika | Oldin | Keyin |
|---|---:|---:|
| Recall@1 | 42% | 42% |
| Recall@3 | 64% | 64% |
| Recall@10 | 86% | 86% |
| MRR | 54% | 54% |
| Bekor qilingan norma sizishi | 0% | 0% |

Bu tasodif emas, **loyihaning shartidan** kelib chiqadi: `heading`
ham, `content` ham tegilmadi, ya'ni `indexed_text` bir xil qoldi va
embeddinglar ham o'zgarmadi (§ 4). O'zgargani — faqat ko'rsatiladigan
nom.

### 6.4 Kechikish: bu mashinada o'lchash ishonchsiz

`docs/24 § 5.1` da 473 ms raqami rad etilgan edi — u GPU band
paytida olingan. Bugungi o'lchov o'sha bo'limning **o'z raqamini
ham** shubha ostiga qo'yadi.

Bir xil kod, bir xil indeks, bir necha soat oralig'ida:

| Sessiya | BM25 median | To'liq qidiruv median |
|---|---:|---:|
| `docs/24` yozilgan payt | 7 ms | 126 ms |
| Bugun (63 ta brauzer jarayoni) | 15 ms | ~270 ms |

Ikki barobar farq — va kod o'rtada o'zgarmagan. Ya'ni bu
mashinadagi **mutlaq** kechikish raqamlari sessiyalar orasida
taqqoslanmaydi.

Taqqoslanadigan yagona narsa — **ayni sessiyadagi nisbat**. Eski
BM25 bugungi sharoitda qayta o'lchandi:

| Ayni sessiya, 36 so'rov | Median | p95 |
|---|---:|---:|
| Eski (chiziqli) | 131 ms | 254 ms |
| **Yangi (teskari indeks)** | **16 ms** | **46 ms** |
| | **8.0×** | 5.5× |

`docs/24` da o'lchangan nisbat 8.9× edi. Ikki sessiya mutlaq
raqamda ikki barobar farq qildi, **nisbatda esa mos keldi** —
demak tezlanish haqiqiy, raqamning o'zi esa sharoitga bog'liq.

**Xulosa metod haqida:** kechikish maqsadi (`p95 < 600 ms`) bu
mashinada tekshirilmaydi. Uni tekshirish uchun barqaror muhit
kerak — CI yugurtiruvchisi yoki maxsus o'lchov mashinasi.
Qayd etildi: `§ 7, P9`.


---

## 7. Bu sprintga kirmaydi

| # | Nima | Nega |
|---|---|---|
| **P5** | `retrieval-gold-v1` matn to'g'riligini o'lchamaydi | A3 — yurist ekspert kerak |
| **P6** | Noaniq modda raqamida foydalanuvchiga tanlov ko'rsatilsin | Interfeys qarori (`docs/24 § 3.3`) |
| **P8** | `article` maydoni band raqamini ham saqlaydi | Nom noaniq, lekin qayta nomlash butun kodga tegadi |
| **P9** | Kechikish barqaror muhitda o'lchansin | Bu mashinada raqamlar ikki barobar tebranadi (§ 6.4) |
