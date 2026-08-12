# Reranker qarori — o'lchov (2026-08-12)

**Savol:** `bge-reranker-v2-m3` ni yoqish keraкmi?

**Javob: yo'q.** U bu korpusda sifatni **pasaytiradi**.

## Sharoit

* Korpus: 20 kodeks, 7 090 modda, 8 636 bo'lak (`kb_version v2026.08.12`)
* To'plam: `retrieval-gold-v1`, 36 holat
* Embedder: BAAI/bge-m3 (CUDA)
* Reranker: BAAI/bge-reranker-v2-m3 (CPU — kechikish shu sababdan
  vakillik qilmaydi, sifat esa qiladi)
* `top_k_retrieve: 50` → `top_k_rerank: 8`

## Natija

| Metrika | Rerankersiz | Reranker bilan | Farq |
|---------|------------:|---------------:|-----:|
| Recall@1 | 42% | **47%** | +5 |
| Recall@3 | **67%** | 61% | −6 |
| **Recall@10** | **89%** | 81% | **−8** |
| MRR | 0.55 | **0.58** | +0.03 |
| Deprecated leak | 0% | 0% | — |
| Kechikish (median) | **204 ms** | 32 044 ms | CPU da |
| Kechikish (p95) | **279 ms** | 41 185 ms | CPU da |

## Nima uchun bu yomon almashuv

Reranker birinchi o'rinni biroz yaxshilaydi (Recall@1 +5, MRR +0.03) —
ya'ni u **saralashda** foyda beradi. Lekin Recall@10 ni sakkiz punktga
tushiradi: to'g'ri normani top-50 dan top-8 ga siqishda pastga surib
yuboradi va u kontekstga umuman tushmaydi.

Bu tizim uchun eng yomon yo'nalish. Groundedness gate faqat kontekstda
**bor** normani tasdiqlay oladi; kontekstga tushmagan norma javobda
hech qanday ko'rinishda paydo bo'lmaydi. Ya'ni Recall@10 — gate ning
yuqori chegarasi, va uni pasaytirish butun zanjirning shiftini
pasaytiradi.

Birinchi o'rinning +5 punkti buni qoplamaydi: sudya agenti kontekstdagi
sakkizta bo'lakni ko'radi, ularning tartibi undan kamroq muhim.

## Ehtimoliy sabab

`bge-reranker-v2-m3` ko'p tilli, lekin o'zbek tili past-resursli.
BGE-M3 embeddinglari + BM25 (RRF `k=3`) birikmasi bu korpusda undan
kuchliroq chiqdi. Reranker o'zbek yuridik atamalarining morfologik
shakllarini yetarlicha ushlamayotgan bo'lishi mumkin.

## Qaror

`use_reranker: false` — `HybridRetriever` ning standart holati
allaqachon shunday edi; profil YAML fayllari esa rerankerni
e'lon qilardi. Endi ikkalasi mos va sabab yozib qo'yilgan.

## Qachon qayta ko'rib chiqiladi

* Korpus kengaygach (qonunosti hujjatlari, sud amaliyoti, plenum
  qarorlari) — taqsimot o'zgaradi;
* Embedding fine-tuning qilingach — o'sha paytda reranker boshqa
  vazifani bajarishi mumkin;
* O'zbek tiliga moslashtirilgan reranker paydo bo'lsa.

Qayta o'lchash: `uzlegal eval retrieval --rerank --out reports/…`
