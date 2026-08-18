# Retrieval baholash — gibrid

**Sana:** 2026-08-18
**Indeks:** `kb/current` — 792 hujjat · **48 527 noyob bo'lak**
**Oldingi o'lchov:** `reports/retrieval-2026-08-13.md` — o'sha paytdagi
indeksda amalda 35 708 bo'lak bor edi (`docs/23`).

> **Sifat metrikalari o'zgarmadi** (R@1 42%, R@3 64%, R@10 86%, MRR 54%
> — uchala raqam ham 13-avgustdagi bilan bir xil). Bu kutilgan
> natija va u tuzatish keraksiz edi degani **emas**.
>
> Sabab: baholash `case.matches(chunk)` orqali **modda raqami va
> hujjatni** tekshiradi, ko'rsatilgan **matnni** emas. Almashtirish
> esa deyarli har doim bir moddaning ichida sodir bo'lardi —
> 4 484 takror guruhning atigi **6 tasida** nusxalarning `article`
> maydoni farq qilgan (`docs/23 § 5.2`). Ya'ni bu to'plam shu turdagi
> nuqsonni **printsipial ravishda ko'rmaydi**: iqtibos to'g'ri moddaga
> ishora qilardi, matn esa o'sha moddaning boshqa bandidan olingandi.
>
> Kechikish 264 → 473 ms ga oshdi. Sabab ham shu tuzatish: indeksda
> qidiriladigan bo'lak soni 35 708 → 48 527 (+36%), BM25 esa
> Python'da chiziqli o'tadi. Bu yo'qotish emas — ilgari o'sha
> bo'laklar ham qidirilardi, faqat natijasi noto'g'ri chiqardi.

Holatlar: 36 · reranker: yo‘q

| Metrika | Natija | Maqsad | |
|---------|-------:|-------:|--|
| recall@1 | 42% | 60% | ❌ |
| recall@3 | 64% | 80% | ❌ |
| recall@10 | 86% | 90% | ❌ |
| mrr | 54% | 75% | ❌ |
| deprecated leak | 0% | 0% | ✅ |
| kechikish (median) | 473 ms | — | |
| kechikish (p95) | 740 ms | 600 ms | ❌ |

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