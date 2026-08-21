# Retrieval baholash — reranker

Holatlar: 36 · reranker: yoqilgan

| Metrika | Natija | Maqsad | |
|---------|-------:|-------:|--|
| recall@1 | 50% | 60% | ❌ |
| recall@3 | 64% | 80% | ❌ |
| recall@10 | 78% | 90% | ❌ |
| mrr | 59% | 75% | ❌ |
| deprecated leak | 0% | 0% | ✅ |
| kechikish (median) | 1353 ms | — | |
| kechikish (p95) | 1740 ms | 600 ms | ❌ |

## Kategoriya bo'yicha (Recall@3)

| Kategoriya | Recall@3 |
|------------|---------:|
| jinoyat | 100% |
| korporativ | 100% |
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

## Topilmagan (8)

- `vind-01` — "O'g'irlangan mulkimni egallab olgan odamdan qaytarib olsam bo'ladimi"
  - kutilgan: ['228'], olindi: ['FUQAROLIK KODEKSI:1023', 'FUQAROLIK KODEKSI:1026', 'FUQAROLIK KODEKSI:229']
- `tatil-01` — 'Xodimga yiliga necha kun dam olish beriladi'
  - kutilgan: ['216', '217'], olindi: ['Mehnat kodeksi:207', 'Mehnat kodeksi:283', 'Sud hujjatlari va bosh:7']
- `ish-haqi-01` — "Maoshni to'lash tartibi va muddatlari"
  - kutilgan: ['333'], olindi: ['Soliq kodeksi:101', 'Bojxona kodeksi:327', 'Bojxona kodeksi:329']
- `mshart-01` — 'Ish beruvchi mehnat shartnomasini rasmiylashtirishga majburmi'
  - kutilgan: ['32'], olindi: ['Mehnat kodeksi:128', 'Mehnat kodeksi:170', 'Mehnat kodeksi:149']
- `sotuv-01` — 'Mol sotish va sotib olish kelishuvi'
  - kutilgan: ['386'], olindi: ['FUQAROLIK KODEKSI:281', 'FUQAROLIK KODEKSI:556', 'Kreditorlarning garov:29']
- `fpk-01` — "Er-xotinni ajratish to'g'risidagi ishni sud qanday ko'radi"
  - kutilgan: ['185'], olindi: ['OILA KODEKSI:40', 'OILA KODEKSI:44', 'OILA KODEKSI:25']
- `fpk-02` — "Bola uchun to'lov undirish bo'yicha sud ishi"
  - kutilgan: ['186', '187'], olindi: ['OILA KODEKSI:147', 'OILA KODEKSI:107', 'OILA KODEKSI:99']
- `fpk-03` — "Sudga murojaat qilishda qanday to'lovlar bo'ladi"
  - kutilgan: ['127'], olindi: ['Iqtisodiy protsessual:139', 'Oʻzbekiston Respublika:26', 'Fuqarolik ishlari boʻy:5']