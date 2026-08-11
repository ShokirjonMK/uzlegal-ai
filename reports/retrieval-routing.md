# Retrieval baholash — gibrid

Holatlar: 36 · reranker: yo‘q

| Metrika | Natija | Maqsad | |
|---------|-------:|-------:|--|
| recall@1 | 42% | 60% | ❌ |
| recall@3 | 67% | 80% | ❌ |
| recall@10 | 89% | 90% | ❌ |
| mrr | 55% | 75% | ❌ |
| deprecated leak | 0% | 0% | ✅ |
| kechikish (median) | 117 ms | — | |
| kechikish (p95) | 187 ms | 600 ms | ✅ |

## Kategoriya bo'yicha (Recall@3)

| Kategoriya | Recall@3 |
|------------|---------:|
| jinoyat | 67% |
| korporativ | 100% |
| majburiyat | 100% |
| mehnat | 50% |
| meros | 100% |
| modda-lookup | 100% |
| muddat | 67% |
| mulk | 50% |
| protsessual | 25% |
| shartnoma | 33% |
| shaxs | 100% |
| zarar | 100% |

## Topilmagan (4)

- `dm-03` — "Sud muddat o'tganini o'zi hisobga oladimi yoki tomon aytishi kerakmi"
  - kutilgan: ['153'], olindi: ['FUQAROLIK KODEKSI:145', 'JINOYAT-PROTSESSUAL KO:314', 'JINOYAT-PROTSESSUAL KO:317']
- `ish-haqi-01` — "Maoshni to'lash tartibi va muddatlari"
  - kutilgan: ['333'], olindi: ['Bojxona kodeksi:333', 'Bojxona kodeksi:327', 'Mehnat kodeksi:253']
- `mshart-01` — 'Ish beruvchi mehnat shartnomasini rasmiylashtirishga majburmi'
  - kutilgan: ['32'], olindi: ['Mehnat kodeksi:25', 'Mehnat kodeksi:125', 'Mehnat kodeksi:128']
- `fpk-01` — "Er-xotinni ajratish to'g'risidagi ishni sud qanday ko'radi"
  - kutilgan: ['185'], olindi: ['OILA KODEKSI:40', 'OILA KODEKSI:44', 'OILA KODEKSI:28']