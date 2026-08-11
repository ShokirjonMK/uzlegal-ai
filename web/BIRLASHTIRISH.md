# Birlashtirish holati — `web/` qobigʻi

Bu papka avval mustaqil loyiha edi (`ai-lowyer`): Next.js 15 asosidagi web,
REST API, Telegram bot va CLI. Endi u **uzlegal-ai yadrosining qobigʻi**.

## Nima oʻzgardi

**Savol-javob yadroga oʻtdi.** `src/lib/services/ask.ts` endi Claude SDK ni
chaqirmaydi — u `POST /v1/consult` va `POST /v1/consult/stream` ga murojaat
qiladi. Qidiruv, agentlar, groundedness gate va iqtiboslar yadroda.

Yangi fayl: `src/lib/uzlegal/client.ts` — yadro mijozi.
Sozlamalar: `UZLEGAL_API_URL` (standart `http://localhost:8080`),
`UZLEGAL_API_KEY`, `UZLEGAL_MODE`, `UZLEGAL_TIMEOUT_MS`.

**Hodisa shakli oʻzgarmadi.** `StreamEvent` oʻsha-oʻsha, shuning uchun web
sahifalari, Telegram bot, REST marshrutlari va CLI tegilmadi.

**Bitta muhim farq:** `/v1/consult/stream` — token oqimi emas, **bosqich**
oqimi. Yakuniy javob oqim oxirida bir marta keladi, chunki gate uni toʻliq
matn ustida tekshiradi. Yaʼni foydalanuvchi endi harf-harf yozilishini
koʻrmaydi; uning oʻrniga «Yurist javob tayyorlamoqda…» kabi bosqich
nomlari koʻrsatiladi.

## Nima OʻZGARMADI — va bu ochiq savol

Uchta xizmat hali ham Anthropic ni **toʻgʻridan-toʻgʻri** chaqiradi:

| Fayl | Nima qiladi | Nega koʻchirilmadi |
|---|---|---|
| `services/analyze.ts` | Hujjat tahlili, xavflar roʻyxati | Yadroda `/v1/analyze/document` bor, lekin javob sxemasi qobiqnikidan boshqa — moslashtirish alohida ish |
| `services/generate.ts` | Hujjat generatsiyasi (shartnoma, daʼvo arizasi) | Yadroda hujjat YARATADIGAN endpoint yoʻq |
| `services/review.ts` | Shartnomani nuqta-nuqta tekshirish | Yadroda mos endpoint yoʻq |

Shuning uchun `ANTHROPIC_API_KEY` hozircha kerak — lekin faqat shu uchta
yoʻl uchun. Savol-javob usiz ham ishlaydi.

Shu bilan birga qobiqda **oʻz RAG qatlami** ham qolgan (`src/lib/rag/`):
`/api/search` va `/qonunlar` sahifasi unga tayanadi. Ikkita qidiruv
yonma-yon turishi uzoq muddatda notoʻgʻri — qaysi biri qolishi hal
qilinishi kerak.

## Koʻchirilmagan fayllar

- `.git/` — eski tarix. Kerak boʻlsa `~/ai-lowyer` da turibdi.
- `node_modules/` — `npm install` bilan tiklanadi.
- `.env.local` — **maxfiy maʼlumot** (bot tokeni, admin paroli). Ataylab
  koʻchirilmadi. Kerak boʻlsa oʻzingiz nusxalang:
  `cp ~/ai-lowyer/.env.local web/.env.local`

## Tekshirilgan va tekshirilmagan

Tekshirilgan: `tsc --noEmit` toza, oʻzbek matni linteri toza.

**Tekshirilmagan:** yadro bilan haqiqiy soʻrov. Python serveri ishga
tushirilmadi (ogʻir ish taqiqlangan edi), shuning uchun `/v1/consult`
javobining haqiqiy shakli faqat `src/uzlegal/core.py` dagi modelga qarab
yozildi. Birinchi haqiqiy soʻrovda maydon nomlari tekshirilishi shart.
