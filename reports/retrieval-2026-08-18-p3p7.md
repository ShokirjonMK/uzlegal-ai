# Retrieval baholash — gibrid

**Sana:** 2026-08-18 — `docs/25` sprintidan keyin
**Indeks:** `kb/current` — 792 hujjat · 48 527 noyob bo'lak

> **Sifat o'zgarmadi va o'zgarmasligi shart edi.** Bu sprint faqat
> `citation_label` ga tegdi; `heading` va `content` tegilmadi, ya'ni
> `indexed_text` va embeddinglar bir xil qoldi (`docs/25 § 4`).
>
> **Kechikish raqamiga ishonmang.** Bu mashinada bir xil kod va
> indeksda o'lchov sessiyalar orasida ikki barobar tebranadi
> (7 → 15 ms BM25, 126 → 270 ms to'liq qidiruv). Taqqoslanadigan
> yagona narsa — ayni sessiyadagi nisbat (`docs/25 § 6.4`).

Holatlar: 36 · reranker: yo‘q

| Metrika | Natija | Maqsad | |
|---------|-------:|-------:|--|
| recall@1 | 42% | 60% | ❌ |
| recall@3 | 64% | 80% | ❌ |
| recall@10 | 86% | 90% | ❌ |
| mrr | 54% | 75% | ❌ |
| deprecated leak | 0% | 0% | ✅ |
| kechikish (median) | 260 ms | — | |
| kechikish (p95) | 312 ms | 600 ms | ✅ |

## Kategoriya bo'yicha (Recall@3)

| Kategoriya | Recall@3 |
|------------|---------:|
| jinoyat | 67% |
| korporativ | 100% |
| majburiyat | 50% |
| mehnat | 50% |
| meros | 100% |
| modda-lookup | 100% |
| muddat | 67% |
| mulk | 50% |
| protsessual | 25% |
| shartnoma | 33% |
| shaxs | 100% |
| zarar | 100% |

## Topilmagan (5)

- `dm-03` — "Sud muddat o'tganini o'zi hisobga oladimi yoki tomon aytishi kerakmi"
  - kutilgan: ['153'], olindi: ['FUQAROLIK KODEKSI:145', 'JINOYAT-PROTSESSUAL KO:314', 'JINOYAT-PROTSESSUAL KO:317']
- `ish-haqi-01` — "Maoshni to'lash tartibi va muddatlari"
  - kutilgan: ['333'], olindi: ['Bojxona kodeksi:333', 'Bojxona kodeksi:327', 'Bojxona kodeksi:329']
- `mshart-01` — 'Ish beruvchi mehnat shartnomasini rasmiylashtirishga majburmi'
  - kutilgan: ['32'], olindi: ['Mehnat kodeksi:25', 'Mehnat kodeksi:125', 'Mehnat kodeksi:128']
- `fpk-01` — "Er-xotinni ajratish to'g'risidagi ishni sud qanday ko'radi"
  - kutilgan: ['185'], olindi: ['OILA KODEKSI:40', 'OILA KODEKSI:44', 'OILA KODEKSI:28']
- `fpk-03` — "Sudga murojaat qilishda qanday to'lovlar bo'ladi"
  - kutilgan: ['127'], olindi: ['Iqtisodiy protsessual:116', 'Fuqarolik protsessual:4', 'Maʼmuriy sud ishlarini:113']