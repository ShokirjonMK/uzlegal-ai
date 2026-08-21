# Retrieval baholash — gibrid

Holatlar: 64 · reranker: yo‘q

| Metrika | Natija | Maqsad | |
|---------|-------:|-------:|--|
| recall@1 | 58% | 60% | ❌ |
| recall@3 | 75% | 80% | ❌ |
| recall@10 | 91% | 90% | ✅ |
| mrr | 68% | 75% | ❌ |
| deprecated leak | 0% | 0% | ✅ |
| kechikish (median) | 274 ms | — | |
| kechikish (p95) | 365 ms | 600 ms | ✅ |

## Kategoriya bo'yicha (Recall@3)

| Kategoriya | Recall@3 |
|------------|---------:|
| himoya | 50% |
| jinoyat | 78% |
| korporativ | 100% |
| majburiyat | 75% |
| mehnat | 67% |
| meros | 100% |
| modda-lookup | 100% |
| muddat | 80% |
| mulk | 33% |
| oila | 100% |
| protsessual | 25% |
| shartnoma | 50% |
| shaxs | 100% |
| zarar | 100% |

## Topilmagan (6)

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
- `fk-10` — 'Mulkimni qonunsiz egallab olgan shaxsdan qaytarib olishim mumkinmi'
  - kutilgan: ['228'], olindi: ['FUQAROLIK KODEKSI:1023', 'FUQAROLIK KODEKSI:230', 'JINOYAT-PROTSESSUAL KO:287']