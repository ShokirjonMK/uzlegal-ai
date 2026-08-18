# Retrieval sifati — to'liq korpusda birinchi o'lchov

**Sana:** 2026-08-13
**Indeks:** `kb/current`, `v2026.08.13` — 792 hujjat · 48 527 bo'lak
**Oldingi o'lchov:** 20 hujjat · 8 636 bo'lak

> ⚠️ **Tuzatish (2026-08-18).** Bu o'lchov paytida indeksda 48 527 emas,
> **35 708** bo'lak qidiruvga kirar edi: takrorlangan `chunk_id` tufayli
> 12 819 bo'lak (26.4%) yuklashda yutilardi va ularning o'rniga boshqa
> bo'lakning matni qaytarilardi. Ya'ni quyidagi barcha metrikalar
> **buzuq indeksda** o'lchangan. Sabab va tuzatish: `docs/23`. Yangi
> asos: `reports/retrieval-2026-08-18.md`.

Bu hisobot `B4` savoliga («qamrov hakami quraymizmi yoki korpusni
kengaytiramizmi») javob beradi. Javob ikkalasi ham emas — va sabab
quyida raqamlar bilan ko'rsatilgan.

---

## 1. Natijalar

| Metrika | Qiymat | Maqsad | 95% ishonch oralig'i |
|---------|--------|--------|----------------------|
| Recall@1 | 42% | 60% | **26 … 58%** |
| Recall@3 | 64% | 80% | 48 … 80% |
| Recall@10 | 86% | 90% | 75 … 97% |
| MRR | 54% | 75% | 38 … 70% |
| Bekor qilingan norma sizishi | **0%** | 0% | ✅ |
| Kechikish | 264 ms median · 453 ms p95 | — | ✅ |

Korpus 40 barobar kattalashdi, sifat esa deyarli o'zgarmadi
(ilgari R@1 42%, R@10 89%). Bu **yomon xabar emas**: 40 barobar ko'p
chalg'ituvchi hujjat qo'shilganda sifatni ushlab turishning o'zi
natija. Lekin kutilgan sakrash ham bo'lmadi.

---

## 2. Nosozliklar qayerda

36 holatning har biri top-10 bo'yicha tasniflandi:

| Turi | Soni | Ulush |
|------|------|-------|
| 1-o'rinda to'g'ri | 15 | 42% |
| top-10 da bor, lekin 1-o'rinda emas | 16 | **44%** |
| Modda raqami to'g'ri, kodeks noto'g'ri | 1 | 3% |
| Top-10 da umuman yo'q | 4 | 11% |

**Asosiy xulosa: bu qamrov muammosi emas.** 86% holatda to'g'ri
javob allaqachon topilgan — u shunchaki yetarlicha yuqorida turmaydi.
Korpusni yana kengaytirish bu 44% ga ta'sir qilmaydi.

### Kanallar bo'yicha tahlil

Ikkita xarakterli nosozlik ochib ko'rildi:

| Holat | Vektor | Leksik (kengaygan) | Yakuniy |
|-------|--------|--------------------|---------|
| `tatil-01` | 26-o'rin | **1-o'rin** | 8-o'rin |
| `vind-01` | topmadi | **1-o'rin** | 10-o'rin |

Kengaytirilgan leksik qidiruv to'g'ri moddani **birinchi o'ringa**
qo'yadi, lekin `w_lex = 0.2` uni pastga suradi.

Diqqat: so'rovni kengaytirish **ishlayapti**. Tezaurus
«maosh → ish haqi», «dam olish → ta'til», «o'g'irlangan mulkni
qaytarish → vindikatsiya» ni to'g'ri chiqaradi. Muammo lug'atda emas,
kanallarni birlashtirishda.

---

## 3. Uchta yechim sinab ko'rildi — uchalasi ham ish bermadi

### 3.1 Reranker (`bge-reranker-v2-m3`)

| Metrika | Rerankersiz | Reranker bilan |
|---------|-------------|----------------|
| Recall@1 | 42% | **50%** |
| Recall@10 | **86%** | 78% |
| Kechikish | **264 ms** | 1 335 ms |

Bir xil savdo: 1-o'rinda yutadi, 10-o'rinda yutqazadi, 5 barobar
sekinlashadi. Bu eski indeksdagi natijani takrorlaydi (42→47% va
89→81%) — ya'ni xulosa korpusga bog'liq emas.

### 3.2 Og'irliklarni qayta sozlash

`w_lex` 0.2 dan 0.8 gacha o'lchandi:

| w_vec / w_lex | R@1 | R@3 | R@10 | MRR |
|---------------|-----|-----|------|-----|
| **0.8 / 0.2** (hozirgi) | 42% | 64% | **86%** | 54% |
| 0.5 / 0.5 | **47%** | **69%** | 78% | **58%** |
| 0.3 / 0.7 | 25% | 58% | 75% | 42% |

Hozirgi qiymat R@1 va R@10 yig'indisi bo'yicha allaqachon eng yaxshi.
0.5/0.5 MRR ni ko'taradi, lekin yana o'sha savdo.

### 3.3 Korpusni kengaytirish

Nosozliklarning atigi **11%** i qamrov bilan bog'liq. Yana ming
hujjat qo'shish bu 4 holatning bir qismini yopishi mumkin, qolgan
44% ga esa ta'sir qilmaydi.

---

## 4. Nima uchun bularning hech biri ishonchli emas

36 ta holatda **bitta holat = 2.8 foiz punkti**.

| «Yaxshilanish» | Aslida |
|----------------|--------|
| Reranker: R@1 +8 p.p. | **3 ta holat** |
| Og'irlik: R@1 +5 p.p. | **2 ta holat** |

`R@1 = 42%` ning 95% ishonch oralig'i — **26% dan 58% gacha**. Ya'ni
haqiqiy qiymat 26% ham, 58% ham bo'lishi mumkin. Bu oraliqqa yuqoridagi
barcha variantlar bemalol sig'adi.

10 foiz punktlik farqni ishonch bilan ajratish uchun **~390 ta holat**
kerak. Bizda 36 ta bor.

**Ya'ni hozirgi to'plamda men qaysi variantni tanlasam ham, uni
tasodifdan ajrata olmayman.** 0.5/0.5 ni tanlab «R@1 47% ga chiqdi»
deb yozish mumkin edi — bu chiroyli ko'rinardi va asossiz bo'lardi.

---

## 5. Qaror (B4)

**Optimizatsiya emas, avval o'lchov asbobini tuzatish.**

Sabab oddiy: buzilgan tarozida ovqat pishirib bo'lmaydi. Retrieval
ustida ishlashdan oldin uni o'lchay olish kerak.

### Keyingi qadamlar, tartib bilan

1. **Gold to'plamni 36 → 150+ holatga kengaytirish.**
   Bunda 1 holat = 0.7 p.p. bo'ladi va ±6 p.p. aniqlik beradi —
   haqiqiy yaxshilanishni shovqindan ajratish uchun yetarli.
   Holatlar korpusdan avtomatik yaratilmasin: bu doiraviy bo'ladi
   (tizim o'zi topa oladigan narsani o'zi tekshiradi). Ular haqiqiy
   savollardan olinishi va yurist tomonidan tasdiqlanishi kerak.

2. **Shundan keyin** yuqoridagi uchta variantni qayta o'lchash.
   Kod tayyor, o'lchov bir buyruq: `uzlegal eval retrieval [--rerank]`.

3. `mshart-01` va `ish-haqi-01` alohida tekshirilsin — ular hech bir
   kanalda top-100 ga tushmadi. Bu yo korpusda hujjat yo'qligini, yo
   gold to'plamdagi xatoni bildiradi.

### Nima o'zgartirilmadi va nega

| Narsa | Holat | Sabab |
|-------|-------|-------|
| `use_reranker` | `false` (o'zgarmadi) | R@10 ni tushiradi, 5× sekin |
| `WEIGHTS` | `0.8 / 0.2` (o'zgarmadi) | Allaqachon optimal, farqlar shovqin ichida |
| Tezaurus | o'zgarmadi | Ishlayapti — muammo boshqa joyda |

O'zgartirmaslik ham qaror. Uni hujjatlashtirish shuning uchun kerakki,
keyingi safar bu savol yana ko'tarilganda o'lchov qaytadan
o'tkazilmasin.

---

## 6. Ijobiy natijalar

- **Bekor qilingan norma sizishi — 0%.** Bu yuridik tizim uchun
  eng muhim xavfsizlik ko'rsatkichi va u to'liq korpusda ham saqlandi.
- **Kechikish 264 ms median** — 35 708 bo'lakli indeksda (yuqoridagi
  tuzatishga qarang). Foydalanuvchi uchun sezilmaydi.
- Tirik sinovda uchala savol ham to'g'ri kodeks, to'g'ri modda va
  to'g'ri `lex.uz` havolasini qaytardi.
