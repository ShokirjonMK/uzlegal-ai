# ADR-002: Noldan pretraining emas, domenga moslashtirish

**Holat:** ✅ Qabul qilindi
**Sana:** 2026-08-08

## Kontekst

Dastlabki talab: "yangi AI model yaratamiz, yuridik sohada idealniy ishlaydigan". Bu ikki xil texnik yo'l bilan tushunilishi mumkin va ular narx/natija bo'yicha keskin farq qiladi.

Mavjud resurslar: MacBook Air M4 24 GB, bitta muhandis, ~5 oy.

## Ko'rib chiqilgan variantlar

### A — Noldan pretraining (foundation model)

| Talab | Qiymat |
|-------|--------|
| Trening ma'lumoti | 10¹²–10¹³ token |
| Mavjud o'zbek sifatli matn | ~10⁹ token (3–4 daraja kam) |
| GPU hisob-kitobi | ~10⁵ A100-soat |
| Xarajat | $0.5–2M |
| Vaqt | 6–12 oy |
| Kutilgan natija | **Zaif** — ma'lumot yetishmasligi tufayli til ham, mantiq ham past |

### B — Continued Pretraining (CPT) + SFT + LoRA + RAG

| Talab | Qiymat |
|-------|--------|
| Trening ma'lumoti | ~300M token CPT + ~46k SFT namuna |
| GPU | Local M4 yoki ~$50 bulut |
| Vaqt | 4–5 oy (asosan ma'lumot tayyorlash) |
| Kutilgan natija | **Kuchli** — kuchli bazaning umumiy qobiliyati + domen chuqurligi |

### C — Faqat prompt engineering (moslashtirishsiz)

| Talab | Qiymat |
|-------|--------|
| Vaqt | 2 hafta |
| Natija | RAG bilan ~65% aniqlik, rol uslublari zaif, o'zbek yuridik tili g'aliz |

## Qaror

**Variant B tanlandi.**

Asosiy sabab: o'zbek tilida foundation model o'qitish uchun **yetarli matn mavjud emas**. 10⁹ token ustida o'qitilgan model 10¹³ token ustida o'qitilgan modeldan har jihatdan yomonroq bo'ladi — hatto o'zbek tilida ham, chunki zamonaviy ko'p tilli modellar til qobiliyatini boshqa tillardan transfer qiladi.

Muhandislik nuqtai nazaridan: **cheklangan ma'lumotni kuchli modelga qo'shish** har doim **cheklangan ma'lumotdan zaif model qurish** dan yaxshiroq.

### Nima "sizning modelingiz" qiladi

Variant B natijasi baribir o'ziga xos model:

| Element | Sizniki |
|---------|---------|
| Trening ma'lumoti | ✅ Sizning yuridik korpusingiz |
| Rol adapterlari | ✅ Sizning 5 ta rolingiz |
| Bilim bazasi | ✅ Sizning KB |
| Sozlash va baholash | ✅ Sizning gold set |
| Baza vaznlar | ❌ Ochiq model (Apache-2.0) |

Bu — hozirgi kunda **barcha jiddiy domen-maxsus AI mahsulotlari** (tibbiyot, moliya, huquq) qanday quriladigan usul.

## Oqibatlari

### Ijobiy
- Loyiha mavjud resurslar bilan real bajariladi
- Baza modelning umumiy qobiliyati saqlanadi (mantiq, ko'p tillilik, ko'rsatmaga rioya)
- Har bir bosqich mustaqil takomillashtiriladi (RAG → SFT → LoRA)
- Baza modelni kelajakda yangisiga almashtirish mumkin (adapterlarni qayta o'qitib)

### Salbiy
- Baza model litsenziyasiga bog'liqlik
- Baza modelning ichki bias'lari meros qoladi
- "Butunlay noldan yaratdik" degan marketing da'vosi qilinmaydi

### Yumshatish
Litsenziya bog'liqligi: Apache-2.0 modellarga ustunlik beriladi ([ADR-001](ADR-001-base-model.md)), bu tijoriy foydalanishni cheklamaydi.

## CPT bo'yicha shartli qaror

CPT (Continued Pretraining) **shartli** — faqat quyidagi holda bajariladi:

> Faza 0 baholashida baza modelning o'zbek tili balli **< 3.5/5**

Sabab: CPT qimmat (+2 hafta, catastrophic forgetting xavfi) va agar model allaqachon o'zbek tilida ravon bo'lsa — keraksiz. Qaror ma'lumotga asoslanadi, taxminga emas.
