# ADR-006: RAG birinchi, fine-tuning ikkinchi

**Holat:** ✅ Qabul qilindi
**Sana:** 2026-08-08

## Kontekst

Modelga yuridik bilim qanday yetkaziladi? Ikki asosiy yo'l bor va ular tez-tez chalkashtiriladi.

## Ko'rib chiqilgan variantlar

### A — Bilim vaznlarda (fine-tuning asosiy)

Qonun matnini trening ma'lumotiga qo'shib, model uni "yodlashi".

| Ijobiy | Salbiy |
|--------|--------|
| Inference tez (retrieval yo'q) | **Iqtibos berib bo'lmaydi** — model qayerdan bilganini ayta olmaydi |
| Kontekst qisqa | **Qonun o'zgarsa qayta o'qitish** kerak |
| | **Hallucination yuqori** — model o'xshash normani "aralashtiradi" |
| | Versiyalash imkonsiz |
| | Yangilanish sikli: haftalar |

### B — Bilim indeksda (RAG asosiy) ← **tanlandi**

Model mulohaza yuritadi, faktni indeksdan oladi.

| Ijobiy | Salbiy |
|--------|--------|
| **Aniq iqtibos** — chunk ID gacha | Inference sekinroq (retrieval + uzun kontekst) |
| **Yangilanish soniyalarda** — indeks yangilanadi | Retrieval sifatiga bog'liq |
| **Versiyalash tabiiy** | Kontekst byudjeti cheklangan |
| Hallucination deterministik tekshiriladi | Ko'proq infratuzilma |
| Model qayta o'qitilmaydi | |

## Qaror

**RAG — bilim manbai. Fine-tuning — xatti-harakat manbai.**

Bu ajratish qat'iy va u butun arxitekturaning [T1 tamoyili](../01-architecture.md#1-dizayn-tamoyillari):

| Fine-tuning **o'rgatadi** | RAG **beradi** |
|---------------------------|----------------|
| Rol uslubi va pozitsiyasi | Qonun matni |
| O'zbek yuridik tili | Modda raqamlari |
| IRAC strukturasi | Amal qilish muddatlari |
| Iqtibos bilan ishlash odati | Sud amaliyoti |
| "Bilmayman" deyish | Doktrinal manbalar |
| Format rioyasi | Havolalar grafi |

### Nima uchun bu qaror hal qiluvchi

Yuridik AI dagi asosiy xavf — mavjud bo'lmagan modda keltirilishi. Variant A da bu xavfni **texnik jihatdan yo'q qilib bo'lmaydi** — model vazniga yozilgan bilimni tekshirish usuli yo'q.

Variant B da esa har bir iqtibos deterministik tekshiriladi:

```python
def check_citation(c: Citation, kb: KnowledgeBase) -> bool:
    doc = kb.get_document(c.doc_id)
    if doc is None: return False                # hallucination
    art = doc.get_article(c.article, as_of=c.version)
    if art is None: return False                # hallucination
    return art.status == "in_force"
```

Bu — model emas, oddiy funksiya. U 100% aniqlik bilan ishlaydi va uni aldab bo'lmaydi.

### Operatsion oqibat

Qonun o'zgarganda:

| Variant A | Variant B |
|-----------|-----------|
| Trening ma'lumotini yangilash | KB ni yangilash |
| Qayta o'qitish (~10 soat) | Indeksni yangilash (~5 daqiqa) |
| Qayta baholash (~2 soat) | Smoke eval (~5 daqiqa) |
| Reliz sikli | Avtomatik kunlik sync |
| **~2 kun** | **~10 daqiqa** |

O'zbekistonda qonunchilik faol o'zgaradi — bu farq yillik operatsion xarajatda hal qiluvchi.

## Amalga oshirish natijasi

Bosqichma-bosqich sifat:

| Bosqich | Aniqlik | Izoh |
|---------|---------|------|
| Baza model, RAG siz | ~25% | O'zbek qonunini bilmaydi |
| Baza model + RAG | **~70%** | ← Faza 2 oxirida ishlaydigan mahsulot |
| + umumiy SFT | ~78% | Yaxshi format, iqtibos odati |
| + rol LoRA | ~83% | Rol sifati |
| + ko'p-agentli debate | ~87% | Nizoli savollarda |
| + groundedness gate | ~87% (hallucination ≤1%) | Aniqlikni oshirmaydi, **xatoni kamaytiradi** |

Muhim jihat: **RAG yolg'iz o'zi qiymatning katta qismini beradi.** Shuning uchun u Faza 2 da, fine-tuning esa Faza 4 da. Agar loyiha vaqtdan qisilsa, RAG bilan to'xtash mumkin va mahsulot baribir foydali bo'ladi.

## Oqibatlari

### Ijobiy
- Iqtibos aniqligi arxitektura darajasida kafolatlanadi
- Qonun yangilanishi model relizidan ajratilgan
- Tarixiy so'rovlar (`as_of`) tabiiy ishlaydi
- Model kichikroq bo'lishi mumkin (bilim saqlash kerak emas)
- Faza 2 dan keyin demo qilinadigan mahsulot bor

### Salbiy

| Salbiy | Yumshatish |
|--------|------------|
| Retrieval sifati — yagona nosozlik nuqtasi | Gibrid qidiruv (3 usul), reranker, mustaqil baholash |
| Uzun kontekst → sekin | Prefix KV-cache, router, kontekst byudjeti 6k |
| Ko'proq infratuzilma | LanceDB — server kerak emas, local da fayl |
| Kontekstga sig'maydigan murakkab savollar | Graf kengaytmasi cheklangan; kerak bo'lsa ko'p bosqichli retrieval |

## Chegara holati: umumiy huquqiy bilim

Ba'zi bilim RAG ga tushmaydi: umumiy huquqiy tamoyillar (*lex specialis derogat legi generali*), yuridik atamalar ma'nosi, mantiqiy tuzilma.

Bu bilim **umumiy SFT bosqichida** modelga o'rgatiladi va u iqtibos talab qilmaydi — chunki bu fakt emas, **usul**. Groundedness gate bunday da'volarni "umumiy/mantiqiy" deb tasniflaydi va iqtibossiz o'tkazadi.
