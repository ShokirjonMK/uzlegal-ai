# 13 — Yakunlash rejasi (PM tahlili)

**Sana:** 2026-08-11 · **Holat:** ijroda · **Muallif:** PM

Bu hujjat bitta savolga javob beradi: **F0–F6 ni 100% qilish uchun nima kerak
va uni kim bajara oladi.**

---

## 1. Halol chegara: nima bajarilmaydi

Uch narsa **texnik emas** — ular kod bilan hal qilinmaydi va hech qanday
agent ularni bajara olmaydi.

| To'siq | Nima kerak | Nima uchun avtomatlashtirilmaydi |
|--------|-----------|----------------------------------|
| **Yurist tekshiruvi** | ~1 500 soat malakali yurist vaqti (46k namuna × 2 daq) | Tekshirilmagan yuridik trening ma'lumoti modelni **ishonch bilan xato qilishga** o'rgatadi — tekshirilmagan modeldan yomonroq |
| **To'liq korpus** | 40 000 hujjat × 20 s = **~17 kun** uzluksiz yig'ish | `robots.txt` Crawl-delay 20 — majburiy, chetlab o'tilmaydi |
| **Huquqiy imzo** | Javobgarlik, litsenziya, PII masalalari (docs/10 § 8) | Yurist xulosasi talab qilinadi |

Shuning uchun bu rejada **100%** ikki ma'noda ishlatiladi:

* **Kod 100%** — barcha modullar yozilgan, ulangan, testlangan
* **Mahsulot 100%** — yuqoridagi uch to'siq hal qilingandan keyin

Bu hujjat **kod 100%** ni maqsad qiladi va har fazada nima qolishini
aniq ko'rsatadi.

---

## 2. Hozirgi holat (o'lchangan)

| Faza | Bor | Yo'q | Kod tayyorligi |
|------|-----|------|---------------:|
| **F0** Muhit | MLX, 3 model, backend reestri, baholash dvigateli | ADR-001 qarori | 70% |
| **F1** Ma'lumot | Konnektor, parser, sync, kashfiyot | Versiyalash, havola grafi, PII, validatsiya | 55% |
| **F2** RAG | Chunking, BGE-M3, gibrid, kengaytma, reranker | Graf kengaytmasi, hujjat yo'naltirish | 60% |
| **F3** Trening data | — | Generatsiya quvuri, filtrlar, tekshirish UI | 0% |
| **F4** Fine-tuning | — | LoRA trening, merge, adapter reestri | 0% |
| **F5** Agentlar | — | 5 rol, munozara, sudya, **iqtibos nazorati** | 0% |
| **F6** Interfeyslar | CLI, REST qisman, Web panel | `consult()`, SSE, MCP, Telegram bot, SDK | 30% |

**Eng katta bo'shliq F5 da va u eng qimmatlisi:** hozir qidiruv moddani
topadi, model matn yozadi, lekin **ular ulanmagan**. `uzlegal ask` qonunni
umuman ko'rmaydi. Bu ulanmaguncha mahsulot savol-javob bera olmaydi.

---

## 3. Ish taqsimoti

Modullar bir-biriga bog'liqligi kam, shuning uchun **parallel** bajariladi.
Har bir ishchi o'z papkasida ishlaydi; umumiy fayllar (`cli/main.py`)
oxirida PM tomonidan ulanadi — aks holda to'qnashuv bo'ladi.

```
                        ┌─────────────┐
                        │     PM      │  reja · ulash · hisobot
                        └──────┬──────┘
          ┌────────────┬───────┼────────┬────────────┐
          ▼            ▼       ▼        ▼            ▼
      ┌───────┐   ┌───────┐ ┌──────┐ ┌──────┐   ┌────────┐
      │ DEV-A │   │ DEV-B │ │DEV-C │ │DEV-D │   │  PM    │
      │  F5   │   │  F1   │ │ F2   │ │ F6   │   │ F0 · F3│
      │agentlar│  │versiya│ │ graf │ │ bot  │   │ bench  │
      └───┬───┘   └───┬───┘ └──┬───┘ └──┬───┘   └───┬────┘
          └───────────┴────────┴────────┴───────────┘
                             ▼
                        ┌─────────┐
                        │   QA    │  mustaqil tekshiruv
                        └────┬────┘
                             ▼
                        ┌─────────┐
                        │   PM    │  hisobot → Telegram
                        └─────────┘
```

| Ishchi | Faza | Papka | Asosiy natija |
|--------|------|-------|---------------|
| **DEV-A** | F5 | `agents/`, `orchestrator/` | 5 rol, munozara, sudya, groundedness gate, `consult()` |
| **DEV-B** | F1 | `ingest/` | Versiyalash, havola grafi, PII, validatsiya |
| **DEV-C** | F2 | `retrieval/`, `index/` | Graf kengaytmasi, hujjat yo'naltirish, indeks metadata |
| **DEV-D** | F6 | `bot/`, `mcp/`, `api/` | Telegram bot, MCP server, SSE, SDK |
| **PM** | F0, F3, F4 | `eval/`, `training/` | ADR-001, trening quvuri |
| **QA** | hammasi | `tests/` | Mustaqil tekshiruv, regressiya |

### Qat'iy qoidalar (to'qnashuvni oldini olish)

1. Hech kim `cli/main.py` ni tahrirlamaydi — har biri `cli/<modul>.py`
   da Typer sub-app yaratadi, PM ularni ulaydi
2. `types.py` ga faqat **qo'shiladi**, mavjud maydonlar o'zgartirilmaydi
3. Har bir ishchi o'z testlarini yozadi (`tests/unit/test_<modul>.py`)
4. `ruff check` va `pytest` yashil bo'lmaguncha ish tugagan hisoblanmaydi

---

## 4. Har faza uchun «tayyor» mezoni

> **Holat 2026-08-11 yakunida.** Batafsil: [14 — Yakuniy hisobot](14-yakuniy-hisobot.md)

### F0 — Muhit va model tanlovi
- [x] Muhit, MLX, uch model
- [x] `bench-uz-legal-v0` yurgizilgan, **ADR-001 yozilgan** — Gemma-3-12B (3.77/5)
- [x] CPT kerakmi degan qaror — **kerak emas**, o'zbek tili 4.82 ≥ 3.5

### F1 — Ma'lumot quvuri
- [x] Konnektor, parser, sync, kashfiyot
- [x] **Versiyalash** — `ingest/versioning.py`
- [x] **Havola grafi** — `ingest/linking.py`, 29 365 havola · 14 947 qirra
- [x] **PII anonimizatsiya** — `ingest/redact.py`
- [x] **Validatsiya** — `ingest/validate.py`, `uzlegal pipeline validate`
- [ ] ⛔ To'liq 40k korpus — 17 kun, bu sessiyada emas

### F2 — RAG
- [x] Chunking, embedding, gibrid, kengaytma
- [x] **Graf kengaytmasi** — havola qilingan normalar kontekstga qo'shiladi
- [x] **Hujjat yo'naltirish** — `retrieval/routing.py`, 20 kodeks profili
- [x] Recall@10 ≥ 85% — **89%** (69% dan)
- [ ] ⛔ Embedding fine-tuning — trening juftliklari kerak

### F3 — Trening ma'lumoti
- [x] Generatsiya quvuri (urug' → sintetik → filtr) — `training/dataset.py`
- [x] Avtomatik filtrlar (iqtibos, format, uzunlik) — `check_sample`
- [x] Tekshirish interfeysi — `uzlegal train verify` (CLI qismi)
- [ ] ⛔ Yurist tekshiruvi — 1 500 soat

### F4 — Fine-tuning
- [x] LoRA trening quvuri (MLX) — `training/lora.py`, `uzlegal train lora`
- [x] Adapter chiqishi va xotira hisobi; reestr `configs/models.yaml` da
- [ ] ⛔ Haqiqiy adapterlar — tekshirilgan data kerak

### F5 — Agentlar
- [x] 5 rol promptlari va sxemalari — `agents/roles.py`, `agents/schemas.py`
- [x] Munozara protokoli, kelishmovchilik balli — `orchestrator/debate.py`
- [x] Sudya sintezi — `JudgeAgent`
- [x] **Groundedness gate** — `orchestrator/gate.py`, iqtibossiz da'vo o'chiriladi
- [x] `consult()` — `core.py`, RAG + model + agentlar bir zanjirda
- [x] Prefix KV-cache — `orchestrator/graph.build_context()`

### F6 — Interfeyslar
- [x] CLI, model boshqaruvi, Web panel
- [x] `/v1/consult` va SSE oqim (bosqich hodisalari)
- [x] Telegram bot — `bot/telegram.py`, `uzlegal bot`
- [x] MCP server — `mcp/server.py`, `uzlegal mcp`
- [x] Python SDK — `sdk.py`, ichki va masofaviy rejim

---

## 5. Xavflar

| Xavf | Yumshatish |
|------|------------|
| Parallel ishchilar bir faylni tahrirlaydi | Papka bo'yicha qat'iy taqsimot, `cli/main.py` faqat PM da |
| Agentlar sifatsiz kod yozadi | QA mustaqil tekshiradi; `ruff` + `pytest` majburiy |
| Sintetik trening data yomon | Ochiq belgilanadi: **tekshirilmagan**, ishlab chiqarishga chiqmaydi |
| F5 sekin ishlaydi (70 s/agent) | Prefix KV-cache; `simple` rejim standart |
| Retrieval 69% — agentlar noto'g'ri kontekst oladi | Gate uni tutadi va rad etadi; ochiq cheklov sifatida yoziladi |

---

## 6. Yakuniy hisobot

PM barcha ish tugagach:
1. Har faza uchun **oldin/keyin** foizi
2. QA verdikti
3. Qolgan to'siqlar va ular kimga bog'liq
4. Telegram orqali yuborish
