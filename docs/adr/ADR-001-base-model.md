# ADR-001: Baza modelni tanlash

**Holat:** ♻️ Qayta ko'rildi — 2026-08-20 (§ «Qayta ko'rish»)
**Sana:** 2026-08-11 (o'lchov natijasi bilan)
**Qaror qabul qiluvchi:** ML muhandis

## Kontekst

Butun tizim bitta baza model ustiga quriladi. Barcha rol adapterlari shu
modelning hosilasi bo'ladi, ya'ni bu qarorni keyinchalik o'zgartirish qimmat —
barcha adapterlarni qayta o'qitish kerak.

Cheklovlar: 24 GB unified memory, Apple Silicon / MLX, o'zbek tili, uzun
kontekst, ochiq vazn.

## Baholash

`bench-uz-legal-v0` — **42 savol, 9 kategoriya**, to'liq deterministik
tekshiruv. LLM-judge **ishlatilmadi**: natija takrorlanadi va judge bias'i
yo'q. Har uch nomzod bir xil sharoitda, harorat 0.1.

Muhim: bu to'plam modelning **qonunni bilishini** o'lchamaydi — u bilim RAG
dan keladi ([ADR-006](ADR-006-rag-first.md)). O'lchanadigan narsa: berilgan
matn ustida o'zbek tilida qanchalik yaxshi mulohaza yuritadi.

## Natijalar

| Model | Umumiy | Mulohaza | O'zbek tili | Atamalar | Ko'rsatma | Rad etish | tok/s | Xotira |
|-------|-------:|---------:|------------:|---------:|----------:|----------:|------:|-------:|
| **gemma3-12b** ⭐ | **3.77** | 83% | 4.82 | 33% | 88% | 100% | 2.9 | 6.7 GB |
| qwen3-14b | 3.28 | 67% | 4.89 | 17% | 81% | 100% | 2.5 | 7.7 GB |
| qwen3-8b | 3.22 | 64% | 4.79 | 17% | 81% | 80% | 5.5 | 4.3 GB |

Kategoriya bo'yicha (to'g'ri javoblar):

| Model | reasoning | refusal | citation | terminology | language | format |
|-------|----------:|--------:|---------:|------------:|---------:|-------:|
| **gemma3-12b** | **8/12** | 10/10 | **5/6** | **2/6** | 3/4 | **4/4** |
| qwen3-14b | 3/12 | 10/10 | 4/6 | 1/6 | **4/4** | 3/4 |
| qwen3-8b | 7/12 | 8/10 | 4/6 | 1/6 | 1/4 | 3/4 |

## Qaror (2026-08-11 — keyinchalik almashtirildi)

**Gemma-3-12B-it (4-bit) tanlandi.**

Uch sabab:

1. **Mulohaza sezilarli ustun** — 8/12 vs 3/12 va 7/12. Yuridik tahlilda
   asosiy qobiliyat shu.
2. **Iqtibos intizomi eng yaxshi** — 5/6. Bu loyihaning markaziy talabi.
3. **Kichikroq** — 6.7 GB vs 7.7 GB. Qoida bo'yicha teng natijada kichigi
   tanlanadi; bu yerda u ham kichik, ham kuchli.

Farq 0.49 ball — qaror qoidasidagi 0.3 chegarasidan katta, shuning uchun
"kichikroqni tanlash" qoidasi qo'llanmadi (baribir mos kelardi).

### CPT shart emas

Uchala modelning o'zbek tili balli **4.79–4.89 / 5**. Bu `ADR-002` dagi
chegaradan (3.5) ancha yuqori. Continued Pretraining **rejadan chiqarildi** —
u ~2 hafta va catastrophic forgetting xavfini olib kelardi, foydasi esa yo'q.

Bu kutilmagan yaxshi natija: dastlab o'zbek tili asosiy xavf deb
belgilangandi.

## Kutilmagan topilma: terminologiya zaif

Eng yaxshi natija ham **2/6** — barcha modellar o'zbek yuridik atamalarini
yomon biladi. Aniq nosozliklar:

| Savol | Kutilgan atama | Natija |
|-------|----------------|--------|
| `term-01` | vindikatsiya | topilmadi |
| `term-02` | haqiqiy emas (nohaq bitim) | topilmadi |
| `term-03` | ishonchnoma | topilmadi |

Bu **fine-tuning aynan qayerda foyda berishini ko'rsatadi**: til yoki mantiq
emas, **domen terminologiyasi**. Faza 3–4 rejasi shunga qarab
tartiblanadi — rol uslubidan oldin atama bilimi.

## Qwen3-14B nima uchun yutqazdi

Kutilmagan natija: kattaroq model mulohazada 3/12 oldi. Ehtimoliy sabab —
`enable_thinking=False` bilan ishga tushirilgan. Qwen3 "thinking" rejimisiz
murakkab mulohazada zaiflashadi, lekin uni yoqish javob uzunligini va
kechikishni bir necha barobar oshiradi (yuridik javobda keraksiz).

Bu alohida tekshirilishi mumkin, lekin gemma3-12b baribir tez va kichik.

## Oqibatlari

### Ijobiy
- CPT rejadan chiqdi: **−2 hafta**, −1 xavf
- Kichikroq model: KV-cache va adapterlar uchun 1 GB ko'proq joy
- Iqtibos intizomi kuchli — gate kamroq da'vo o'chiradi
- 128k kontekst (Qwen3 da 32k) — uzun hujjat tahlili uchun zaxira

### Salbiy
- **Gemma ToU litsenziyasi** Apache-2.0 dan cheklangan. Tijoriy foydalanish
  oldidan shartlar yuristda tekshirilishi kerak — `docs/10 § 8` ga qo'shildi.
- Generatsiya 2.9 tok/s (Qwen3-8B 5.5). Tezlik kerak bo'lsa `hybrid`
  profilida 8B "tez rejim" modeli sifatida qoladi.

### Qaytarish narxi
O'rta. Model o'zgarsa adapterlar qayta o'qitiladi (~$12 bulut, 2 hafta
kalendar). Lekin adapterlar hali yo'q, shuning uchun **hozir qaytarish
deyarli bepul** — qaror to'g'ri vaqtda qabul qilindi.

## Keyingi qadam

`configs/models.yaml` da `selected: gemma3-12b`. Barcha rol adapterlari shu
baza ustiga o'qitiladi.


---

## Qayta ko'rish — 2026-08-20

**Yangi qaror: Qwen3-14B (4-bit).** Gemma-3-12B rad etildi.

### Nima uchun o'zgardi

O'lchov natijalari **o'zgarmadi** — Gemma hamon 0.49 ball ustun.
O'zgargan narsa qaror mezoni: `docs/10 § 8` da qayd etilgan
huquqiy savol ochiq turardi va u endi hal qilindi.

| | Gemma-3-12B | Qwen3-14B |
|---|---|---|
| Umumiy ball | **3.77** | 3.28 |
| Litsenziya | Gemma ToU — foydalanish siyosati va hosila modellarga cheklov | **Apache-2.0** |
| Tijoriy foydalanish | Tekshirilishi shart edi | Ochiq |
| Hosila (adapter) tarqatish | Cheklovga tobe | Ochiq |
| O'zbek tili | 4.82 / 5 | **4.89 / 5** |
| Xotira | 6.7 GB | 7.7 GB |

### Asos

1. **Huquqiy tozalik balldan ustun.** Bu mahsulot yuristlarga
   qonun bo'yicha javob beradi. Uning o'z baza modeli litsenziyasi
   noaniq bo'lsa — mahsulotning butun asosi noaniq. Iqtibosga
   asoslangan tizimda bu qabul qilib bo'lmaydigan ziddiyat.

2. **Kechiktirish narxi assimetrik.** Adapterlarni Gemma ustida
   o'qitib, keyin litsenziya to'sib qo'ysa — **hamma adapter
   qaytadan o'qitiladi** va u yurist soatini emas, GPU soatini
   emas, **kalendarni** yoqadi. Qaror ilgari qabul qilingani ma'qul.

3. **0.49 ball qayerdan kelgani muhim.** Farq asosan `reasoning`
   (8/12 vs 3/12) dan. Lekin `§ Kutilmagan topilma` da yozilgani
   kabi, ikkala model ham **terminologiyada teng darajada zaif**
   (2/6 va 1/6) — ya'ni fine-tuning aynan shu bo'shliqni yopadi.
   Rol adapterlaridan keyin bu farqning qancha qolishi
   **o'lchanmagan** va uni oldindan aytib bo'lmaydi.

4. **O'zbek tilida Qwen3 hatto ustunroq** (4.89 vs 4.82) —
   farq shovqin ichida, lekin hech bo'lmaganda yo'qotish emas.

### Nima qilinadi

| Qadam | Holat |
|---|---|
| `configs/models.yaml` → `selected: qwen3-14b` | ✅ |
| `docs/10 § 8` dagi 6-savol yopildi | ✅ |
| `configs/training/role-lora.yaml` baza modeli | tekshirilsin |
| Adapterlar | hali o'qitilmagan — **yo'qotish yo'q** |

### Xavf — ochiq aytiladi

Mulohaza balli pastroq modelga o'tilmoqda va bu **sifatga ta'sir
qilishi mumkin**. Ta'sir hajmi hozir noma'lum: `bench-uz-legal-v0`
to'plami bo'sh (0 holat), ya'ni qayta o'lchash uchun avval u
tiklanishi kerak. Qayd etildi: bu o'lchov R1 bosqichida
takrorlanadi va natija shu ADR ga qo'shiladi.

Agar farq amalda sezilarli chiqsa — qaror qayta ko'riladi,
lekin **litsenziya mezoni saqlanadi**: muqobil sifatida boshqa
Apache-2.0 yoki MIT modeli qidiriladi, Gemma emas.
