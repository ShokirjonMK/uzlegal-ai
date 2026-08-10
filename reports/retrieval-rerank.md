# Retrieval baholash — reranker

Holatlar: 36 · reranker: yoqilgan

| Metrika | Natija | Maqsad | |
|---------|-------:|-------:|--|
| recall@1 | 31% | 60% | ❌ |
| recall@3 | 42% | 80% | ❌ |
| recall@10 | 56% | 90% | ❌ |
| mrr | 38% | 75% | ❌ |
| deprecated leak | 0% | 0% | ✅ |
| kechikish (median) | 11510 ms | — | |
| kechikish (p95) | 15311 ms | 600 ms | ❌ |

## Kategoriya bo'yicha (Recall@3)

| Kategoriya | Recall@3 |
|------------|---------:|
| jinoyat | 100% |
| korporativ | 0% |
| majburiyat | 0% |
| mehnat | 25% |
| meros | 50% |
| modda-lookup | 100% |
| muddat | 33% |
| mulk | 50% |
| protsessual | 0% |
| shartnoma | 33% |
| shaxs | 50% |
| zarar | 100% |

## Topilmagan (16)

- `vind-01` — "O'g'irlangan mulkimni egallab olgan odamdan qaytarib olsam bo'ladimi"
  - kutilgan: ['228'], olindi: ['OʻZBEKISTON RESPUB:1023', 'OʻZBEKISTON RESPUB:1026', 'OʻZBEKISTON RESPUB:229']
- `dm-03` — "Sud muddat o'tganini o'zi hisobga oladimi yoki tomon aytishi kerakmi"
  - kutilgan: ['153'], olindi: ['OʻZBEKISTON RESPUB:314', 'OʻZBEKISTON RESPUB:317', 'OʻZBEKISTON RESPUB:145']
- `sinov-01` — "Yangi xodimni tekshirib ko'rish uchun qancha vaqt belgilash mumkin"
  - kutilgan: ['130', '131', '130-131'], olindi: ['Oʻzbekiston Respub:147', 'Oʻzbekiston Respub:137', 'Oʻzbekiston Respub:364']
- `bosh-01` — "Ishdan bo'shatishni kim rasmiylashtiradi"
  - kutilgan: ['170'], olindi: ['Oʻzbekiston Respub:153', 'Oʻzbekiston Respub:166', 'Oʻzbekiston Respub:309']
- `tatil-01` — 'Xodimga yiliga necha kun dam olish beriladi'
  - kutilgan: ['216', '217'], olindi: ['Oʻzbekiston Respub:207', 'Oʻzbekiston Respub:283', 'Oʻzbekiston Respub:204']
- `ish-haqi-01` — "Maoshni to'lash tartibi va muddatlari"
  - kutilgan: ['333'], olindi: ['Oʻzbekiston Respub:101', 'Oʻzbekiston Respub:327', 'Oʻzbekiston Respub:329']
- `mshart-01` — 'Ish beruvchi mehnat shartnomasini rasmiylashtirishga majburmi'
  - kutilgan: ['32'], olindi: ['Oʻzbekiston Respub:128', 'Oʻzbekiston Respub:149', 'Oʻzbekiston Respub:5']
- `yur-02` — 'Yuridik shaxs deb nima tushuniladi'
  - kutilgan: ['39'], olindi: ['Oʻzbekiston Respub:38', 'OʻZBEKISTON RESPUB:989', 'OʻZBEKISTON RESPUB:48']
- `voyaga-01` — "O'n olti yoshli o'smir o'zi bitim tuza oladimi"
  - kutilgan: ['27'], olindi: ['OʻZBEKISTON RESPUB:29', 'OʻZBEKISTON RESPUB:117', 'OʻZBEKISTON RESPUB:118']
- `garov-01` — "Qarzni ta'minlash uchun mulkni ta'minot sifatida berish"
  - kutilgan: ['264'], olindi: ['Oʻzbekiston Respub:106', 'OʻZBEKISTON RESPUB:516', 'Oʻzbekiston Respub:106']
- `majb-01` — 'Majburiyat deganda nima tushuniladi'
  - kutilgan: ['234'], olindi: ['OʻZBEKISTON RESPUB:235', 'Oʻzbekiston Respub:5', 'Oʻzbekiston Respub:301']
- `sotuv-01` — 'Mol sotish va sotib olish kelishuvi'
  - kutilgan: ['386'], olindi: ['OʻZBEKISTON RESPUB:281', 'OʻZBEKISTON RESPUB:556', 'OʻZBEKISTON RESPUB:391']
- `bekor-01` — 'Shartnoma buzilganda zarar qanday hisoblanadi'
  - kutilgan: ['456'], olindi: ['OʻZBEKISTON RESPUB:382', 'OʻZBEKISTON RESPUB:918', 'OʻZBEKISTON RESPUB:383']
- `meros-02` — "Vasiyatda ko'rsatilmagan mol-mulk kimga o'tadi"
  - kutilgan: ['1123'], olindi: ['OʻZBEKISTON RESPUB:1157', 'OʻZBEKISTON RESPUB:184', 'OʻZBEKISTON RESPUB:196']
- `fpk-01` — "Er-xotinni ajratish to'g'risidagi ishni sud qanday ko'radi"
  - kutilgan: ['185'], olindi: ['OʻZBEKISTON RESPUB:40', 'OʻZBEKISTON RESPUB:44', 'OʻZBEKISTON RESPUB:41']
- `fpk-03` — "Sudga murojaat qilishda qanday to'lovlar bo'ladi"
  - kutilgan: ['127'], olindi: ['Oʻzbekiston Respub:139', 'Oʻzbekiston Respub:5', 'Oʻzbekiston Respub:4']