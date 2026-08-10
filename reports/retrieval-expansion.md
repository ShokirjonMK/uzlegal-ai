# Retrieval baholash — gibrid

Holatlar: 36 · reranker: yo‘q

| Metrika | Natija | Maqsad | |
|---------|-------:|-------:|--|
| recall@1 | 36% | 60% | ❌ |
| recall@3 | 56% | 80% | ❌ |
| recall@10 | 69% | 90% | ❌ |
| mrr | 47% | 75% | ❌ |
| deprecated leak | 0% | 0% | ✅ |
| kechikish (median) | 101 ms | — | |
| kechikish (p95) | 153 ms | 600 ms | ✅ |

## Kategoriya bo'yicha (Recall@3)

| Kategoriya | Recall@3 |
|------------|---------:|
| jinoyat | 67% |
| korporativ | 50% |
| majburiyat | 0% |
| mehnat | 50% |
| meros | 50% |
| modda-lookup | 100% |
| muddat | 67% |
| mulk | 50% |
| protsessual | 25% |
| shartnoma | 33% |
| shaxs | 100% |
| zarar | 100% |

## Topilmagan (11)

- `vind-01` — "O'g'irlangan mulkimni egallab olgan odamdan qaytarib olsam bo'ladimi"
  - kutilgan: ['228'], olindi: ['FUQAROLIK KODEKSI:1023', 'FUQAROLIK KODEKSI:278', 'FUQAROLIK KODEKSI:193']
- `sinov-01` — "Yangi xodimni tekshirib ko'rish uchun qancha vaqt belgilash mumkin"
  - kutilgan: ['130', '131', '130-131'], olindi: ['Mehnat kodeksi:141', 'Mehnat kodeksi:147', 'Mehnat kodeksi:139']
- `ish-haqi-01` — "Maoshni to'lash tartibi va muddatlari"
  - kutilgan: ['333'], olindi: ['Mehnat kodeksi:253', 'Bojxona kodeksi:327', 'Bojxona kodeksi:333']
- `mshart-01` — 'Ish beruvchi mehnat shartnomasini rasmiylashtirishga majburmi'
  - kutilgan: ['32'], olindi: ['Mehnat kodeksi:128', 'Mehnat kodeksi:125', 'Mehnat kodeksi:506']
- `yur-02` — 'Yuridik shaxs deb nima tushuniladi'
  - kutilgan: ['39'], olindi: ['Soliq kodeksi:38', 'Bojxona kodeksi:307', 'FUQAROLIK KODEKSI:57']
- `garov-01` — "Qarzni ta'minlash uchun mulkni ta'minot sifatida berish"
  - kutilgan: ['264'], olindi: ['FUQAROLIK KODEKSI:742', 'FUQAROLIK KODEKSI:732', 'Budjet kodeksi:155']
- `majb-01` — 'Majburiyat deganda nima tushuniladi'
  - kutilgan: ['234'], olindi: ['FUQAROLIK KODEKSI:235', 'Mehnat kodeksi:5', 'HAVO KODEKSI:54']
- `bekor-01` — 'Shartnoma buzilganda zarar qanday hisoblanadi'
  - kutilgan: ['456'], olindi: ['FUQAROLIK KODEKSI:14', 'Mehnat kodeksi:345', 'FUQAROLIK KODEKSI:355']
- `fpk-01` — "Er-xotinni ajratish to'g'risidagi ishni sud qanday ko'radi"
  - kutilgan: ['185'], olindi: ['OILA KODEKSI:44', 'OILA KODEKSI:40', 'OILA KODEKSI:28']
- `fpk-02` — "Bola uchun to'lov undirish bo'yicha sud ishi"
  - kutilgan: ['186', '187'], olindi: ['OILA KODEKSI:107', 'OILA KODEKSI:99', 'OILA KODEKSI:147']
- `fpk-03` — "Sudga murojaat qilishda qanday to'lovlar bo'ladi"
  - kutilgan: ['127'], olindi: ['Fuqarolik protsessual:4', 'Iqtisodiy protsessual:139', 'Iqtisodiy protsessual:3']