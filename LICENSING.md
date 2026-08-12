# Litsenziyalash — UzLegal-AI

**Mualliflik huquqi © 2026 Shokirjon Madaminov** (ShokirjonMK · MKdev · @ceoNeuron).
Barcha huquqlar himoyalangan.

UzLegal-AI **ikki tomonlama litsenziya** (dual licensing) asosida
tarqatiladi. Sizga qaysi biri tegishli ekanini quyidagi jadval koʻrsatadi.

---

## Qisqacha

| Foydalanish turi | Litsenziya | Toʻlov |
|---|---|---|
| Oʻrganish, tadqiqot, shaxsiy sinov | AGPL-3.0 | Bepul |
| Ochiq kodli loyihada ishlatish | AGPL-3.0 | Bepul |
| **Ichki tijorat foydalanish** | **Tijorat litsenziyasi** | Kelishuv boʻyicha |
| **Mijozlarga xizmat koʻrsatish (SaaS)** | **Tijorat litsenziyasi** | Kelishuv boʻyicha |
| **Yopiq kodli mahsulotga qoʻshish** | **Tijorat litsenziyasi** | Kelishuv boʻyicha |

Shubha boʻlsa — soʻrang: **@ceoNeuron**

---

## 1. AGPL-3.0 (ochiq litsenziya)

Toʻliq matn: [`LICENSE`](LICENSE)

AGPL-3.0 sizga kodni **ishlatish, oʻrganish, oʻzgartirish va tarqatish**
huquqini beradi. Buning evaziga uchta shart bor:

1. **Manba kodini ochiq qoldirish.** Oʻzgartirilgan nusxani tarqatsangiz,
   oʻzgarishlarni ham AGPL-3.0 ostida chiqarasiz.

2. **Tarmoq orqali xizmat ham hisobga olinadi (§ 13).** Bu AGPL ning
   GPL dan asosiy farqi. Agar siz oʻzgartirilgan nusxani **server
   sifatida** ishlatsangiz va foydalanuvchilar unga tarmoq orqali
   murojaat qilsa — ularga ham manba kodini taklif qilishingiz shart.
   Yaʼni «biz kodni tarqatmaymiz, faqat xizmat koʻrsatamiz» degan
   bahona AGPL da ishlamaydi.

3. **Mualliflik saqlanadi.** Mualliflik xabarlari, `SIGNATURE.md` va
   API javoblaridagi `X-Author` sarlavhalari olib tashlanmaydi.

### AGPL nima uchun tanlandi

| Sabab | Izoh |
|---|---|
| **Ishonch** | Huquqiy AI da kod ochiq boʻlishi shart — foydalanuvchi javob qanday shakllanganini tekshira olishi kerak |
| **Himoya** | Kimdir kodni olib **yopiq** mahsulot yasab sotolmaydi |
| **SaaS bardoshi** | § 13 tarmoq xizmatini ham qamrab oladi — MIT va GPL da bu boʻshliq bor |
| **Daromad** | Tijorat foydalanish uchun alohida litsenziya olinadi |

---

## 2. Tijorat litsenziyasi

AGPL shartlari sizga toʻgʻri kelmasa — masalan:

* mahsulotingiz **yopiq kodli** va uni ochishni istamaysiz;
* mijozlarga **xizmat koʻrsatasiz** va manba kodini taklif qilishni
  istamaysiz;
* korporativ yuridik siyosat AGPL ni taqiqlaydi;

— **tijorat litsenziyasi** olishingiz mumkin. U AGPL shartlaridan ozod
qiladi.

### Nimalarni oʻz ichiga oladi

| | |
|---|---|
| AGPL majburiyatlaridan ozod qilish | Kodni yopiq mahsulotda ishlatish mumkin |
| Foydalanish litsenziyasi kaliti | `serve`, `bot`, `mcp` uchun (§ 3) |
| Muddat va imkoniyat chegaralari | Kelishuv boʻyicha |
| Texnik koʻmak | Alohida kelishuv |

### Murojaat

**Shokirjon Madaminov** — Telegram: **@ceoNeuron**
GitHub: [github.com/ShokirjonMK/uzlegal-ai](https://github.com/ShokirjonMK/uzlegal-ai)

Xatda koʻrsating: tashkilot nomi, foydalanish maqsadi, taxminiy
foydalanuvchilar soni, joylashtirish turi (oʻz serveringiz yoki bulut).

---

## 3. Texnik litsenziya darvozasi

Ikkala litsenziya turida ham xizmat buyruqlari muallif bergan
**imzolangan token** talab qiladi:

| Buyruq | Litsenziya |
|---|---|
| `uzlegal serve` · `bot` · `mcp` | **talab qilinadi** |
| `uzlegal search` · `ask` · `doctor` · `index` · `eval` | erkin |

Sabab: cheklov **xizmat koʻrsatishga** qoʻyiladi. Lokal oʻrganish,
tekshirish va tadqiqot ochiq qoladi — bu AGPL ruhiga ham mos.

Token Ed25519 bilan imzolanadi. Ochiq kalit kodda, maxfiy kalit faqat
muallifda:

```
SHA256:R4s0AF7cVC018xjK1s3jLusb67r/JoLXFqYKo2WlHkI
```

Batafsil: [`docs/17-mualliflik-va-litsenziya.md`](docs/17-mualliflik-va-litsenziya.md)

---

## 4. Manba maʼlumotlar

Huquqiy hujjatlar (lex.uz va boshqalar) Oʻzbekiston Respublikasi
qonunchiligiga muvofiq **ochiq maʼlumot** hisoblanadi va oʻz shartlari
asosida ishlatiladi. Ular ushbu litsenziya doirasiga kirmaydi.

---

## 5. Litsenziya tarixi

| Sana | Oʻzgarish |
|---|---|
| 2026-08-12 | **MIT → AGPL-3.0 + tijorat** (ikki tomonlama) |
| — | Boshlanishida MIT |

> ⚠️ **Muhim.** 2026-08-12 gacha tarqatilgan nusxalar MIT litsenziyasi
> ostida olingan va ular uchun MIT shartlari amal qiladi. Litsenziya
> oʻzgarishi **orqaga qaytmaydi**. Shu sanadan keyingi barcha versiyalar
> AGPL-3.0 + tijorat shartlari ostida.

---

## 6. Kafolat yoʻqligi

Dastur **«qanday boʻlsa shundayligicha»** taqdim etiladi, hech qanday
kafolatsiz. Bu AGPL-3.0 ning 15- va 16-bandlarida batafsil yozilgan.

Alohida taʼkidlanadi: **UzLegal-AI yuridik maslahat bermaydi.** U
yuridik **tadqiqot vositasi**. Har qanday xulosa malakali yurist
tomonidan tasdiqlanishi shart. Tizim javoblariga tayanib qabul qilingan
qarorlar uchun javobgarlik foydalanuvchi zimmasida.
