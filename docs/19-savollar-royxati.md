# 19 — Savollar roʻyxati (javob kutilmoqda)

**Sana:** 2026-08-12

Tizimni toʻliq oʻrganib chiqqach, javobsiz qolgan yoki **sizning
qaroringizni** talab qiladigan savollar. Ustuvorlik boʻyicha tartiblangan.

---

## A. Blokerlar — bularsiz keyingi ish maʼnosiz

### A1. Litsenziya turi ⚠️ ENG MUHIM

`LICENSE` da **MIT** turibdi. MIT **har kimga** kodni ishlatish,
oʻzgartirish, sotish va qayta tarqatish huquqini **allaqachon bergan**.

Yaʼni men qurgan litsenziya darvozasini MIT ostida olib tashlash
**qonuniy**. *Qulf oʻrnatildi, lekin kalit eshik yonida osilgan.*

| Variant | Nima boʻladi |
|---|---|
| **A** — Xususiy (proprietary) | Repo **yopiladi**, faqat siz bergan ruxsat bilan ishlatiladi |
| **B** — AGPL-3.0 + tijorat *(tavsiyam)* | Ochiq qoladi, lekin fork ham ochiq boʻlishga **majbur**. Tijorat foydalanish uchun sizdan litsenziya olinadi |
| **C** — MIT qoladi | Texnik darvoza faqat hisobot vositasi boʻladi, huquqiy toʻsiq emas |

**Savol: qaysi variantni tanlaysiz?**

> ⚠️ Muhim: repo hozir **ommaviy** va MIT ostida tarqatilgan. Litsenziyani
> keyin oʻzgartirsangiz ham **eski nusxalar MIT ostida qolaveradi** —
> orqaga qaytarib boʻlmaydi. Qanchalik tez hal qilinsa, shuncha yaxshi.

### A2. Mualliflik huquqi kimga tegishli?

Jismoniy shaxs (Shokirjon Madaminov) yoki tashkilotmi? Bu litsenziya
matni va shartnomalar uchun kerak.

### A3. Yurist ekspert bormi?

Loyihaning eng katta toʻsigʻi — **texnik emas**:

| Ish | Vaqt |
|---|---|
| Gold set kengaytirish | ~80 soat |
| Rol adapterlari uchun dataset | ~1 500 soat |
| Huquqiy hujjatlar (shartnoma, siyosat) | alohida |

**Savollar:** Yurist bormi? Kim? Qancha vaqt ajrata oladi? Pullikmi?

### A4. Huquqiy hujjatlarni kim tayyorlaydi?

Foydalanuvchi shartnomasi, maxfiylik siyosati, javobgarlik cheklovi,
«Shaxsga doir maʼlumotlar toʻgʻrisida»gi qonun boʻyicha lokalizatsiya.

Bu **eng uzun muddat oladigan** ish va u texnik ishga parallel ketishi
kerak. **Bugun boshlansa yaxshi.**

---

## B. Mahsulot yoʻnalishi

### B1. Birinchi maqsadli auditoriya kim?

Bu barcha keyingi qarorlarga taʼsir qiladi — qaysi savollarni yaxshi
bajarish kerakligi, qaysi kanalga eʼtibor berish kerakligi.

| Auditoriya | Nima oʻzgaradi |
|---|---|
| Oddiy fuqaro | Til soddaroq, Telegram asosiy kanal, tez javob muhim |
| Yurist/advokat | Chuqurroq tahlil, iqtibos aniqligi, sekinroq javob ham maqbul |
| Biznes | Shartnoma tahlili va hujjat generatsiyasi birinchi oʻrinda |
| Davlat organi | Air-gapped, audit, maxfiylik birinchi oʻrinda |

### B2. Biznes modeli qanday?

Bepulmi? Obunami? Soʻrov boʻyichami? Litsenziya sotiladimi?

Kodda **rejalar tizimi allaqachon bor** (`bepul` / `asosiy` / …) —
lekin narxlar va chegaralar sizning qaroringiz.

### B3. Asosiy kanal qaysi — Telegram yoki web?

Ikkalasi ham ishlaydi, lekin sifatni oshirish uchun **bittasiga
eʼtibor qaratish** kerak.

### B4. Qamrov muammosini qanday hal qilamiz?

`traps-30` da 4 ta nosozlik qoldi va ular bir sinfda: savol butunlay
boshqa sohaga tegishli (AQSh Konstitutsiyasi, GDPR, hokim qarori), lekin
qidiruv baribir nimadir qaytaradi.

Men buni **oʻlchab** koʻrdim: oddiy ball chegarasi buni ajrata olmaydi.

| Variant | Xarajat | Natija |
|---|---|---|
| Korpusni kengaytirish | ~17 kun (avtomatik) | Muammo tabiiy kamayadi |
| Semantik mos-nomoslik hakami | ~3 kun ishlab chiqish | Aniqroq, lekin arxitekturaga yangi qism |

**Ikkinchisini sizning qaroringizsiz qoʻshmadim.**

---

## C. Texnik infratuzilma

### C1. Server bormi?

Ishlab chiqarish uchun qanday apparat rejalashtirilgan? GPU bormi?
Bu model tanloviga bevosita taʼsir qiladi:

| Apparat | Model | Kechikish |
|---|---|---|
| 8 GB VRAM (hozirgi) | gemma3:4b | tez |
| 8 GB VRAM | gemma3:12b | 60–90 s |
| 24 GB VRAM | gemma3:12b | ~10 s |
| A100 (bulut) | 32B | ~6 s (parallel agentlar) |

### C2. Domen va hosting bormi?

### C3. Ikkita maʼlumotlar bazasi yonma-yon turibdi

Web qismida **MongoDB** ham, **SQLite** ham ishlatiladi (statistika ikki
joyda). Qaysi biri qolsin?

### C4. Ikkita RAG yonma-yon turibdi

Python yadroda ham, web qobigʻida ham alohida qidiruv tizimi bor.
`web/BIRLASHTIRISH.md` ning oʻzi buni «uzoq muddatda notoʻgʻri» deb
yozgan.

**Taklif:** web qidiruvini yadro `/v1/search` ga koʻchirish (~2 kun).
Rozimisiz?

### C5. Anthropic API kaliti kerakmi?

Web qismida uchta xizmat hali ham Anthropic ni **toʻgʻridan-toʻgʻri**
chaqiradi: hujjat tahlili, hujjat generatsiyasi, shartnoma tekshiruvi.

| Variant | Natija |
|---|---|
| Qoldirish | Sifat yuqori, lekin maʼlumot chetga chiqadi va pul ketadi |
| Yadroga koʻchirish | Toʻliq mahalliy, bepul, lekin sifat pastroq boʻlishi mumkin |

---

## D. Maʼlumot va korpus

### D1. Toʻliq korpusni hozir boshlaymizmi?

40 000 hujjat × 20 s = **~17 kun uzluksiz**. Fonda ketadi, kompyuterni
band qilmaydi (soatiga bir necha soʻrov).

**Boshlaymizmi?**

### D2. Qonunosti hujjatlari kerakmi?

Vazirlar Mahkamasi qarorlari, vazirlik buyruqlari, hokim qarorlari.
Amaliyotda savollarning katta qismi aynan shularga tegishli.

### D3. Sud amaliyoti va plenum qarorlari kerakmi?

Bu tizimning qiymatini sezilarli oshiradi, lekin manbasi va huquqiy
maqomi aniqlanishi kerak.

### D4. Rus tilidagi nashrlar kerakmi?

lex.uz da hujjatlarning rus nashri **alohida hujjat** sifatida turadi.
Hozir faqat oʻzbek nashri indekslanadi.

---

## E. Fine-tuning

### E1. Adapterlarni v1.0 dan keyinga qoldirish tavsiyamga rozimisiz?

Sabab: 1 500 soat yurist vaqtini **taxmin** asosida sarflashdan koʻra,
avval 80 soat sarflab **oʻlchov** qurish va haqiqiy foydalanuvchi
savollarini bilish samaraliroq.

### E2. Bulut GPU byudjeti bormi?

Trening uchun ~$50 (`docs/11` bahosi). Bu mashinada 12B modelni
oʻqitib boʻlmaydi — 8 GB VRAM yetmaydi.

---

## F. Aniqlik kerak boʻlgan joylar

### F1. «Omonmisiz sifatida bajar» — nimani anglatadi?

Taqdimot PDF sini **senior marketolog** nuqtai nazaridan yozdim. Ikkinchi
soʻzni tushunmadim — kopirayter? SMM mutaxassisi? Ism?

### F2. Hisobot boti loyihaning rasmiy botimi?

Menga bergan bot (`uzlegalAiroBot`) faqat hisobot uchunmi yoki u
loyihaning **foydalanuvchi boti** ham boʻladimi? Bu bot sozlamalariga
taʼsir qiladi.

### F3. `.integrity-manifest.sig` ni yangilaysizmi?

Quyida alohida izohladim (§ G).

### F4. Web qismidagi eski `ai-lowyer` nomi qolsinmi?

`web/package.json` da loyiha nomi hali ham `ai-lowyer`. `uzlegal-web`
ga oʻzgartiraymi?

---

## G. Izoh: `.integrity-manifest.sig` nima

Siz «nimaligini tushunmadim» dedingiz — izohlayman.

**Bu fayl repoda allaqachon bor edi**, men yaratmadim.

`scripts/verify-integrity.sh` skripti bilan ishlaydi va **loyiha
fayllari oʻzgartirilmaganini** tekshiradi:

```
har bir fayl  ──HMAC-SHA256──►  imzo  ──►  .integrity-manifest.sig
                    ▲
                    │
              maxfiy kalit
       (~/.ssh/.uzlegal-signing-secret — faqat sizda)
```

**Nima uchun kerak:** kimdir kodni oʻzgartirsa (masalan zararli kod
qoʻshsa), imzo mos kelmaydi va `./scripts/verify-integrity.sh` buni
koʻrsatadi.

**Muammo:** men bugun ~40 faylni oʻzgartirdim, yaʼni manifest **eskirdi**.
Uni yangilash uchun `~/.ssh/.uzlegal-signing-secret` kerak — u **faqat
sizning mashinangizda**. Men uni yangilay olmayman va yangilashga
urinmadim ham.

**Nima qilish kerak:** oʻz mashinangizda manifestni qayta yaratib,
`chore: integrity manifest yangilash` commit qiling. Aks holda
`verify-integrity.sh` boshqalarda «fayllar oʻzgartirilgan» deb xato
beradi.

**Savol:** buni oʻzingiz qilasizmi, yoki bu tizim kerak emasmi?

---

## Javob berish tartibi

Eng tez foyda beradigan tartib:

1. **A1** (litsenziya) — har kun kechikish qaytarib boʻlmaydigan
   nusxalarni koʻpaytiradi;
2. **A3, A4** (yurist) — eng uzun muddat oladi, erta boshlansin;
3. **D1** (korpus) — 17 kun, fonda ketadi, bugun boshlash mumkin;
4. Qolganlari.

Faqat raqamlar bilan javob bersangiz ham yetarli — masalan
«A1: B, A3: bor, D1: ha».
