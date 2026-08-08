# 00 — Umumiy ko'rinish

## 1. Muammo

O'zbekistonda huquqiy axborotni qidirish bugungi kunda quyidagicha kechadi:

- Yurist `lex.uz` da kalit so'z bo'yicha qidiradi → yuzlab natija, ularning qaysi biri hozir kuchda ekani noaniq
- Hujjatlar o'zaro havolalar bilan bog'langan, lekin bu bog'lanishlar mashina o'qiy oladigan shaklda emas
- Bir norma bir necha marta tahrirlangan; qaysi tahrir qaysi sanada amal qilganini qo'lda aniqlash kerak
- Umumiy maqsadli LLM lar (ChatGPT, Gemini) o'zbek qonunchiligini **bilmaydi** va so'ralganda **o'ylab topadi** — mavjud bo'lmagan modda raqamini ishonch bilan keltiradi

Oxirgi nuqta hal qiluvchi. Yuridik sohada 90% aniqlik yetarli emas — noto'g'ri keltirilgan modda ishni yutqazishga olib keladi.

## 2. Maqsad

Ikkita mustaqil maqsad:

**M1 — Ishonchli huquqiy qidiruv.** Savolga real hujjatga havola bilan javob beradigan tizim. Havolasiz da'vo chiqmaydi. Bekor qilingan norma ishlatilmaydi.

**M2 — Ko'p nuqtai nazarli tahlil.** Bir masalani beshta rol (yurist, advokat, prokuror, professor, sudya) turlicha ko'radi va ularning to'qnashuvidan bir tomonlama javobga qaraganda mustahkamroq xulosa chiqadi.

M1 M2 dan muhimroq. Iqtibossiz ko'p-agentli tizim — bu shunchaki besh baravar ko'proq ishonchli yolg'on.

## 3. Doira (Scope)

### Kiradi

- O'zbekiston Respublikasi qonunchiligi: kodekslar, qonunlar, PF/PQ, vazirlik hujjatlari
- Oliy sud Plenumi qarorlari va ochiq sud amaliyoti
- Hujjat versiyalari va amal qilish muddatlari
- O'zbek (lotin) tili asosiy, rus tili ikkilamchi
- Beshta agent roli va ular o'rtasidagi munozara protokoli
- Oltita ishlash interfeysi (CLI, Web, REST, SDK, MCP, bot)

### Kirmaydi (hozircha)

- Yuridik maslahat berish (mahsulot **tadqiqot vositasi**, maslahatchi emas)
- Hujjat avtomatik imzolash, sudga topshirish
- Boshqa davlatlar qonunchiligi (professor agenti qiyoslash uchun umumiy bilimidan foydalanadi, lekin bu iqtibos bilan tasdiqlanmaydi)
- Real vaqtda sud ishlarini kuzatish
- Noldan foundation model pretraining — [ADR-002](adr/ADR-002-lora-vs-full-finetune.md) ga qarang

## 4. Nima uchun "yangi model" pretraining emas

Foydalanuvchi talabi "yangi AI model yaratish" edi. Muhandislik nuqtai nazaridan bu ikki xil ma'noni anglatishi mumkin:

| Yondashuv | Xarajat | Vaqt | Natija sifati (o'zbek huquqi) |
|-----------|---------|------|-------------------------------|
| Noldan pretraining | $0.5–2M GPU | 6–12 oy | **Yomonroq** — trening ma'lumoti yetarli emas |
| Domenga moslashtirish (CPT + SFT + LoRA + RAG) | ~$0 (local) | 4–5 oy | **Yaxshiroq** |

O'zbek tilidagi yuqori sifatli matn korpusi ~10⁹ token darajasida. Zamonaviy foundation model 10¹³ token ustida o'qitiladi. Noldan o'qitilgan o'zbek modeli tilni ham, mantiqni ham yomon egallaydi.

To'g'ri yechim: **kuchli ko'p tilli bazani olib, uni yuridik domenga chuqur moslashtirish**. Natija amalda "sizning modelingiz" — u sizning ma'lumotingizda o'qitilgan, sizning vazifangizga sozlangan va o'zbek huquqida umumiy modellardan ustun turadi.

Batafsil: [ADR-002](adr/ADR-002-lora-vs-full-finetune.md)

## 5. Muvaffaqiyat mezonlari

Loyiha quyidagi o'lchanadigan chegaralarga yetganda muvaffaqiyatli deb hisoblanadi:

| Metrika | Maqsad | Nima uchun shu qiymat |
|---------|--------|------------------------|
| **Iqtibos aniqligi** (keltirilgan modda mavjud va tegishli) | ≥ 95% | Asosiy ishonch mezoni |
| **Hallucination darajasi** (mavjud bo'lmagan norma) | ≤ 1% | Nolga intiladi; 1% — audit chegarasi |
| **Bekor qilingan norma ishlatilishi** | 0% | Qattiq talab, texnik jihatdan oldini olinadi |
| **Retrieval recall@10** | ≥ 90% | To'g'ri hujjat top-10 da bo'lishi |
| **Gold set to'g'ri javob** (500 ta yurist tekshirgan savol) | ≥ 80% | Boshlang'ich malaka darajasi |
| **Rad etish to'g'riligi** (bilmaganda "bilmayman") | ≥ 85% | Ishonchli noaniqlik |
| **Kechikish** (p95, local M4) | ≤ 45 s to'liq debate | Foydalanish uchun qulay |
| **Kechikish** (p95, tez rejim, bitta agent) | ≤ 8 s | Interaktiv ishlash |

Bu raqamlar [`docs/08-evaluation.md`](08-evaluation.md) da qanday o'lchanishi bilan birga tavsiflangan.

## 6. Foydalanuvchi profillari

**P1 — Amaliyotchi yurist / advokat.** Ish bo'yicha tegishli normalarni tez topish, qarshi tomon argumentlarini oldindan ko'rish. Web UI + iqtibos ko'rinishi.

**P2 — Talaba / o'qituvchi.** Doktrinal tushuntirish, kolliziyalarni tahlil qilish. Professor agenti.

**P3 — Dasturchi.** Boshqa mahsulotga huquqiy qidiruvni integratsiya qilish. REST API + SDK.

**P4 — Tadqiqotchi.** Ommaviy tahlil, korpus bo'yicha statistika. CLI + batch rejim.

## 7. Asosiy risklar

| Risk | Ta'sir | Yumshatish |
|------|--------|------------|
| Ma'lumot sifati past (noto'g'ri parsing, versiya chalkashligi) | **Kritik** — butun tizim asosini buzadi | Faza 1 ga eng ko'p vaqt; qo'lda validatsiya namunasi |
| Yurist ekspert vaqti yetishmasligi (SFT datani tekshirish) | Yuqori | Erta jalb qilish; kichikroq lekin toza dataset |
| O'zbek tilida baza model zaif | O'rta | Faza 0 da o'lchab tanlash, CPT bilan tuzatish |
| Huquqiy javobgarlik (noto'g'ri maslahat) | Yuqori | Qat'iy disclaimer, audit log, "maslahat emas" pozitsiyasi |
| 24 GB RAM cheklovi | O'rta | Adapter arxitekturasi, kvantlash, kerak bo'lsa server profili |

Batafsil: [`docs/11-roadmap.md`](11-roadmap.md) § Risklar.

## 8. Keyingi hujjat

→ [01 — Arxitektura](01-architecture.md)
