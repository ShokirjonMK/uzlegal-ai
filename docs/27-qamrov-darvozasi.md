# 27 — Qamrov darvozasi

**Sana:** 2026-08-20
**Manba:** strategiya, S1 — «qamrovni kamchilikdan e'lon qilingan
chegaraga aylantirish». Bu «kodekslar bilan chiqamiz» qarorining
texnik sharti.

---

## 1. Muammo

Korpus O'zbekiston qonunchiligining bir qismini qoplaydi. Qamrovdan
tashqaridagi savolga tizim **yaqin narsani** topib berardi:

| So'ralgan | Qaytarilgan |
|---|---|
| Yevropa Ittifoqi GDPR | O'zbekiston shaxsiy ma'lumotlar qonuni |
| AQSh Konstitutsiyasi | O'zbekiston Konstitutsiyasi |
| Oliy sud Plenumi qarori | mavzuga yaqin kodeks moddasi |

Bu yo'qotish emas, **noto'g'ri javob**. Foydalanuvchi savoliga emas,
boshqa savolga javob oladi — va u ishonarli ko'rinadi, chunki iqtibos
haqiqiy va havola ishlaydi.

`traps-30` da bu o'lchangan: «qamrov» toifasi **40%** da edi.

---

## 2. Ikkita ishlamagan yondashuv — ular ham natija

Darvoza qurishdan oldin ikkita signal sinaldi va **ikkalasi ham
rad etildi**. Ular shu yerda qayd etilgan, chunki keyingi safar
xuddi shu g'oya yana ko'tarilishi mumkin.

### 2.1 Qidiruv balli chegarasi — ajratmaydi

O'lchandi (gold-36 va qamrov tuzoqlari, ayni indeks):

| | min | median | max |
|---|---:|---:|---:|
| Gold savollar | **0.2000** | 0.3626 | 0.6500 |
| Qamrov tuzoqlari | **0.2000** | — | 0.2030 |

Gold savollarning eng pasti tuzoqlar bilan **aynan teng**. Sabab
tuzilmaviy: RRF balli **o'rinni** normallashtiradi, moslikni emas —
birinchi natija har doim bir xil hissa oladi, u qanchalik yaroqsiz
bo'lishidan qat'i nazar.

Chegara qo'yish bu yerda tanlov emas: qaysi qiymat olinmasin, u yo
tuzoqlarni o'tkazadi, yo gold savollarni rad etadi.

### 2.2 Atama korpusda bormi — teskari ishlaydi

Ikkinchi g'oya: so'rovdagi atamalar korpus lug'atida (`BM25.df`)
umuman uchramasa, mavzu qoplanmagan.

O'lchandi:

| | Korpusda umuman yo'q atamasi bor |
|---|---:|
| Gold savollar | **5 / 36** |
| Qamrov tuzoqlari | **0 / 5** |

Signal nafaqat zaif, balki **teskari**. Sabab: gold savollarda
morfologik shakllar bor (`mulkimni`, `majburmi`, `vasiyatda`) va
ular korpusda uchramaydi. Tuzoqlardagi so'zlar esa (`dengiz`,
`hokim`, `plenum`, hatto `gdpr`) korpusda qayerdadir bor.

---

## 3. Ishlaydigan signal — nomlangan manba

Beshala tuzoqning umumiy tuzilishi bitta:

> **Savol huquqiy manbani nomlaydi va o'sha manba korpusda yo'q.**

```
«AQSh Konstitutsiyasi»          → boshqa yurisdiksiya
«Yevropa Ittifoqi GDPR»         → boshqa yurisdiksiya
«Oliy sud Plenumining qarori»   → korpusda 4 ta hujjat
«hokimning qarori»              → korpusda yo'q
«xalqaro dengiz huquqi»         → korpusda yo'q
```

Bu ball ham, o'xshashlik ham emas — bu **ha yoki yo'q**. Shuning
uchun u deterministik, tushuntirib bo'ladigan va **modelsiz
testlanadigan**.

### 3.1 Nima uchun qaror modelga berilmaydi

1. Model «bilmayman» deyishga tabiatan qarshi — u har doim yaqin
   narsa topadi va uni ishonch bilan taqdim etadi.
2. Deterministik qaror takrorlanadi va CI da tekshiriladi.

### 3.2 Ikki tekshiruv

**Yurisdiksiya.** Korpus ta'rifi bo'yicha faqat O'zbekiston
qonunchiligidan iborat, shuning uchun bu tekshiruvga **korpus
ma'lumoti kerak emas**. Boshqa davlat yoki tashkilotning huquqi
haqidagi savolga javob yo'q va korpusni kengaytirish bilan
paydo bo'lmaydi — bu boshqa mahsulot.

Yolg'on ijobiydan himoya: yurisdiksiya nomining o'zi yetarli emas.
«Rossiyaga eksport», «chet el fuqarosi» — bular **O'zbekiston**
huquqi savollari. Rad etish uchun yonida huquqiy manba so'zi ham
turishi kerak. Istisno: `GDPR` kabi nomlangan hujjat o'zi manba.

**Manba turi.** Savolda nomlangan hujjat sinfi (plenum qarori,
hokim qarori, xalqaro shartnoma, vazirlik buyrug'i) korpusda
yetarlicha bormi. Chegara — 10 hujjat: bitta-ikkita tasodifiy
hujjat savolga javob bermaydi, lekin qidiruvni «topdim» deb
aldashi mumkin.

Bu tekshiruv **ma'lumotdan o'qiladi**, kodda qotirilmagan.
Korpusga plenum qarorlari qo'shilsa, darvoza qo'lda
o'zgartirilmasdan ularni o'tkaza boshlaydi. Buni test
qo'riqlaydi (`test_korpus_kengaysa_tekshiruv_ozi_yumshaydi`).

---

## 4. Natija

| | Oldin | Keyin |
|---|---:|---:|
| Qamrov tuzoqlari rad etildi | 2 / 5 | **5 / 5** |
| Gold savollar noto'g'ri rad etildi | — | **0 / 36** |
| Boshqa tuzoqlar noto'g'ri rad etildi | — | **0 / 25** |

Rad javob **halol**: nima so'ralgani, nima uchun javob yo'qligi va
korpusda aslida nima borligi aytiladi.

```
Bu savol bilim bazasining qamrovidan tashqarida.

Bilim bazasida Oliy sud Plenumi qarorlari atigi 4 ta hujjat bor.
Shu sababli bu savolga ishonchli javob bera olmayman — topilgan
normalar so'ralgan manbadan emas.

Taxmin qilib javob bermayman: yaqin mavzudagi normalarni
ko'rsatish so'ralgan savolga javob emas.
```

### 4.1 O'lchov chegarasi — ochiq aytiladi

Yuqoridagi raqamlar **darvozaning o'zini** o'lchaydi: savol
to'sildimi yoki yo'q. To'liq `traps-30` baholashi model talab
qiladi va u bu mashinada yugurtirilmagan (baza model yuklanmagan).
Ya'ni «qamrov toifasi 40% → 100%» degan da'vo hali **tasdiqlanmagan**;
tasdiqlangani — darvoza beshala savolni to'sishi va 61 ta ishlaydigan
savolni to'smasligi.

---

## 5. Bu ishga kirmaydi

| # | Nima | Nega |
|---|---|---|
| **Q1** | To'liq `traps-30` o'lchovi | Baza model kerak (Qwen3-14B yuklanmagan) |
| **Q2** | Foydalanuvchiga «qamrov xaritasi» ko'rsatish | Interfeys ishi — nima qoplangani ochiq ro'yxat sifatida |
| **Q3** | Mavzu darajasidagi qamrov (soha bo'yicha) | Hozir manba darajasida; soha darajasi gold set kengayganda o'lchanadi |
