# Retrieval baholash — reranker

Holatlar: 36 · reranker: yoqilgan

| Metrika | Natija | Maqsad | |
|---------|-------:|-------:|--|
| recall@1 | 47% | 60% | ❌ |
| recall@3 | 61% | 80% | ❌ |
| recall@10 | 81% | 90% | ❌ |
| mrr | 58% | 75% | ❌ |
| deprecated leak | 0% | 0% | ✅ |
| kechikish (median) | 32044 ms | — | |
| kechikish (p95) | 41185 ms | 600 ms | ❌ |

## Kategoriya bo'yicha (Recall@3)

| Kategoriya | Recall@3 |
|------------|---------:|
| jinoyat | 100% |
| korporativ | 50% |
| majburiyat | 100% |
| mehnat | 38% |
| meros | 100% |
| modda-lookup | 100% |
| muddat | 33% |
| mulk | 50% |
| protsessual | 0% |
| shartnoma | 67% |
| shaxs | 100% |
| zarar | 100% |

## Topilmagan (7)

- `vind-01` — "O'g'irlangan mulkimni egallab olgan odamdan qaytarib olsam bo'ladimi"
  - kutilgan: ['228'], olindi: ['FUQAROLIK KODEKSI:1023', 'FUQAROLIK KODEKSI:1026', 'FUQAROLIK KODEKSI:229']
- `tatil-01` — 'Xodimga yiliga necha kun dam olish beriladi'
  - kutilgan: ['216', '217'], olindi: ['Mehnat kodeksi:207', 'Mehnat kodeksi:283', 'Mehnat kodeksi:204']
- `ish-haqi-01` — "Maoshni to'lash tartibi va muddatlari"
  - kutilgan: ['333'], olindi: ['Soliq kodeksi:101', 'Bojxona kodeksi:327', 'Bojxona kodeksi:329']
- `mshart-01` — 'Ish beruvchi mehnat shartnomasini rasmiylashtirishga majburmi'
  - kutilgan: ['32'], olindi: ['Mehnat kodeksi:128', 'Mehnat kodeksi:170', 'Mehnat kodeksi:149']
- `fpk-01` — "Er-xotinni ajratish to'g'risidagi ishni sud qanday ko'radi"
  - kutilgan: ['185'], olindi: ['OILA KODEKSI:40', 'OILA KODEKSI:44', 'OILA KODEKSI:41']
- `fpk-02` — "Bola uchun to'lov undirish bo'yicha sud ishi"
  - kutilgan: ['186', '187'], olindi: ['OILA KODEKSI:147', 'OILA KODEKSI:107', 'OILA KODEKSI:99']
- `fpk-03` — "Sudga murojaat qilishda qanday to'lovlar bo'ladi"
  - kutilgan: ['127'], olindi: ['Iqtisodiy protsessual:139', 'Maʼmuriy sud ishlarini:5', 'Fuqarolik protsessual:4']