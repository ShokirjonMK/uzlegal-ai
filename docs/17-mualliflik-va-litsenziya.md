# 17 — Mualliflik himoyasi va foydalanish litsenziyasi

**Sana:** 2026-08-12 · **Holat:** texnik qism tayyor, **huquqiy qism qaror kutmoqda**

---

## 1. Maqsad

Repo egasining talabi:

> Mualliflik huquqlari va kodni kimdir olib ishga tushurib yuborishi va
> hokazolarni oldini olish. API'larda signature qo'yish (`X-Developer`,
> `X-Author`), CLI va boshqalarda ham imzo qo'yish, ishga tushirishda
> mendan ruxsat so'rash va faqat o'zim va o'zim ruxsat berganlar
> ishlata olishi.

Imzo kalitlari: `ShokirjonMK` · `MKdev` · `mk` · `@ceoNeuron`

---

## 2. ⚠️ ENG MUHIM: hozirgi litsenziya maqsadga ZID

`LICENSE` faylida **MIT** turibdi. MIT matni aynan shunday deydi:

> Permission is hereby granted, **free of charge**, to **any person**
> obtaining a copy of this software … to **use, copy, modify, merge,
> publish, distribute, sublicense, and/or sell** copies …

Ya'ni MIT **har kimga** kodni olish, ishlatish, o'zgartirish, sotish va
qayta tarqatish huquqini **allaqachon bergan**.

### Bu nimani anglatadi

| Savol | Javob |
|-------|-------|
| Texnik darvoza kodni himoya qiladimi? | Yo'q — MIT ostida uni olib tashlash **qonuniy** |
| Kimdir forkni litsenziyasiz ishlatsa? | MIT bo'yicha **haqli** |
| Sud yo'li bilan to'xtatish mumkinmi? | MIT amal qilar ekan — **yo'q** |

**Qulf o'rnatildi, lekin kalit eshik yonida osilgan.**

Bundan tashqari: repo hozir **ommaviy (public)** va MIT ostida
tarqatilgan. Litsenziyani keyin o'zgartirsangiz ham, **eski nusxalar**
MIT ostida qolaveradi — orqaga qaytarib bo'lmaydi.

### Uch variant

| # | Variant | Kimga mos | Nima o'zgaradi |
|---|---------|-----------|----------------|
| **A** | **Xususiy litsenziya** (proprietary) | Tijorat mahsuloti | `LICENSE` almashtiriladi, repo **yopiq** qilinadi. Faqat siz bergan ruxsat bilan ishlatiladi |
| **B** | **Ikki tomonlama** (dual: AGPL-3.0 + tijorat) | Ochiq, lekin himoyalangan | AGPL: forkni ham **ochiq qilishga majbur** qiladi va SaaS bo'shlig'ini yopadi. Tijorat foydalanish uchun — sizdan litsenziya |
| **C** | MIT qoladi | Jamoatchilik loyihasi | Texnik darvoza faqat **hisobot va javobgarlik** vositasi bo'ladi, huquqiy to'siq emas |

**Tavsiyam: B (AGPL-3.0 + tijorat).** Sabablari:

* ochiqlik saqlanadi — bu ishonch va jalb qilish uchun muhim, ayniqsa
  huquqiy AI da («kod ochiq, tekshiring»);
* AGPL forkni **ochiq qolishga majbur qiladi** — kimdir yopiq mahsulot
  yasab sotolmaydi;
* AGPL ning §13 bandi **tarmoq orqali xizmat ko'rsatishni** ham qamrab
  oladi (MIT va GPL da bu bo'shliq bor);
* tijorat mijozlar sizdan alohida litsenziya oladi — bu **daromad
  manbai** bo'ladi.

**Bu huquqiy va biznes qarori — men o'zim o'zgartirmadim.** Sizning
tasdig'ingiz kerak.

---

## 3. Texnik qism — bajarildi

### 3.1 Yagona mualliflik manbai

`src/uzlegal/signature.py` — ism, taxallus, aloqa va kalitlar **bitta
joyda**. CLI, API, MCP va bot shundan oladi. Ikki joyda yozilgan ism
muqarrar ravishda ikkiga ajraladi.

```python
AUTHOR        = "Shokirjon Madaminov"
AUTHOR_HANDLE = "ShokirjonMK"
DEVELOPER     = "MKdev"
CONTACT       = "@ceoNeuron"
AUTHOR_KEYS   = ("ShokirjonMK", "MKdev", "mk", "@ceoNeuron")
```

### 3.2 API sarlavhalari

Har bir HTTP javobda (xato javoblarida ham):

```
X-Author:           Shokirjon Madaminov (ShokirjonMK)
X-Developer:        MKdev
X-Contact:          @ceoNeuron
X-Project:          UzLegal-AI
X-Key-Fingerprint:  SHA256:R4s0AF7cVC018xjK1s3jLusb67r/JoLXFqYKo2WlHkI
```

`/v1/meta` da to'liq `attribution` va `license` bloklari.

### 3.3 CLI banneri

`uzlegal doctor`, `serve`, `bot`, `mcp` — hammasida mualliflik satri.
`uzlegal license author` — to'liq ma'lumot va mualliflik huquqi izohi.

### 3.4 Litsenziya darvozasi

**Ed25519 ochiq kalitli imzo.**

```
muallif mashinasi                       har qanday o'rnatma
─────────────────                       ──────────────────
maxfiy kalit  ──imzolaydi──►   token   ──tekshiradi──►  ochiq kalit
(faqat sizda)                                          (kodda, ochiq)
```

Nima uchun bu to'g'ri sxema:

* kodni **o'qigan** odam litsenziya yasay olmaydi — maxfiy kalit unda yo'q;
* ochiq kalitni kodda saqlash **xavfsiz** — u ataylab ommaviy;
* litsenziyani **muddat** va **imkoniyat** bo'yicha cheklash mumkin.

Sinaldi va isbotlandi (`tests/unit/test_signature.py`, 29 test):

| Urinish | Natija |
|---------|--------|
| Boshqa kalit bilan imzolash | ❌ rad etildi |
| Foydalanuvchi nomini o'zgartirish | ❌ rad etildi |
| Muddatni cho'zish | ❌ rad etildi |
| `scope` ni kengaytirish | ❌ rad etildi |
| Muddati o'tgan token | ❌ rad etildi |
| Haqiqiy token | ✅ qabul qilindi |

### 3.5 Nima cheklanadi, nima YO'Q

| Buyruq | Litsenziya | Nega |
|--------|:----------:|------|
| `serve` · `bot` · `mcp` | **talab qilinadi** | Bular tizimni **boshqalarga ochadi** |
| `search` · `ask` · `doctor` · `index` · `eval` | erkin | Lokal ish va diagnostika. Cheklansa muallifning o'zi ham ishlay olmasdi |

Litsenziyasiz `serve` shunday javob beradi (chiqish kodi **77**):

```
✕ Ishga tushirilmadi

Foydalanish litsenziyasi yo'q.

UzLegal-AI — Shokirjon Madaminov (ShokirjonMK) ning mualliflik ishi.
Xizmatni ishga tushirish uchun muallif bergan litsenziya kerak.
Murojaat: @ceoNeuron
```

---

## 4. Foydalanish

### Litsenziya berish (faqat siz)

```bash
# Muddatsiz, barcha imkoniyatlar — o'zingiz uchun
uzlegal license issue "Shokirjon Madaminov" --days 0 --out license.key

# Mijozga: 1 yil, faqat API va bot
uzlegal license issue "Alfa MChJ" --days 365 --scope serve,bot --out alfa.key

# Sinov: 14 kun
uzlegal license issue "Beta sinov" --days 14 --note "pilot" --out beta.key
```

Maxfiy kalit standart holda `~/.ssh/id_ed25519`. Boshqa yo'l: `--key`.
Parol bilan himoyalangan bo'lsa: `UZLEGAL_KEY_PASSPHRASE`.

### Foydalanuvchi tomonida

```bash
export UZLEGAL_LICENSE="uzlegal-lic.v1.…"     # yoki `license.key` fayli
uzlegal license show                           # holatni ko'rish
uzlegal serve
```

### Docker

```yaml
environment:
  UZLEGAL_LICENSE: ${UZLEGAL_LICENSE:?litsenziya shart}
```

---

## 5. Halol chegaralar

Bu mexanizm **nimani beradi**:

* litsenziyasiz nusxa xizmat ko'rsatmaydi va buni **ochiq aytadi**;
* har bir javobda mualliflik ko'rinadi — kim yozgani yashirilmaydi;
* **kim ruxsat olganini** isbotlash mumkin (token imzolangan);
* muddat va imkoniyat bo'yicha nazorat.

Nimani **bermaydi**:

* kodni o'qishdan himoya — manba ochiq;
* tekshiruvni kod ichidan olib tashlashdan himoya — bu har qanday
  ochiq kodli loyihada **printsipial ravishda** mumkin;
* MIT ostida tarqatilgan **eski nusxalarga** ta'sir.

Himoyaning **asosiy qismi huquqiy**, texnik qism esa uni qo'llab-quvvatlaydi
va halol foydalanuvchi uchun chegarani aniq qiladi.

---

## 6. Keyingi qadamlar — qaroringiz kerak

| # | Ish | Kim hal qiladi |
|---|-----|----------------|
| 1 | **Litsenziya turini tanlash** (A / B / C) | **Siz** |
| 2 | Repo ochiq qolsinmi yoki yopilsinmi | **Siz** |
| 3 | Tanlangan litsenziya matnini qo'yish | Men (tasdiqdan keyin) |
| 4 | `NOTICE` fayli — mualliflik va uchinchi tomon kutubxonalari | Men |
| 5 | Web va Telegram bot yuzasida mualliflik ko'rsatish | Men |
| 6 | Litsenziya reestri (kimga berilgan) | Men |

**1-band bajarilmaguncha texnik darvoza huquqiy kuchga ega emas.**
