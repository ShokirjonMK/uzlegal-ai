# 01 — Arxitektura

## 1. Dizayn tamoyillari

Barcha keyingi qarorlar shu beshta tamoyildan kelib chiqadi:

**T1 — Bilim modelda emas, indeksda.** Model qonunni "yodlamaydi". Model *mulohaza yuritishni* biladi, faktni indeksdan oladi. Qonun o'zgarsa — indeks yangilanadi, model qayta o'qitilmaydi.

**T2 — Iqtibos majburiy.** Har bir huquqiy da'vo `document_id + article + version` uchligiga bog'lanadi. Bog'lanmagan da'vo javobdan chiqariladi.

**T3 — Bitta baza, ko'p adapter.** Beshta rol beshta model emas. Bitta kvantlangan baza + beshta LoRA adapter. Bu 24 GB cheklovini hal qiladi va rollarni izchil saqlaydi.

**T4 — Yadro interfeysdan mustaqil.** `core` kutubxonasi HTTP, terminal yoki bot haqida hech narsa bilmaydi. Har bir interfeys — yupqa adapter.

**T5 — Har bir qadam kuzatiladi.** Retrieval natijasi, har agentning javobi, sudyaning qarori — hammasi trace ga yoziladi. Yuridik tizimda "model shunday dedi" yetarli emas; nima uchun deganini ko'rsatish kerak.

---

## 2. Qatlamli ko'rinish

```mermaid
flowchart TB
    subgraph L6["6 · Interfeys qatlami"]
        direction LR
        I1[Web UI<br/>Next.js]
        I2[CLI<br/>Typer]
        I3[REST/SSE<br/>FastAPI]
        I4[SDK<br/>py · ts]
        I5[MCP<br/>server]
        I6[Bot<br/>Telegram]
    end

    subgraph L5["5 · Gateway qatlami"]
        direction LR
        G1[Auth · API key]
        G2[Rate limit]
        G3[Audit log]
        G4[PII redaction]
    end

    subgraph L4["4 · Orkestratsiya qatlami — LangGraph"]
        direction LR
        O1[Router]
        O2[Debate Engine]
        O3[Judge / Synthesis]
        O4[Groundedness Gate]
    end

    subgraph L3["3 · Agent qatlami"]
        direction LR
        A1[jurist]
        A2[advocate]
        A3[prosecutor]
        A4[professor]
        A5[judge]
    end

    subgraph L2["2 · Inference qatlami"]
        direction LR
        M1[MLX / vLLM runtime]
        M2[Baza model 4-bit]
        M3[LoRA adapter registry]
        M4[KV-cache pool]
    end

    subgraph L1["1 · Bilim qatlami"]
        direction LR
        K1[(Vektor indeks<br/>BGE-M3)]
        K2[(Leksik indeks<br/>BM25)]
        K3[Reranker]
        K4[(Hujjat grafi<br/>versiya · havola)]
    end

    subgraph L0["0 · Ma'lumot qatlami"]
        direction LR
        D1[Konnektorlar<br/>lex.uz · sud.uz]
        D2[Normalizatsiya]
        D3[Versiyalash]
        D4[(Object store<br/>xom hujjatlar)]
    end

    L6 --> L5 --> L4
    L4 <--> L3
    L3 <--> L2
    L4 <--> L1
    L3 <--> L1
    L0 --> L1
```

Har bir qatlam faqat o'zidan pastdagisiga bog'liq. Bu modullarni **parallel ishlab chiqish** imkonini beradi — RAG jamoasi agent qatlami tayyor bo'lishini kutmaydi.

---

## 3. So'rov hayotiy sikli

Foydalanuvchi savol beradi. Nima sodir bo'ladi:

```mermaid
sequenceDiagram
    participant U as Foydalanuvchi
    participant GW as Gateway
    participant R as Router
    participant RET as RAG
    participant AG as Agentlar
    participant J as Judge
    participant G as Gate

    U->>GW: savol + kontekst
    GW->>GW: auth · rate-limit · PII maskalash
    GW->>R: normalizatsiyalangan so'rov

    R->>R: murakkablikni baholash
    Note over R: simple → 1 agent<br/>standard → 3 agent<br/>complex → to'liq debate

    R->>RET: huquqiy savolni kengaytirish
    RET->>RET: gibrid qidiruv (vektor + BM25)
    RET->>RET: rerank → top-K
    RET->>RET: versiya filtri (amaldagi normalar)
    RET-->>R: kontekst + iqtiboslar

    R->>AG: jurist (faktlar + normalar)
    AG-->>R: huquqiy ramka

    par Raund 1
        R->>AG: advocate (himoya)
        R->>AG: prosecutor (ayblov)
    end
    AG-->>J: ikki pozitsiya

    opt Kelishmovchilik yuqori
        J->>AG: raund 2 — bir-birining dalilini rad et
        AG-->>J: rebuttal
    end

    J->>AG: professor (doktrinal sharh)
    AG-->>J: nazariy asos

    J->>J: sintez + tortish
    J->>G: loyiha javob + iqtiboslar

    G->>RET: har bir da'voni tekshir
    alt Iqtibos tasdiqlandi
        G-->>U: javob + havolalar + trace
    else Tasdiqlanmadi
        G->>G: da'voni olib tashla yoki "noaniq" deb belgila
        G-->>U: qisqartirilgan javob + ogohlantirish
    end
```

### Router mantiqi

Har bir savolga to'liq debate kerak emas — u qimmat (45 s, ~8k token). Router uch darajaga ajratadi:

| Daraja | Belgilari | Oqim | Kechikish |
|--------|-----------|------|-----------|
| `simple` | Faktik: "MMTning hozirgi stavkasi?" | RAG → `jurist` → gate | ~5 s |
| `standard` | Bir tomonlama tahlil: "Bu shartnoma haqiqiymi?" | RAG → `jurist` → `professor` → `judge` | ~20 s |
| `complex` | Nizoli: "Bu ishda kim haq?" | To'liq debate | ~45 s |

Router — kichik klassifikator (baza model + qisqa prompt, yoki o'qitilgan yengil model). Foydalanuvchi `--mode` bilan majburlashi mumkin.

---

## 4. Inference qatlami: bitta baza, ko'p adapter

Bu loyihaning markaziy texnik qarori.

### Muammo

Beshta 14B modelni 4-bit da yuklash = ~40 GB. Mashinada 24 GB (undan ~18 GB GPU uchun). Sig'maydi.

### Yechim

```mermaid
flowchart LR
    subgraph MEM["Unified memory ~10 GB"]
        BASE["Baza model<br/>Qwen3-14B 4-bit<br/>~8.0 GB<br/>(bir marta yuklanadi)"]
        subgraph AD["Adapter registry ~200 MB"]
            A1[jurist<br/>40 MB]
            A2[advocate<br/>40 MB]
            A3[prosecutor<br/>40 MB]
            A4[professor<br/>40 MB]
            A5[judge<br/>40 MB]
        end
        KV["KV-cache pool<br/>~1.5 GB"]
    end

    REQ[So'rov: agent=advocate] --> SW{Adapter<br/>almashtirish}
    SW -->|~50 ms| BASE
    A2 -.faol.-> BASE
    BASE --> OUT[Javob]
    BASE <--> KV
```

**Nima uchun ishlaydi:** LoRA adapteri — bu asosiy vazn matritsalariga qo'shiladigan kichik past-rangli qo'shimcha (`W' = W + BA`). Adapterni almashtirish = 40 MB ni ko'chirish, 8 GB ni emas. MLX da bu ~50 ms.

**Qo'shimcha foyda:** barcha rollar bir xil huquqiy bilimni bo'lishadi (baza da o'qitilgan), faqat *uslub va pozitsiya* farq qiladi. Bu izchillikni ta'minlaydi — advokat va prokuror bir xil qonunni turlicha *talqin* qiladi, turlicha *bilmaydi*.

Batafsil: [ADR-003](adr/ADR-003-single-base-multi-adapter.md), [`docs/02-hardware-runtime.md`](02-hardware-runtime.md)

---

## 5. Bilim qatlami: uch komponentli retrieval

Bitta vektor qidiruv yuridik matn uchun yetarli emas. Sabab: yuristlar **aniq raqam va atama** bilan qidiradi ("234-modda", "vindikatsiya da'vosi"), semantik qidiruv esa aniq mosliklarni ba'zan o'tkazib yuboradi.

```mermaid
flowchart TB
    Q[Savol] --> QE[Query expansion<br/>sinonim · rus/o'zbek · yuridik atama]

    QE --> V[Vektor qidiruv<br/>BGE-M3 · top-50]
    QE --> B[BM25 leksik<br/>top-50]

    V --> F[RRF birlashtirish]
    B --> F

    F --> VF{Versiya filtri}
    VF -->|amalda| RR[Reranker<br/>bge-reranker-v2-m3<br/>top-8]
    VF -->|bekor qilingan| X[Chiqarib tashlash]

    RR --> G[Hujjat grafi:<br/>havola qilingan normalarni<br/>ham qo'shish]
    G --> CTX[Yakuniy kontekst<br/>≤ 6k token]
```

**Versiya filtri** — yuridik RAG ni oddiy RAG dan ajratadigan narsa. Har bir chunk metadatasida:

```json
{
  "doc_id": "uz-fk-1996",
  "article": "234",
  "version": "2024-03-15",
  "valid_from": "2024-04-01",
  "valid_to": null,
  "status": "in_force",
  "supersedes": "2019-11-20",
  "amended_by": ["uz-zru-812-2023"]
}
```

Filtr `valid_to != null` bo'lgan chunklarni chiqaradi (agar foydalanuvchi aniq tarixiy sanani so'ramagan bo'lsa — "2021-yilda qanday edi?" degan savol uchun `as_of` parametri bor).

Batafsil: [`docs/04-rag.md`](04-rag.md)

---

## 6. Groundedness Gate

Javob foydalanuvchiga yetib borishidan oldingi oxirgi to'siq. Bu **model emas — deterministik tekshiruv**.

```mermaid
flowchart TB
    ANS[Judge javobi] --> SPLIT[Da'volarga ajratish<br/>claim extraction]
    SPLIT --> LOOP{Har bir da'vo}

    LOOP --> HAS{Iqtibos<br/>bormi?}
    HAS -->|yo'q| CLS{Da'vo turi}
    CLS -->|huquqiy| DROP[❌ Chiqarish]
    CLS -->|umumiy/mantiqiy| KEEP1[✓ Qoldirish]

    HAS -->|ha| EXIST{Hujjat va modda<br/>indeksda mavjudmi?}
    EXIST -->|yo'q| DROP
    EXIST -->|ha| SUPP{Iqtibos matni<br/>da'voni qo'llab-<br/>quvvatlaydimi?}
    SUPP -->|yo'q| FLAG[⚠ 'noaniq' deb belgilash]
    SUPP -->|ha| KEEP2[✓ Havola bilan]

    DROP --> ASM[Javobni qayta yig'ish]
    FLAG --> ASM
    KEEP1 --> ASM
    KEEP2 --> ASM

    ASM --> EMPTY{Huquqiy da'vo<br/>qoldimi?}
    EMPTY -->|yo'q| REFUSE["'Ishonchli javob<br/>topilmadi'"]
    EMPTY -->|ha| OUT[Yakuniy javob]
```

Uchinchi qadam ("iqtibos matni da'voni qo'llab-quvvatlaydimi?") — NLI modeli yoki baza modelning qisqa tekshirish chaqiruvi. Bu eng qimmat qadam, shuning uchun faqat huquqiy da'volarga qo'llaniladi.

**Muhim:** gate javobni *yaxshilamaydi* — u faqat **olib tashlaydi**. Bu ataylab. Gate hech qachon yangi matn generatsiya qilmaydi, aks holda u o'zi hallucination manbaiga aylanadi.

---

## 7. Ma'lumot modeli (asosiy entitilar)

```mermaid
erDiagram
    DOCUMENT ||--o{ VERSION : "tahrirlari"
    VERSION ||--o{ ARTICLE : "moddalari"
    ARTICLE ||--o{ CHUNK : "bo'laklari"
    ARTICLE ||--o{ REFERENCE : "havolalari"
    REFERENCE }o--|| ARTICLE : "ko'rsatadi"
    CHUNK ||--|| EMBEDDING : "vektori"
    CONSULTATION ||--o{ AGENT_TURN : "agent javoblari"
    AGENT_TURN ||--o{ CITATION : "iqtiboslari"
    CITATION }o--|| CHUNK : "manbasi"

    DOCUMENT {
        string doc_id PK
        string type "kodeks|qonun|PF|PQ|qaror"
        string title_uz
        string title_ru
        date   adopted_at
        string issuer
    }
    VERSION {
        string version_id PK
        date   valid_from
        date   valid_to "null = amalda"
        string status
        string source_url
    }
    ARTICLE {
        string article_id PK
        string number "234, 234-1"
        text   body_uz
        text   body_ru
    }
    CHUNK {
        string chunk_id PK
        text   content
        int    token_count
        json   metadata
    }
    CONSULTATION {
        string trace_id PK
        text   question
        string mode "simple|standard|complex"
        json   result
        int    latency_ms
    }
```

---

## 8. Modullar va mas'uliyat chegaralari

| Modul | Paket | Mas'uliyat | Bog'liqligi |
|-------|-------|------------|-------------|
| **Ingest** | `uzlegal.ingest` | Manbalardan yig'ish, normalizatsiya, versiyalash | — |
| **Index** | `uzlegal.index` | Chunking, embedding, BM25, graf qurish | `ingest` |
| **Retrieval** | `uzlegal.retrieval` | Gibrid qidiruv, rerank, versiya filtri | `index` |
| **Inference** | `uzlegal.inference` | Model yuklash, adapter almashtirish, generatsiya | — |
| **Agents** | `uzlegal.agents` | Rol promptlari, debate protokoli | `inference`, `retrieval` |
| **Orchestrator** | `uzlegal.orchestrator` | LangGraph grafi, router, judge, gate | `agents` |
| **Training** | `uzlegal.training` | Dataset qurish, LoRA trening, merge | `inference` |
| **Eval** | `uzlegal.eval` | Metrikalar, gold set, regressiya | hammasi |
| **API** | `uzlegal.api` | FastAPI, SSE, auth | `orchestrator` |
| **CLI** | `uzlegal.cli` | Terminal interfeysi | `orchestrator` |
| **MCP** | `uzlegal.mcp` | MCP server | `orchestrator` |

Qat'iy qoida: **`core` (ingest→orchestrator) hech qachon interfeys paketlarini import qilmaydi.** Bog'liqlik faqat bir yo'nalishda.

Kod strukturasi: [`docs/12-repo-structure.md`](12-repo-structure.md)

---

## 9. Kengaytirish nuqtalari

Tizim quyidagi joylarda kengaytiriladigan qilib loyihalangan:

| Nuqta | Interfeys | Misol foydalanish |
|-------|-----------|-------------------|
| Yangi manba | `SourceConnector` | Vazirlik sayti, xalqaro shartnomalar |
| Yangi agent roli | `AgentRole` + adapter | Notarius, soliq inspektori, mediator |
| Yangi retriever | `Retriever` | Graf-asosli qidiruv, SQL |
| Yangi interfeys | `core` ni chaqiradi | WhatsApp bot, VS Code kengaytmasi |
| Yangi runtime | `InferenceBackend` | vLLM, llama.cpp, bulut API |
| Yangi til | Til paketi | Qoraqalpoq, ingliz |

Yangi agent qo'shish uchun kod o'zgartirish shart emas — YAML konfiguratsiya + o'qitilgan adapter yetarli:

```yaml
# configs/agents/notary.yaml
role: notary
adapter: adapters/notary-v1
temperature: 0.2
system_prompt_file: prompts/notary.uz.md
retrieval_profile: notarial_acts
participates_in_debate: false
```

---

## 10. Nima *ataylab* qilinmagan

Senior dizaynda rad etilgan variantlarni yozib qo'yish muhim:

| Variant | Nima uchun rad etildi |
|---------|----------------------|
| Har rol uchun alohida to'liq model | 40 GB RAM kerak; rollar o'rtasida bilim nomuvofiqligi |
| Faqat fine-tuning, RAG siz | Qonun o'zgarganda qayta o'qitish kerak; iqtibos berib bo'lmaydi |
| Faqat RAG, fine-tuning siz | Rol uslublari zaif; o'zbek yuridik tili g'aliz |
| Agentlar erkin muloqoti (autonomous chat) | Konvergensiya kafolatlanmaydi, xarajat oldindan bilinmaydi |
| Bulut LLM (GPT/Claude) API asosida | Maxfiy ish ma'lumoti tashqariga chiqadi; oflayn ishlamaydi; qimmat |
| Javobni gate da qayta yozish | Gate ning o'zi hallucination manbaiga aylanadi |

---

## 11. Keyingi hujjat

→ [02 — Apparat va runtime](02-hardware-runtime.md)
