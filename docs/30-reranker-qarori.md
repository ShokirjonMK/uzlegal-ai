# 30 — Reranker: qayta o'lchov va qaror

**Sana:** 2026-08-21
**Manba:** strategiya, A2 — «reranker R@1 ni ko'tarsin».

---

## 1. Nima uchun qayta o'lchandi

Reranker ilgari ikki marta o'lchangan va ikkalasida ham natija
yomon chiqqan:

| O'lchov | R@1 | R@3 | R@10 | Kechikish |
|---|---:|---:|---:|---:|
| `retrieval-rerank.md` | 31% | 42% | 56% | 11.5 s |
| `retrieval-rerank-natija-2026-08-12.md` | 47% | 61% | 81% | 32 s |

Shuning uchun u o'chirilgan. Odatda bunday savolni qayta ochish —
ishni takrorlash bo'lardi.

**Lekin bu safar asos o'zgargan edi.** Ikkala o'lchov ham
**2026-08-12** da olingan, `chunk_id` nuqsoni esa **2026-08-18** da
tuzatilgan (`docs/23`). O'sha paytda `store.load()` bo'laklarning
**26.4% ida noto'g'ri matn** qaytarardi.

Reranker esa aynan **chunk matnini** o'qiydi
(`rerank()` → `item.chunk.indexed_text`). Ya'ni u har to'rtinchi
nomzodda **boshqa normaning matnini** baholagan. Bunday sharoitdagi
o'lchov reranker haqida emas, buzuq indeks haqida gapiradi.

---

## 2. Yangi o'lchov

Bir xil to'plam (36 holat), tuzatilgan indeks, `qwen3:8b` faol
(reranker modelga bog'liq emas — u alohida cross-encoder).

| Metrika | Rerankersiz | Reranker bilan | Farq |
|---|---:|---:|---:|
| Recall@1 | 42% | **50%** | **+8 p.p.** |
| Recall@3 | 64% | 64% | 0 |
| Recall@10 | **86%** | 78% | **−8 p.p.** |
| MRR | 54% | **59%** | +5 p.p. |
| Bekor qilingan norma sizishi | 0% | 0% | — |
| Kechikish (median) | ~270 ms | **1 353 ms** | **5×** |

Eski o'lchovlarga nisbatan sezilarli yaxshilanish (32 s → 1.35 s,
R@10 81% → 78% emas, balki taqqoslash bazasi ham o'zgargan) —
ya'ni buzuq indeks haqiqatan natijani buzgan edi.

---

## 3. R@10 nima uchun tushadi — bu nuqson emas

Birinchi qarashda g'alati: qayta tartiblash **bir xil** nomzodlarni
aralashtiradi, ro'yxatdan chiqarmasligi kerak.

Sabab `hybrid.py:414` da:

```python
head = filtered[: max(top_k * 3, 20)]
filtered = self.reranker.rerank(query, head) + filtered[len(head):]
```

`top_k=10` bo'lganda reranker **top-30** ni qayta tartiblaydi. Ya'ni
11–30 o'rindagi nomzod 1–10 dagi to'g'ri javobdan yuqoriga ko'tarilishi
mumkin va to'g'ri javob top-10 dan **chiqib ketadi**.

Bu kengaytirilgan nomzod to'plamining tabiiy narxi. Xulosa:
**cross-encoder tartibi bu domenda RRF dan yomonroq** — birinchi
o'rindan tashqari.

---

## 4. Qaror

**Reranker o'chiq qoladi.**

Sabab ishlatilish usulida. Norma topuvchi mahsulotida foydalanuvchi
**ro'yxatni ko'radi**: kerakli modda ro'yxatda bo'lsa, u topiladi.
Shuning uchun bu mahsulot uchun muhim metrika **R@10**, R@1 emas —
va reranker aynan R@10 ni pasaytiradi.

Narx tomoni ham bir yoqlama emas: 5 barobar kechikish (270 ms →
1.35 s) interaktiv qidiruvda sezilarli.

### 4.1 Qachon u foydali bo'lardi

Agar interfeys **bitta** javob ko'rsatsa — R@1 muhim bo'lardi va
reranker +8 p.p. bergan bo'lardi. Ya'ni bu **interfeys qaroriga
bog'liq**, mutlaq emas.

Shuning uchun kod o'chirilmadi: `--rerank` bayrog'i va
`use_reranker` sozlamasi joyida qoladi. Qaror o'zgarsa —
o'lchov ham, kod ham tayyor.

---

## 5. Ochiq qolgani

| # | Nima | Nega |
|---|---|---|
| **R1** | `head` hajmi (`top_k * 3`) sozlanadigan bo'lsin | Hozir qotirilgan. `head = top_k` bo'lsa R@10 tushmasdi, lekin reranker foydasi ham kamayardi — o'lchanmagan |
| **R2** | Reranker kengaytirilgan gold setda qayta o'lchansin | 36 holat ±16 p.p. beradi; ±8 p.p. farqlar shu shovqin ichida |

R2 alohida diqqatga arziydi: yuqoridagi **barcha farqlar shovqin
chegarasiga yaqin**. Qaror ular asosida emas, **kechikish** va
**mahsulot ko'rinishi** asosida qabul qilindi — bu ikkalasi
shovqinga bog'liq emas.
