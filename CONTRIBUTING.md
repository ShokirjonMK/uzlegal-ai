# Hissa qo'shish

## Loyiha holati

**Faza 0 — dizayn.** Hozircha repoda arxitektura hujjatlari va spetsifikatsiya bor. Implementatsiya [`docs/11-roadmap.md`](docs/11-roadmap.md) bo'yicha boshlanadi.

## Ish tartibi

```bash
git clone https://github.com/ShokirjonMK/uzlegal-ai.git
cd uzlegal-ai
make setup-mac        # yoki setup-linux
make doctor           # muhit tekshiruvi
```

Branch nomlari:

| Prefiks | Maqsad |
|---------|--------|
| `feat/` | Yangi xususiyat |
| `fix/` | Xato tuzatish |
| `docs/` | Hujjatlar |
| `data/` | KB yangilanishi (kod emas) |
| `eval/` | Baholash to'plamlari |

## Kod standartlari

```bash
make lint     # ruff + mypy --strict + import-linter
make test     # unit + integration
```

- Barcha ommaviy funksiyalar type-hinted
- Ma'lumot strukturalari — Pydantic modellari
- Docstring: **nima uchun**, nima emas
- Test qamrovi ≥ 75%

### Qatlam bog'liqliklari (CI da tekshiriladi)

`import-linter` quyidagilarni majburlaydi:

1. `core` va undan pastdagi modullar `api`/`cli`/`mcp`/`bot` ni import qilmaydi
2. `ingest` hech narsani import qilmaydi
3. `agents` `orchestrator` ni import qilmaydi
4. Tashqi kutubxonalar faqat adapter modullarda

Bu qoidalarni buzgan PR CI da to'xtaydi. Batafsil: [`docs/12-repo-structure.md`](docs/12-repo-structure.md).

## PR talablari

| Talab | Majburiymi |
|-------|:----------:|
| `make lint` yashil | ✅ |
| `make test` yashil | ✅ |
| Yangi kod uchun test | ✅ |
| `make eval-smoke` regressiya yo'q | ✅ (model/RAG ga tegsa) |
| ADR (arxitektura qarori bo'lsa) | ✅ |
| Hujjat yangilanishi | ✅ (xatti-harakat o'zgarsa) |

## Yuridik mazmunga hissa qo'shish

Bu loyihaning eng qimmatli hissasi — **yuridik ekspertiza**, kod emas.

### Gold set savollari

`data/eval/gold-500/` ga savol qo'shish:

```json
{
  "id": "gold-0501",
  "category": "analytical",
  "question": "...",
  "expected_citations": ["uz-mk-2022:111"],
  "expected_answer_points": ["...", "..."],
  "must_not_contain": ["..."],
  "difficulty": "hard",
  "legal_area": "mehnat"
}
```

Talablar:
- Iqtiboslar real va tekshirilgan bo'lishi
- Kamida ikki yurist tasdig'i
- Manba havolasi ko'rsatilishi

### Xato hisoboti (noto'g'ri javob)

Issue ochishda quyidagilarni kiriting:

1. `trace_id` (javobda ko'rsatiladi)
2. Savol
3. Tizim nima dedi
4. **To'g'ri javob nima va nima uchun** (iqtibos bilan)
5. Model va KB versiyasi

Tasdiqlangan xatolar avtomatik gold set ga qo'shiladi.

## Nima qabul qilinmaydi

| | Sabab |
|---|-------|
| Tekshirilmagan yuridik trening ma'lumoti | Modelni ishonch bilan xato qilishga o'rgatadi |
| Groundedness gate ni chetlab o'tuvchi kod | Tizimning asosiy kafolatini buzadi |
| Iqtibossiz huquqiy da'volar | Arxitektura tamoyiliga zid |
| Disclaimer ni olib tashlash | Huquqiy talab |
| Tashqi LLM API ga bog'liqlik `core` da | Oflayn ishlash va maxfiylikni buzadi |
| Mualliflik huquqi noaniq ma'lumot | Huquqiy risk |

## Xavfsizlik

Zaiflik topsangiz **ommaviy issue ochmang**. To'g'ridan-to'g'ri [@ShokirjonMK](https://github.com/ShokirjonMK) ga yozing.

Ayniqsa jiddiy:
- Groundedness gate ni chetlab o'tish usuli
- Prompt injection orqali rol qulfini buzish
- PII sizib chiqishi
- Bekor qilingan normani amaldagidek ko'rsatish yo'li

## Aloqa

[@ShokirjonMK](https://github.com/ShokirjonMK) · Issues · Discussions
