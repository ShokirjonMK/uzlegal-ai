# bench-uz-legal-v0

Faza 0 baza model tanlovi uchun baholash to'plami — [ADR-001](../../../docs/adr/ADR-001-base-model.md).

## ⚠️ Muhim: bu huquqiy manba EMAS

Bu to'plamdagi `context` matnlari **sintetik sinov fixture'lari**. Ular real
qonun matni emas va huquqiy maqsadda ishlatilmasligi kerak. Ular faqat bitta
narsani o'lchaydi:

> **Model berilgan matn ustida o'zbek tilida qanchalik yaxshi mulohaza yuritadi?**

Modelning qonunni *bilishi* bu yerda baholanmaydi — u bilim RAG dan keladi
([ADR-006](../../../docs/adr/ADR-006-rag-first.md)). Real qonun korpusi Faza 1
da quriladi va `gold-500` to'plami o'sha korpus asosida yuriстlar tomonidan
tayyorlanadi.

## Nima o'lchanadi

| O'lcham | Vazn | Qanday tekshiriladi |
|---------|-----:|---------------------|
| `context_reasoning` | 0.30 | `expect_any` / `forbid` — kontekstdan to'g'ri xulosa |
| `uzbek_fluency` | 0.30 | Kirill va rus/ingliz so'zlarining yo'qligi, o'zbek morfologiyasi |
| `legal_terminology` | 0.25 | `expect_any` — kutilgan yuridik atamalar |
| `instruction_following` | 0.15 | `must_cite`, `max_words`, `must_refuse` |

Barcha tekshiruvlar **deterministik** — LLM-judge ishlatilmaydi, shuning uchun
natija takrorlanadi va judge bias'i yo'q.

## Kategoriyalar

| Kategoriya | Soni | Nima sinaladi |
|------------|-----:|---------------|
| `reasoning` | 12 | Kontekstdan xulosa chiqarish |
| `refusal` | 10 | Kontekstda javob yo'qligini tan olish |
| `citation` | 6 | Iqtibos intizomi |
| `terminology` | 6 | O'zbek yuridik atamalari |
| `language` | 4 | Toza o'zbek tili (kirill/rus aralashmasligi) |
| `format` | 4 | Ko'rsatilgan formatga rioya |
| **Jami** | **42** | |

`refusal` kategoriyasi eng muhim: yuridik tizimda "bilmayman" — to'g'ri javob.
Kontekstda javob bo'lmagan holda javob "to'qib chiqargan" model rad etiladi.

## Ishga tushirish

```bash
uzlegal eval bench --candidates qwen3-14b,gemma3-12b,qwen3-8b
uzlegal eval bench --candidates qwen3-8b --limit 10   # tez sinov
```

Natija: `reports/model-selection.md` va `reports/bench-<model>.jsonl`

## Namuna format

```json
{
  "id": "reason-01",
  "category": "reasoning",
  "context": "[C1] Sinov muddati olti oydan oshmasligi kerak.",
  "question": "Ish beruvchi bir yillik sinov muddati belgilay oladimi?",
  "expect_any": [["yo'q", "belgilay olmaydi", "mumkin emas"]],
  "forbid": ["ha, belgilay oladi"],
  "must_cite": ["C1"],
  "max_words": 80
}
```

- `expect_any`: ro'yxatlar ro'yxati. Har bir ichki ro'yxatdan **kamida bittasi**
  javobda bo'lishi kerak (sinonimlar guruhi).
- `forbid`: bittasi ham bo'lmasligi kerak — bo'lsa namuna muvaffaqiyatsiz.
- `must_cite`: shu belgilar javobda bo'lishi shart.
- `must_refuse`: model javob bermasligi kerakligini bildiradi.
