# AI Lawyer — ish qoidalari

Bu fayl loyiha ustida ishlashning majburiy tartibini belgilaydi.
Har bir topshiriq shu qoidalarga muvofiq bajariladi.

---

## 1. Har bir topshiriq raqamlanadi

- Raqamlar `docs/TASKS.md` faylida ketma-ket yuritiladi: `#1`, `#2`, `#3`…
- Kichik qadamlar ota-topshiriq raqamiga bogʻlanadi: `#8.1`, `#8.2`.
- Topshiriq **yopilmaydi**, toki QA bosqichidan oʻtmaguncha.
- Har bir topshiriqning holati `docs/TASKS.md` da yangilab boriladi:
  `reja` → `bajarilmoqda` → `testda` → `qaytarildi` → `yopildi`.

---

## 2. Rollar va jarayon

Har bir topshiriq quyidagi zanjirdan oʻtadi. Bosqichni oʻtkazib yuborish mumkin emas.

```
Topshiriq
   │
   ▼
① SENIOR PM ── tahlil qiladi, boʻladi, rejalashtiradi
   │           📤 TG: "pm-start" hisoboti
   ▼
② SENIOR DEVELOPER(lar) ── bajaradi (bir nechta boʻlishi mumkin, parallel)
   │           📤 TG: "dev" hisoboti (uzoq ishlarda)
   ▼
③ SENIOR QA ── toʻliq test qiladi
   │
   ├── ❌ oʻtmadi → 📤 TG: "qa-fail" → ② ga qaytadi
   │
   └── ✅ oʻtdi   → 📤 TG: "qa"
   │
   ▼
④ SENIOR PM ── yakuniy hisobot yozadi
               📤 TG: "pm-done"
```

### ① Senior PM — topshiriqni qabul qilish

Topshiriq kelganda **darhol**, ishni boshlashdan oldin:

1. Topshiriqni qanday tushunganini oʻz soʻzi bilan qayta bayon qiladi.
2. Kichik qadamlarga boʻladi va raqamlaydi.
3. Xavflarni, nomaʼlum joylarni va foydalanuvchidan kutilayotgan narsalarni
   aniq sanab oʻtadi.
4. `docs/TASKS.md` ga yozadi.
5. TG ga `pm-start` hisobotini yuboradi.

### ② Senior Developer

- Bir nechta mustaqil qadam boʻlsa, ular parallel bajariladi.
- Har bir qadam yakunlanganda `docs/TASKS.md` yangilanadi.
- Kod yozilgandan keyin QA ga oʻtkaziladi — oʻzini oʻzi tasdiqlamaydi.

### ③ Senior QA — toʻliq test

Majburiy minimum (hammasi bajarilishi shart):

```bash
npm run check      # typecheck + oʻzbek matni linteri
npm run build      # build buzilmaganini tekshirish
```

Bundan tashqari, oʻzgarish turiga qarab:

| Nima oʻzgardi | Qanday tekshiriladi |
|---|---|
| API marshrut | Server ishga tushiriladi, `curl` bilan haqiqiy soʻrov yuboriladi |
| Web sahifa | Sahifa 200 qaytarishi va asosiy oqim ishlashi tekshiriladi |
| `src/lib/uz/` | Kod nuqtalari (U+02BB / U+02BC) darajasida tekshiriladi |
| RAG | Namuna soʻrov bilan qidiruv natijasi koʻzdan kechiriladi |
| Telegram bot | `getMe` va haqiqiy xabar yuborish bilan tekshiriladi |
| CLI | Buyruq haqiqatan ishga tushirilib koʻriladi |

**QA oʻtmasa** — topshiriq `qaytarildi` holatiga oʻtadi, TG ga `qa-fail`
yuboriladi va ② bosqichga qaytadi. Yopilmaydi.

### ④ Senior PM — yakuniy hisobot

- Nima qilindi (raqamlar boʻyicha).
- Nima tekshirildi va natija.
- Nima qilinmadi va nima uchun.
- Foydalanuvchidan nima kutilmoqda.

---

## 3. Telegram hisobotlari

Kanal: `ADMIN_CHAT_ID` (hozirgi qiymat `.env.local` da).

```bash
npm run report -- --kind pm-start --id 8 --title "Sarlavha" --body "Matn"
npm run report -- --kind dev      --id 8 --title "Sarlavha" --body "Matn"
npm run report -- --kind qa       --id 8 --title "Sarlavha" --body "Matn" --status "oʻtdi"
npm run report -- --kind qa-fail  --id 8 --title "Sarlavha" --body "Sabab"
npm run report -- --kind pm-done  --id 8 --title "Sarlavha" --body "Matn" --status "yopildi"

# Uzun matnni quvur orqali:
cat hisobot.txt | npm run report -- --kind pm-done --id 8 --title "Sarlavha"
```

**Majburiy hisobotlar:** `pm-start` (topshiriq boshida) va `pm-done` (yakunda).
`dev`, `qa`, `qa-fail` — bosqich uzoq davom etsa yoki test oʻtmasa.

Hisobot yuborilmasa ish tugallangan hisoblanmaydi.

---

## 4. Kod yozish qoidalari

- **Til:** barcha izohlar, xato xabarlari va UI matni — **oʻzbek tilida**.
  Kod identifikatorlari ingliz tilida (odatiy amaliyot).
- **Apostrof:** foydalanuvchiga koʻrinadigan har qanday matnda `oʻ`/`gʻ` uchun
  U+02BB (`ʻ`), tutuq belgisi uchun U+02BC (`ʼ`). ASCII `'` ishlatilmaydi.
  `npm run lint:uz` buni tekshiradi.
- **Aralash yozuv taqiqlanadi:** bitta soʻzda lotin va kirill harflari
  boʻlmasligi kerak (`terminалда` kabi). Linter tutadi. <!-- lint-uz-ignore: ataylab yomon misol -->
- Ataylab qilingan istisno uchun: `// lint-uz-ignore` (keyingi satrga taʼsir qiladi).
- **Yangi kutubxona qoʻshishdan oldin** — haqiqatan zarurmi, oʻylab koʻriladi.
- **Maxfiy maʼlumot** hech qachon kodga yozilmaydi. Faqat `.env.local`.

---

## 5. Model bilan ishlash

- Model: `claude-opus-5` (`AI_LOWYER_MODEL` orqali oʻzgartiriladi).
- `temperature`, `top_p`, `top_k`, `budget_tokens` **ishlatilmaydi** — bu model
  ularni qabul qilmaydi (400 xatosi). Chuqurlik `output_config.effort` bilan.
- Rad javobi (`stop_reason: "refusal"`) `content` ni oʻqishdan **oldin**
  tekshiriladi.
- Uzun chiqish kutilsa — streaming.
- Tizim promptining barqaror qismi keshlanadi; oʻzgaruvchan qism keyin turadi.

---

## 6. Nima qilinmaydi

- Foydalanuvchi soʻramagan holda tashqi xizmatga hech narsa yuborilmaydi
  (git push, deploy, ommaviy xabar).
- Qonun moddalari oʻylab topilmaydi. Baza boʻsh boʻlsa — buni ochiq aytiladi.
- Test oʻtmagan ish "tayyor" deb hisobot qilinmaydi.
