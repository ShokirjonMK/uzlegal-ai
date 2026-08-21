# 29 — Gold set kengaytirish va u ochgan noqulay haqiqat

**Sana:** 2026-08-21
**Manba:** yakuniy tahlil, 4-qadam — «gold set 36 dan ~200 gacha».

---

## 1. Muammo

`retrieval-gold-v1` da 36 holat bor. Bu **±16 p.p.** shovqin degani:
har qanday yaxshilanish statistik jihatdan isbotlanmaydi. Kengaytirish
kerak edi.

---

## 2. Nima qilindi

### 2.1 Ishonch darajasi ochiq yozildi

`GoldCase` ga `verified_by` maydoni qo'shildi va u **yashirilmaydi**:

| Qiymat | Ma'nosi |
|---|---|
| `expert` | Malakali yurist tasdiqlagan |
| `machine` | Avtomatik tekshiruvdan o'tgan |
| `noma'lum` | Eski holatlar — kim yozgani qayd etilmagan |

Diqqat: eski 36 holat `expert` deb **belgilanmadi**. Ularni kim
yozgani hujjatlashtirilmagan va uni faraz qilish yolg'on bo'lardi.

### 2.2 Tekshirgich

`eval/goldset.py` har holatni korpusga solishtiradi:

* savol modda raqamini o'zi aytmasin (aks holda test qidiruvni emas,
  raqam topishni o'lchaydi);
* kutilgan modda korpusda **haqiqatan** bo'lsin;
* `doc_hint` berilgan bo'lsa modda **o'sha hujjatda** bo'lsin.

Tekshirgich darhol foyda berdi. 31 ta yangi holatdan **uchtasi rad
etildi**: men ularni Mehnat kodeksidan deb yozgandim, aslida ular
«Fuqarolarning mehnat huquqlari kafolatlari…» degan **boshqa
hujjatdan** edi. Bu xato gold setga tushsa, u doimiy noto'g'ri
o'lchov bo'lib qolardi.

### 2.3 28 ta yangi holat

Har biri korpusdagi modda matni **o'qib** yozildi: savol shunday
tuzildiki, javob aynan o'sha moddada bo'lsin.

---

## 3. Va shu yerda noqulay natija chiqdi

Kengaytirilgan to'plam (64 holat) o'lchanganda raqamlar keskin
yaxshilandi:

| | 36 holat | 64 holat |
|---|---:|---:|
| R@1 | 42% | 58% |
| R@10 | 86% | **91%** ✅ |

R@10 birinchi marta 90% maqsadiga yetdi. **Bu xulosa noto'g'ri
bo'lardi.**

Ikki guruh alohida o'lchandi:

| Guruh | n | R@1 | R@3 | R@10 | MRR |
|---|---:|---:|---:|---:|---:|
| Eski (`noma'lum`) | 36 | 42% | 64% | 86% | 54% |
| **Yangi (`machine`)** | 28 | **79%** | **89%** | **96%** | **85%** |

Mening holatlarim **deyarli ikki barobar oson**.

### 3.1 Nima uchun

Sabab usulda. Men savolni **modda matnidan** yozdim: matnni o'qib,
undan savol tuzdim. Natijada savol manbadagi so'zlarga yaqin bo'ladi
va qidiruv uni osongina topadi.

Haqiqiy foydalanuvchi esa boshqacha yozadi: u **muammodan** kelib
chiqadi va qonun atamalarini bilmaydi. Eski to'plamdagi
«O'g'irlangan mulkimni egallab olgan odamdan qaytarib olsam
bo'ladimi» savolida `vindikatsiya` so'zi **yo'q** — shuning uchun u
qiyin.

### 3.2 Nima qilindi

Ikki to'plam **ajratildi**:

```
data/eval/retrieval-gold-v1/      36 holat  — ASOS, tegilmaydi
data/eval/retrieval-machine-v1/   28 holat  — mashina yozgan
```

Ularni birlashtirish asosni buzardi: vaqt bo'yicha taqqoslash
imkonsiz bo'lib qolardi va «R@10 91%» degan raqam **shishirilgan**
bo'lardi.

Bu shu loyihada oltinchi marta «e'lon qilingan raqam amaldagi raqam
emas» holati. Bu safar uni **e'lon qilishdan oldin** ushladik.

---

## 4. Machine to'plami nima uchun baribir kerak

U qidiruv sifatini o'lchamaydi — buni yuqoridagi jadval ko'rsatdi.
Lekin u boshqa narsa uchun yaroqli:

| Nima uchun | Izoh |
|---|---|
| **Regressiya nazorati** | Oson holat ham yiqilsa — jiddiy buzilish bor |
| **Qamrov xaritasi** | Qaysi kodekslar test bilan qoplangani ko'rinadi |
| **Chegara holati** | 96% dan pastga tushish signal |

Ya'ni u **pol**, shift emas.

---

## 5. Haqiqiy gold set uchun nima kerak

Savol **muammodan** yozilishi kerak, modda matnidan emas. Buni
ishonchli qilishning ikki yo'li bor va ikkalasi ham mashinada
bajarilmaydi:

| Yo'l | Kim | Baho |
|---|---|---|
| Yurist haqiqiy mijoz savollarini yozadi | yurist | ~20 soat / 100 holat |
| Yopiq sinovdan haqiqiy savollar yig'iladi | foydalanuvchi | R1 bosqichi |

Ikkinchisi arzonroq va tabiiyroq: sinovda odamlar o'z so'zi bilan
so'raydi va o'sha savollar to'plamga aylanadi. Strategiyada R1
bosqichining maqsadi aynan shu deb yozilgan edi.

---

## 6. Ochiq qolgani

| # | Nima | Nega |
|---|---|---|
| **G1** | Haqiqiy gold set 200 holatgacha | Yurist yoki yopiq sinov (§ 5) |
| **G2** | Eski 36 holatning muallifi aniqlansin | Hozir `noma'lum` — ular `expert` bo'lishi mumkin, lekin bu tasdiqlanmagan |
| **G3** | Machine to'plami CI da pol sifatida | 96% dan pastga tushsa — regressiya |
