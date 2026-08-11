---
name: rag-qonun
description: Qonun bazasi (RAG) — modda chegarasida boʻlaklash, gibrid qidiruv (vektor + kalit soʻz), node:sqlite doʻkon, Voyage/lokal embedding, sitatalar. Use when touching src/lib/rag/, running ingest, debugging search quality, changing chunking or embeddings, or when answers cite wrong/missing articles.
---

# Qonun bazasi (RAG)

`src/lib/rag/` — beshta modul: `chunk` → `embeddings` → `store` → `retrieve`,
`ingest` ularni bogʻlaydi.

## Boʻlaklash modda chegarasida boʻladi

`chunkLegalText()` "har 500 belgida kes" qilmaydi. Sabab: javobda
*"Mehnat kodeksining 173-moddasi"* deb aniq havola berish uchun boʻlak
**bitta moddaga** toʻgʻri kelishi kerak.

- Modda sarlavhasi **satr boshida** turishi shart. Naqshlar:
  `173-modda.`, `173-модда`, `Статья 173.`, `Article 173.`
- `MAX_CHARS = 4000` — undan uzun modda qism/band chegarasida boʻlinadi.
- `MIN_CHARS = 400` — undan kichik boʻlakka boʻlinmaydi.
- Modda topilmasa — paragraf boʻyicha zaxira yoʻl.

**Sifat muammosi koʻpincha shu yerdan boshlanadi.** Qidiruv notoʻgʻri natija
bersa, avval boʻlaklashni tekshiring: PDF dan kelgan matnda sarlavha satr
oʻrtasiga tushib qolgan boʻlishi mumkin — u holda butun kodeks bitta ulkan
boʻlak boʻlib qoladi.

```bash
npm run ingest -- --help
```

## Gibrid qidiruv: 0.7 vektor + 0.3 kalit soʻz

Ikkalasi ham kerak, va nega — muhim:

- **Vektor** — foydalanuvchi *"ishdan boʻshatish"* deydi, matnda
  *"mehnat shartnomasini bekor qilish"* yozilgan. Semantik moslik topadi.
- **Kalit soʻz** — foydalanuvchi *"173-modda"* deydi. Bu yerda aniq moslik
  kerak, vektor buni ishonchli topmaydi.

`extractArticleRefs()` soʻrovdan modda raqamini ajratadi (`173-modda`,
`статья 173`, `article 173`).

Nisbatni (`VECTOR_WEIGHT` / `KEYWORD_WEIGHT`) oʻzgartirishdan oldin
**ikkala turdagi** soʻrov bilan sinang — birini yaxshilash ikkinchisini
buzadi.

Standart: `topK = 8`, `minScore = 0.05`.

## Taqqoslash — har doim `foldForSearch()`

```ts
import { foldForSearch } from "@/lib/uz/orthography";
```

Har qanday apostrofni ASCII `'` ga keltiradi va kichik harfga oʻtkazadi.
`StoredChunk.folded` — shu koʻrinishdagi matn, kalit soʻz qidiruvi faqat
shundan foydalanadi.

Yangi qidiruv mantigʻi yozsangiz, xom `text` boʻyicha taqqoslamang —
`oʻzbek` va `o'zbek` mos kelmaydi.

`STOPWORDS` — uch tilda (uz/ru/en). 3 belgidan qisqa soʻzlar ham tashlanadi.

## Doʻkon: `node:sqlite`, tashqi baza yoʻq

- Node 22.5+ tarkibidagi `DatabaseSync`. `data/corpus.db`.
- Vektorlar BLOB sifatida saqlanadi, **qidiruv xotirada** bajariladi
  (`loadAll()` → cosine).
- ~50 000 boʻlakkacha yetarli tez. Undan katta korpus uchun
  PostgreSQL + pgvector — interfeys oʻzgarmaydi.

`upsertChunks()` idempotent — bir hujjatni qayta ingest qilish dublikat
yaratmaydi. Hujjatni almashtirish uchun `deleteDocument()` keyin qayta ingest.

## Embedding: ikki provayder

| Provayder | Qachon |
|---|---|
| `voyage` | Asosiy. Kalit kerak (`.env.local`). Sifatli. |
| `local` | Zaxira. Belgi n-grammalarini xeshlaydi, `LOCAL_DIM = 512`. |

Lokal variant oʻzbekchada yomon emas — qoʻshimchalar koʻp oʻzgargani uchun
n-gramma yondashuvi morfologiyaga chidamli.

**Provayderni almashtirsangiz butun korpusni qayta ingest qiling.** Turli
oʻlchamdagi vektorlar bir bazada — jimgina notoʻgʻri natija beradi.

## Javobda sitata

```ts
import { toCitations } from "@/lib/rag/retrieve";
const citations = toCitations(chunks, 240);
```

`CLAUDE.md`: **qonun moddalari oʻylab topilmaydi.** Baza boʻsh boʻlsa
(`isEmpty()`) — buni foydalanuvchiga ochiq ayting, taxminiy javob bermang.

## Tekshirish

QA majburiy: namuna soʻrov bilan qidiruv natijasini koʻzdan kechirish.

```bash
npm run cli -- search "ishdan boʻshatish tartibi"
npm run cli -- search "173-modda"          # kalit soʻz yoʻli
```

Ikkalasi ham mos natija berishi kerak — biri ishlab, ikkinchisi ishlamasa,
gibrid nisbat yoki `foldForSearch` da muammo bor.
