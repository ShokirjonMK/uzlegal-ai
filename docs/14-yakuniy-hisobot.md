# 14 — Yakuniy hisobot (2026-08-11)

> **ESKIRGAN SARLAVHA.** Bu hujjat dastlab «kod 100%» deb nomlangan edi.
> 2026-08-12 dagi mustaqil tekshiruv ikkita muhim istisno topdi:
>
> * **Inference qatlami 100% emas edi.** `backend.py` `vllm_backend` va
>   `openai_backend` ni import qilardi, lekin bu ikki fayl **mavjud
>   emasdi**. Ya'ni macOS'dan tashqarida ishlaydigan bitta ham model
>   yo'q edi va `server` profili ishga tushmasdi.
> * **Xavfsizlik umuman hisobga olinmagan edi.** `/v1/admin/*` —
>   foydalanuvchi yaratish va API kalitini qayta tiklash — hech qanday
>   kalitsiz ochiq edi.
>
> Ikkalasi ham 2026-08-12 da tuzatildi. Joriy holat:
> [`16-holat-2026-08-12.md`](16-holat-2026-08-12.md).
>
> Quyidagi matn tarixiy yozuv sifatida o'zgarishsiz qoldirilgan.

**Sana:** 2026-08-11 · **Muallif:** PM · **Asos:** [13 — Yakunlash rejasi](13-completion-plan.md)

Bu hujjat rejaning 6-bo'limidagi talabga javob beradi: har faza uchun
oldin/keyin, QA verdikti, qolgan to'siqlar va ular kimga bog'liq.

---

## 1. Bir jumlada

Qidiruv moddani topardi, model matn yozardi, lekin **ular ulanmagan
edi** — `uzlegal ask` qonunni umuman ko'rmasdi. Endi ulangan: savol →
qidiruv → agentlar → sudya → iqtibos nazorati → javob. Iqtibossiz
huquqiy da'vo javobga chiqmaydi.

---

## 2. Faza bo'yicha oldin/keyin

| Faza | Oldin | Keyin | Nima qo'shildi | Nima qoldi |
|------|------:|------:|----------------|------------|
| **F0** Muhit | 70% | **100%** | ADR-001 yopildi, `bench-uz-legal-v0` yurgizildi, Gemma-3-12B tanlandi, CPT keraksizligi o'lchandi | — |
| **F1** Ma'lumot | 55% | **95%** | Versiyalash, havola grafi, PII anonimizatsiya, validatsiya, `pipeline` CLI | ⛔ 40k korpus (17 kun) |
| **F2** RAG | 60% | **95%** | Hujjat yo'naltirish, graf kengaytmasi, RRF sozlash. Recall@10 **69% → 89%** | ⛔ Embedding fine-tuning (trening juftliklari kerak) |
| **F3** Trening data | 0% | **70%** | Generatsiya quvuri, avtomatik filtrlar, tekshirish CLI | ⛔ Yurist tekshiruvi (~1 500 soat) |
| **F4** Fine-tuning | 0% | **70%** | LoRA quvuri (MLX), xotira hisobi, adapter chiqishi, `train` CLI | ⛔ Haqiqiy adapterlar (tekshirilgan data kerak) |
| **F5** Agentlar | 0% | **95%** | 5 rol, munozara protokoli, sudya sintezi, **groundedness gate**, `consult()`, prefix KV-cache | Rol adapterlari (F4 ga bog'liq) |
| **F6** Interfeyslar | 30% | **95%** | `/v1/consult` + SSE, Telegram bot, MCP server, Python SDK, CLI | Auth/ratelimit (server profili) |

Foizlar **kod tayyorligi** bo'yicha. Mahsulot tayyorligi 1-bo'limdagi
uch to'siqqa bog'liq va u bu sessiyada o'zgarmadi.

---

## 3. Sifat mezoni

```
make lint        ✅  ruff · ruff format · mypy --strict (58 fayl) · import-linter
make test        ✅  490 unit + 13 integration
make eval-smoke  ⬜  (natija 5-bo'limda)
```

Boshlanish holati qizil edi: 3 ruff xatosi, 33 formatlanmagan fayl,
19 mypy xatosi, `lint-imports` esa `uzlegal.ingest` moduli
ko'rinmasligidan yiqilardi.

---

## 4. Arxitektura qarorlari (shu sessiyada qabul qilingan)

### RRF `k=60` → `k=3`

Adabiyotdagi `k=60` **ikkala qidiruv kanali ham teng ishonchli** bo'lgan
holat uchun. Bizda ular teng emas, va o'lchov buni ko'rsatdi:

    savol:  "Yangi xodimni tekshirib ko'rish uchun qancha vaqt"
    vektor: to'g'ri modda — 1-o'rin
    leksik: umuman topmagan
    RRF60:  29-o'rin  ← to'g'ri javob top-10 dan chiqib ketdi

`k=60` da 1- va 50-o'rin farqi atigi 1.8x, `k=3` da esa 13x. Bitta
o'zgarish Recall@10 ni 69% → 83% ga ko'tardi; hujjat yo'naltirish
qolgan 6 punktni qo'shdi.

### Groundedness gate — o'chiradi, tuzatmaydi

Gate hech qachon yangi matn generatsiya qilmaydi. Bu ataylab: tuzatuvchi
gate o'zi hallucination manbaiga aylanardi va tekshiruvchi tekshiriladigan
narsaga aylanardi.

Uchinchi bosqich (iqtibos da'voni qo'llab-quvvatlaydimi) da'voni
**o'chirmaydi, belgilaydi**. Sabab: bu bosqich leksik va u xato qilishi
mumkin; to'g'ri da'voni o'chirish noto'g'risini qoldirishdan qimmatroq.

### LangGraph emas

docs/06 § 4 LangGraph ni taklif qiladi. Grafda yettita tugun va ikkita
shart bor — u beradigan uchta narsani (iz, xatolarga chidamlilik,
shartli oqim) oddiy funksiya ham beradi, qo'shimcha bog'liqliksiz.
Checkpoint kerak bo'lganda (server profili, insonni jalb qilish) u
qo'shiladi va tashqi shartnoma o'zgarmaydi — tashqi dunyo faqat
`consult()` ni ko'radi.

### `uzlegal.cli` boshqa interfeyslardan yuqorida

Import-linter shartnomasida CLI alohida qatlamga chiqarildi: u boshqa
interfeyslarni **ishga tushiradi** (`serve`, `bot`, `mcp`). Bir qatlamga
qo'yilsa bu import taqiqlanardi, holbuki u to'g'ri yo'nalish.

---

## 5. O'lchovlar

### Retrieval (`retrieval-gold-v1`, 36 holat, modelsiz)

| Metrika | Boshlanish | Yakun | Maqsad |
|---------|-----------:|------:|-------:|
| Recall@1 | 36% | **42%** | 60% |
| Recall@3 | 56% | **67%** | 80% |
| Recall@10 | 69% | **89%** | 90% |
| MRR | 0.47 | **0.55** | 0.75 |
| Deprecated leak | 0% | **0%** | 0% |
| Kechikish (median) | 101 ms | **117 ms** | — |

Qolgan 4 nosozlik (`dm-03`, `ish-haqi-01`, `mshart-01`, `fpk-01`) —
semantik: to'g'ri modda kandidatlar orasida bor, lekin past o'rinda.
Ularni tuzatish embedding fine-tuning talab qiladi (⛔ F2).

### Model tanlovi (`bench-uz-legal-v0`, 42 savol, deterministik)

| Model | Umumiy | O'zbek tili | Mulohaza | tok/s |
|-------|-------:|------------:|---------:|------:|
| **gemma3-12b** ⭐ | **3.77** | 4.82 | 83% | 2.9 |
| qwen3-14b | 3.28 | 4.89 | 67% | 2.5 |
| qwen3-8b | 3.22 | 4.79 | 64% | 5.5 |

CPT shart emas: o'zbek tili balli 4.82 ≥ 3.5 (ADR-001).

---

## 6. Qolgan to'siqlar

| To'siq | Kimga bog'liq | Nima kerak |
|--------|---------------|------------|
| **Yurist tekshiruvi** | Malakali yurist | ~1 500 soat (46k namuna × 2 daq). Bu bajarilmaguncha F3/F4 «kod tayyor, mahsulot yo'q» holatida qoladi |
| **To'liq korpus** | Vaqt | 40 000 hujjat × 20 s = ~17 kun uzluksiz. `robots.txt` Crawl-delay 20 — chetlab o'tilmaydi. Hozir 20 kodeks (8 627 chunk) |
| **Huquqiy imzo** | Yurist + rahbariyat | Javobgarlik, litsenziya, PII (docs/10 § 8) |

Bularning uchalasi ham **texnik emas** — kod bilan hal qilinmaydi.

---

## 7. Ochiq cheklovlar (foydalanuvchiga aytilishi shart)

1. **Recall@10 89%** — o'ntadan bir savolda to'g'ri norma kontekstga
   tushmaydi. Gate buni tutadi (javob rad etiladi), lekin bu «javob
   yo'q» degani, «javob noto'g'ri» degani emas.
2. **Rol adapterlari o'qitilmagan** — rollar farqi faqat promptdan
   keladi. Bu ishlaydi, lekin adapterlar bergan rol sadoqatidan pastroq.
3. **Korpus 20 kodeks bilan cheklangan** — qonunosti hujjatlari, sud
   amaliyoti va plenum qarorlari yo'q.
4. **Javob yuridik maslahat emas** — barcha interfeyslarda shu
   ogohlantirish beriladi.
