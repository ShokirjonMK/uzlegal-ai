# Ma'lumot manbalari

Bu hujjat bilim bazasidagi har bir manbani, uning litsenziyasini va ishlatish shartlarini qayd etadi. Har yangi manba qo'shilganda yangilanadi.

## Holat: Faza 1 boshlanmagan — quyidagilar rejalashtirilgan manbalar

## 1. Normativ-huquqiy hujjatlar

| Manba | URL | Turi | Hajm (taxminiy) | Litsenziya | Holat |
|-------|-----|------|-----------------|------------|-------|
| Qonunchilik ma'lumotlari milliy bazasi | lex.uz | Kodeks, qonun, PF, PQ, VM qarorlari | ~40 000 | Ochiq rasmiy ma'lumot | 📋 Rejada |
| Oliy sud Plenumi qarorlari | lex.uz / sud.uz | Tushuntirish qarorlari | ~300 | Ochiq | 📋 Rejada |
| Vazirlik va idora hujjatlari | tegishli saytlar | Idoraviy hujjatlar | ~10 000 | Ochiq | 📋 Rejada |

**Huquqiy asos:** O'zbekiston Respublikasi qonunchiligiga muvofiq normativ-huquqiy hujjatlar rasmiy e'lon qilinadi va ochiq foydalanishda bo'ladi. Mualliflik huquqi ob'ekti hisoblanmaydi.

## 2. Sud amaliyoti

| Manba | URL | Turi | Hajm | Litsenziya | Holat |
|-------|-----|------|------|------------|-------|
| Ochiq sud qarorlari | public.sud.uz | Sud qarorlari | ~500 000 | Ochiq (PII bilan) | 📋 Rejada |

⚠️ **Shaxsiy ma'lumotlar:** sud qarorlarida F.I.Sh., manzil, hujjat raqamlari bo'ladi. Indekslashdan **oldin** anonimizatsiya majburiy — [`docs/03-data-pipeline.md`](docs/03-data-pipeline.md#37-pii-anonimizatsiya).

Anonimizatsiya sifati o'lchanadi: 500 ta qaror namunasida qolib ketgan PII ≤ 0.5%.

## 3. Doktrinal manbalar

| Manba | Turi | Litsenziya | Holat |
|-------|------|------------|-------|
| Yuridik darsliklar | Kitob | ⚠️ Mualliflik huquqi — **ruxsat kerak** | ⛔ Bloklangan |
| Ilmiy maqolalar | Maqola | Har biri alohida tekshiriladi | ⛔ Bloklangan |
| Ochiq sharhlar | Sharh | Ochiq | 📋 Rejada |

**Qoida:** mualliflik huquqi bilan himoyalangan material **yozma ruxsatsiz** korpusga kiritilmaydi. Bu Faza 1 da hal qilinishi kerak bo'lgan masala.

## 4. Yig'ish qoidalari

Barcha veb-manbalar uchun:

| Qoida | Qiymat |
|-------|--------|
| `robots.txt` | Qat'iy rioya |
| Rate limit | ≤ 1 so'rov/soniya |
| `User-Agent` | `UzLegal-AI/0.x (+github.com/ShokirjonMK/uzlegal-ai; aloqa)` |
| Qayta urinish | Eksponensial kechikish, maksimum 3 |
| Foydalanish shartlari | Har manba uchun tekshiriladi |
| Xom nusxa | O'zgarmas arxivda saqlanadi (takrorlanuvchanlik) |

## 5. Model manbalari

| Model | Manba | Litsenziya |
|-------|-------|------------|
| Baza model | ⏳ Faza 0 da tanlanadi | Apache-2.0 ga ustunlik |
| BGE-M3 (embedding) | BAAI/bge-m3 | MIT |
| bge-reranker-v2-m3 | BAAI/bge-reranker-v2-m3 | Apache-2.0 |

## 6. Trening ma'lumoti

| To'plam | Manba | Hajm (maqsad) | Holat |
|---------|-------|---------------|-------|
| SFT umumiy | Sintetik + real hujjatlar, yurist tekshirgan | 20 000 | 📋 Faza 3 |
| Rol datasetlari (×5) | Sintetik + real, yurist tekshirgan | 8 000/rol | 📋 Faza 3 |
| Gold set | Yurist tomonidan yozilgan | 500 | 📋 Faza 3 |

Barcha trening namunalari `verified_by` va `verified_at` maydonlarini saqlaydi — kim va qachon tekshirgani kuzatiladi.

## 7. Manba qo'shish tartibi

Yangi manba qo'shishdan oldin:

1. Litsenziya va foydalanish shartlarini tekshirish
2. PII mavjudligini baholash
3. Shu jadvalga qator qo'shish
4. Konnektor yozish (`src/uzlegal/ingest/connectors/`)
5. Validatsiya qoidalarini qo'shish
6. 50 hujjat namunasida qo'lda tekshirish

Litsenziya noaniq bo'lsa — **manba qo'shilmaydi**.
