# UzLegal-AI

> O'zbekiston huquqiy tizimi uchun ko'p-agentli, iqtibosga asoslangan (citation-grounded) sun'iy intellekt platformasi.

[![Status](https://img.shields.io/badge/status-beta-yellow)]()
[![License](https://img.shields.io/badge/license-AGPL--3.0%20%2B%20tijorat-blue)]()
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows%20%7C%20Docker-lightgrey)]()

---

## Loyiha nima?

UzLegal-AI — bu bitta chatbot emas. Bu **beshta yuridik rolni** o'ynay oladigan va bir masalani **turli nuqtai nazardan** hal qilib, so'ng ularni muvozanatga soladigan huquqiy mulohaza yuritish tizimi:

| Agent | Roli | Nima beradi |
|-------|------|-------------|
| **Yurist** (`jurist`) | Faktlarni ajratadi, tegishli normalarni topadi | Neytral huquqiy tahlil |
| **Advokat** (`advocate`) | Mijoz foydasiga eng kuchli pozitsiya | Himoya argumentlari, protsessual imkoniyatlar |
| **Prokuror** (`prosecutor`) | Qarama-qarshi pozitsiya, ayblov | Zaif nuqtalar, qarshi dalillar |
| **Professor** (`professor`) | Doktrina, kolliziyalar, qiyosiy huquq | Nazariy asos, ilmiy sharh |
| **Sudya** (`judge`) | Dalillarni tortadi, yakun chiqaradi | Asoslangan, muvozanatli xulosa |

Bu **adversarial (qarama-qarshilikka asoslangan)** dizayn tasodifiy emas — u real sud jarayonining strukturasini takrorlaydi va bitta modelning bir tomonlama javob berish tendensiyasini kamaytiradi.

## Asosiy tamoyil: iqtibossiz javob yo'q

Yuridik AI dagi eng katta xavf — modelning **mavjud bo'lmagan qonun moddasini o'ylab topishi** (hallucination). Bu tizimda:

- Har bir huquqiy da'vo real hujjatga havola bilan qaytariladi: `[FK, 234-modda, 2024-yil tahriri]`
- Havola bilan tasdiqlanmagan da'vo javobdan **avtomatik chiqariladi** (`groundedness gate`)
- Bekor qilingan yoki o'zgartirilgan norma `deprecated` deb belgilanadi va ishlatilmaydi
- Model bilmasa — **"bilmayman"** deydi. Rad etish darajasi (`refusal rate`) o'lchanadigan metrika

> **Ogohlantirish:** Bu tizim yuridik maslahat bermaydi. U yuridik **tadqiqot vositasi**. Har qanday xulosa malakali yurist tomonidan tasdiqlanishi shart.

---

## Arxitektura (qisqacha)

```mermaid
flowchart TB
    subgraph CL["Kirish qatlami (Interfaces)"]
        W[Web UI]
        C[CLI / Terminal]
        A[REST + SSE API]
        S[Python/TS SDK]
        T[Telegram bot]
        M[MCP server]
    end

    GW[API Gateway<br/>auth · rate-limit · audit]

    subgraph ORCH["Orkestratsiya (LangGraph)"]
        R[Router<br/>murakkablikni baholaydi]
        D[Debate Engine<br/>advokat ⇄ prokuror]
        J[Judge<br/>sintez + qaror]
    end

    subgraph INF["Inference qatlami"]
        BASE[(Baza model 4-bit<br/>+ 5 LoRA adapter)]
    end

    subgraph RET["Bilim qatlami (RAG)"]
        VS[(Vektor: BGE-M3)]
        BM[(BM25 leksik)]
        RR[Reranker]
        KG[(Hujjat grafi<br/>versiyalar · havolalar)]
    end

    W & C & A & S & T & M --> GW --> R
    R --> D --> J
    D <--> BASE
    J <--> BASE
    D <--> RET
    VS & BM --> RR --> D
    KG --> RR
```

To'liq tavsif: [`docs/01-architecture.md`](docs/01-architecture.md)

---

## Ishlash rejimlari

Tizim bitta yadro (`core`) ustiga qurilgan va **oltita** turli usulda ishlatiladi:

| Rejim | Buyruq / manzil | Foydalanuvchi |
|-------|-----------------|---------------|
| Terminal (interaktiv) | `uzlegal chat --agent judge` | Yurist, dasturchi |
| Terminal (bir martalik) | `uzlegal ask "..." --json` | Skript, CI |
| Web UI | `http://localhost:3000` | Yakuniy foydalanuvchi |
| REST + streaming | `POST /v1/consult` (SSE) | Integratsiya |
| SDK | `pip install uzlegal` | Dasturchi |
| MCP server | `uzlegal mcp serve` | Claude Code, IDE |

Batafsil: [`docs/07-interfaces.md`](docs/07-interfaces.md)

### Joylashtirish variantlari

| Profil | Apparat | Model | Holat |
|--------|---------|-------|-------|
| `local-dev` | MacBook Air M4 24 GB | 14B 4-bit | Butunlay oflayn, internetsiz |
| `workstation` | Mac Studio / RTX 4090 | 14B 8-bit yoki 32B 4-bit | Jamoa ishi |
| `server` | Linux + A100/H100 | 32B+ , vLLM | Ishlab chiqarish |
| `hybrid` | Local + bulut fallback | Yengil savol local, og'iri bulutga | Tejamkor |
| `air-gapped` | Izolyatsiya qilingan tarmoq | To'liq oflayn | Davlat/maxfiy ma'lumot |

Batafsil: [`docs/09-deployment.md`](docs/09-deployment.md)

---

## Hujjatlar

| # | Hujjat | Mavzu |
|---|--------|-------|
| 00 | [Umumiy ko'rinish](docs/00-overview.md) | Muammo, maqsad, doira, muvaffaqiyat mezonlari |
| 01 | [Arxitektura](docs/01-architecture.md) | Tizim dizayni, qatlamlar, ma'lumot oqimi |
| 02 | [Apparat va runtime](docs/02-hardware-runtime.md) | M4 24 GB byudjeti, MLX, kvantlash |
| 03 | [Ma'lumot quvuri](docs/03-data-pipeline.md) | Yig'ish, tozalash, versiyalash, chunking |
| 04 | [RAG tizimi](docs/04-rag.md) | Gibrid qidiruv, reranking, groundedness |
| 05 | [Fine-tuning](docs/05-finetuning.md) | LoRA, dataset, trening, baholash |
| 06 | [Agentlar](docs/06-agents.md) | Rollar, debate protokoli, orkestratsiya |
| 07 | [Interfeyslar](docs/07-interfaces.md) | CLI, Web, API, SDK, MCP, bot |
| 08 | [Baholash](docs/08-evaluation.md) | Metrikalar, gold set, regressiya testlari |
| 09 | [Joylashtirish](docs/09-deployment.md) | Profillar, Docker, monitoring |
| 10 | [Xavfsizlik va muvofiqlik](docs/10-security-compliance.md) | PII, audit, huquqiy javobgarlik |
| 11 | [Yo'l xaritasi](docs/11-roadmap.md) | Fazalar, muddatlar, risklar |
| 12 | [Repo strukturasi](docs/12-repo-structure.md) | Kod tashkiloti, modullar |

**Arxitektura qarorlari (ADR):** [`docs/adr/`](docs/adr/) — nima uchun aynan shu texnologiya tanlangani va qanday muqobillar rad etilgani.

---

## Tezkor boshlash

```bash
git clone https://github.com/ShokirjonMK/uzlegal-ai.git
cd uzlegal-ai

# 1. Muhit
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,rag]"

# 2. Model — ikki yo'ldan biri
#    a) Har qanday platforma (Linux, Windows, macOS) — Ollama orqali
ollama pull gemma3:12b
uzlegal models use ollama-gemma3-12b
#    b) Faqat Apple Silicon — MLX orqali
#    pip install -e ".[mac]" && uzlegal models use gemma3-12b

# 3. Bilim bazasini qurish (20 kodeks ≈ 7 daqiqa — Crawl-delay 20 s)
uzlegal kb sync
uzlegal index build

# 4. Tekshirish va ishga tushirish
uzlegal doctor
uzlegal ask "Mehnat shartnomasida sinov muddati necha oy?"
uzlegal serve --profile local-dev
```

> **NVIDIA kartada.** `uzlegal index build` embedding uchun avtomatik
> `cuda` ni tanlaydi. 8 GB VRAM da model bilan bir vaqtda ishlatilsa
> xotira yetmasligi mumkin — bunday holda `UZLEGAL_EMBED_DEVICE=cpu`.

---

## Loyiha holati

**Beta.** Yadro to'liq ishlaydi: savol → gibrid qidiruv → agentlar
munozarasi → sudya xulosasi → iqtibos nazorati → javob. Barcha
interfeyslar (CLI, REST+SSE, MCP, Telegram bot, SDK, Web) ulangan.

**Nima tayyor:**

- 20 ta kodeks (7 090 modda) indekslangan, versiyalash bilan
- Uchala platformada model ishlaydi (`openai` backend orqali)
- `/v1/admin/*` kalitsiz ochilmaydi; rate-limit va reja chegaralari amalda
- 800+ test, `mypy --strict` toza, CI har push da yuguradi

**Nima yo'q — ochiq aytiladi:**

| Cheklov | Nima uchun |
|---------|-----------|
| Korpus 20 kodeks bilan cheklangan | Qonunosti hujjatlari va sud amaliyoti hali yig'ilmagan (40k hujjat ≈ 17 kun, `robots.txt` Crawl-delay 20) |
| Rol adapterlari o'qitilmagan | Rollar farqi promptdan keladi; LoRA uchun yurist tekshiruvidan o'tgan dataset kerak |
| Huquqiy hujjatlar yo'q | Foydalanuvchi shartnomasi va maxfiylik siyosati yurist tasdig'ini talab qiladi |

Yo'l xaritasi: [`docs/11-roadmap.md`](docs/11-roadmap.md).

---

## Litsenziya

**Ikki tomonlama:** [AGPL-3.0](LICENSE) yoki tijorat litsenziyasi.

| Foydalanish | Litsenziya |
|---|---|
| O'rganish, tadqiqot, ochiq kodli loyiha | AGPL-3.0 (bepul) |
| Tijorat, SaaS, yopiq kodli mahsulot | Tijorat litsenziyasi |

AGPL-3.0 ning § 13 bandi **tarmoq orqali xizmat ko'rsatishni** ham
qamrab oladi: o'zgartirilgan nusxani server sifatida ishlatsangiz,
foydalanuvchilarga manba kodini taklif qilishingiz shart.

Batafsil: [`LICENSING.md`](LICENSING.md) · Murojaat: **@ceoNeuron**

> Xizmat buyruqlari (`serve`, `bot`, `mcp`) muallif bergan imzolangan
> litsenziya talab qiladi. Lokal ish (`search`, `ask`, `doctor`,
> `index`, `eval`) erkin.

Manba huquqiy hujjatlar (lex.uz va boshqalar) O'zbekiston Respublikasi qonunchiligiga muvofiq ochiq ma'lumot hisoblanadi va o'z shartlari asosida ishlatiladi.

## Muallif

**Shokirjon Madaminov** — [@ShokirjonMK](https://github.com/ShokirjonMK)
