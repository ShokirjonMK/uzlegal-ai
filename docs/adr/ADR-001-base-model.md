# ADR-001: Baza modelni tanlash

**Holat:** 🟡 Kutilmoqda — Faza 0 baholash natijalari bilan to'ldiriladi
**Sana:** 2026-08-08 (qoralama)
**Qaror qabul qiluvchi:** ML muhandis

## Kontekst

Butun tizim bitta baza model ustiga quriladi. Barcha rol adapterlari shu modelning hosilasi bo'ladi, ya'ni bu qarorni keyinchalik o'zgartirish qimmat — barcha adapterlarni qayta o'qitish kerak bo'ladi.

Cheklovlar:
- 24 GB unified memory (~18 GB foydalanish mumkin)
- Apple Silicon / MLX moslik
- O'zbek tilida ishlash qobiliyati
- Uzun kontekst (≥ 8k, ideal 32k) — yuridik hujjatlar uzun
- Ochiq vazn va tijoriy foydalanishga ruxsat beruvchi litsenziya

## Ko'rib chiqilgan variantlar

| Model | Params | 4-bit | Kontekst | Litsenziya | Ijobiy | Salbiy |
|-------|--------|-------|----------|------------|--------|--------|
| **Qwen3-14B** | 14B | 8.0 GB | 32k+ | Apache-2.0 | Kuchli reasoning, tool-calling, strukturali chiqish | O'zbek tili o'rtacha |
| **Gemma-3-12B-it** | 12B | 7.0 GB | 128k | Gemma ToU | 140 til, turkiy tillar yaxshiroq | Reasoning zaifroq, litsenziya cheklovlari |
| **Mistral-Small-3.2-24B** | 24B | 13.5 GB | 128k | Apache-2.0 | Kuchli umumiy sifat | LoRA trening qisiq, zaxira kam |
| **Qwen3-8B** | 8B | 4.5 GB | 32k | Apache-2.0 | Tez, katta zaxira, arzon trening | Murakkab huquqiy mantiq zaif |

### Rad etilgan variantlar

- **70B+ modellar** — 24 GB ga sig'maydi, hatto 4-bit da ham
- **Yopiq API modellari (GPT, Claude)** — oflayn ishlamaydi, maxfiy ma'lumot tashqariga chiqadi, uzoq muddatli xarajat yuqori, fine-tune cheklangan
- **Noldan pretraining** — [ADR-002](ADR-002-lora-vs-full-finetune.md) ga qarang

## Baholash protokoli

`bench-uz-legal-v0` — 100 savol, to'rtta o'lchov (1–5 ball, ikki mustaqil baholovchi):

| O'lchov | Vazn | Nima tekshiradi |
|---------|:----:|-----------------|
| O'zbek tili ravonligi | 0.30 | Matn tabiiy va yuridik uslubga mos |
| Yuridik terminologiya | 0.25 | Atamalar to'g'ri ishlatiladi |
| Kontekstdan mulohaza | 0.30 | Berilgan matndan to'g'ri xulosa |
| Ko'rsatmaga rioya | 0.15 | Rol, format, "bilmasang aytma" |

**Muhim:** modelning qonunni *bilishi* baholanmaydi — u RAG dan keladi. Baholanadigan narsa: berilgan matn ustida o'zbek tilida qanchalik yaxshi mulohaza yuritadi.

Plus texnik o'lchovlar: tok/s, xotira sarfi, 8k kontekstda barqarorlik.

## Qaror qoidasi

1. O'zbek tili balli **< 3.0** → nomzod rad etiladi, boshqa ballari qanday bo'lishidan qat'i nazar
2. Umumiy ball farqi **< 0.3** → kichikroq model tanlanadi (zaxira xotira muhimroq)
3. Litsenziya tijoriy foydalanishni cheklasa → jiddiy kamchilik

## Qaror

> ⏳ **Faza 0 tugagach to'ldiriladi.**
>
> Bu yerga yoziladi: tanlangan model, ball jadvali, tanlov sababi, va agar ikkinchi o'rindagi model kelajakda muqobil bo'lsa — o'tish sharti.

## Kutilayotgan oqibatlar

**Agar Qwen3-14B tanlansa:** kuchli mulohaza, lekin o'zbek tilini yaxshilash uchun CPT ehtimoli yuqori (+2 hafta).

**Agar Gemma-3-12B tanlansa:** yaxshiroq o'zbek tili, kamroq CPT ehtimoli, lekin murakkab huquqiy mulohazada zaifroq — buni ko'p-agentli munozara qisman qoplaydi.

**Agar Qwen3-8B tanlansa:** eng tez iteratsiya, eng arzon trening, lekin sifat shifti pastroq. `hybrid` profilida "tez rejim" modeli sifatida baribir foydali.

## Qaytarish narxi

Yuqori. Model o'zgarsa: SFT + 5 adapter qayta o'qitiladi (~$50 bulut, ~2 hafta kalendar vaqt). Shuning uchun Faza 0 baholashiga vaqt ayamaslik kerak — bu eng arzon nuqtada qilinadigan qaror.
