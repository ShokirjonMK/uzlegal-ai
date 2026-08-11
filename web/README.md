# AI Lawyer

Oʻzbekiston Respublikasi qonunchiligi boʻyicha yuridik yordamchi.
Bitta loyihada toʻrtta yuza: **web ilova**, **REST API**, **Telegram bot** va **CLI** —
hammasi bitta `src/lib/` yadroni ulashadi.

## Nima qila oladi

| Imkoniyat | Tavsif |
|---|---|
| **Savol-javob** | Huquqiy savolga javob. Qonun bazasidan topilgan moddalarga havola bilan. |
| **Qonun bazasi (RAG)** | Qonun matnlaridan modda darajasida qidiruv — vektor + kalit soʻz (gibrid). |
| **Hujjat tahlili** | Shartnomadagi xavflarni, nomutanosib shartlarni va yetishmayotgan bandlarni topadi. |
| **Hujjat generatsiyasi** | Shartnoma, ariza, ishonchnoma va boshqa loyihalar. `.docx` sifatida yuklab olish. |
| **Qoʻshimcha tekshiruvlar** | 10 ta majburiy talab boʻyicha nuqta-ma-nuqta baholash va umumiy ball. |

Oʻzbek (lotin va kirill), rus va ingliz tillarini tushunadi va savol qaysi tilda
berilsa, shu tilda javob beradi.

## Oʻzbek tili sifati

Loyihaning alohida qatlami (`src/lib/uz/`) shunga bagʻishlangan:

- **Orfografiya** — `oʻ`/`gʻ` uchun U+02BB va tutuq belgisi uchun U+02BC
  avtomatik qoʻyiladi. Foydalanuvchi `'`, `'`, `` ` `` yozsa ham toʻgʻrilanadi.
- **Yozuv** — lotin ↔ kirill translitteratsiyasi; javob savol yozuviga moslashadi.
- **Atamalar** — yuridik atamalar lugʻati promptga kiritiladi, ruscha kalkalar
  (`dogovor`, `isk`, `zayavleniye`) oʻrniga rasmiy atamalar ishlatiladi.
- **Uslub qoidalari** — sana, summa va qonunga havola formati, gap qurilishi,
  tez-tez uchraydigan imlo xatolari — hammasi tizim promptida qatʼiy koʻrsatilgan.
- **Linter** — `npm run lint:uz` aralash yozuvli soʻzlarni (`terminалда`) va <!-- lint-uz-ignore: ataylab yomon misol -->
  notoʻgʻri apostroflarni topadi. Bu xatolarni koʻz bilan ilgʻab boʻlmaydi.

## Ishga tushirish

### Docker orqali — butun tizim bitta buyruq bilan

Web, Telegram bot va MongoDB birga koʻtariladi. Hech narsa alohida
oʻrnatilmaydi.

```bash
cp .env.example .env.local     # va ANTHROPIC_API_KEY ni toʻldiring
npm run docker:up              # http://localhost:3000
```

| Buyruq | Vazifasi |
|---|---|
| `npm run docker:up` | Koʻtaradi (kerak boʻlsa tasvirni qayta quradi) |
| `npm run docker:holat` | Konteynerlar holati |
| `npm run docker:logs` | Jurnalni kuzatish |
| `npm run docker:ingest` | Qonun bazasini toʻldirish (konteyner ichida) |
| `npm run docker:down` | Toʻxtatish |

Maʼlumot yoʻqolmaydi: MongoDB alohida hajmda, qonun bazasi va matnlar esa
`./data/` papkasida — konteyner oʻchsa ham joyida qoladi.

macOS da Docker demoni kerak. Docker Desktop oʻrniga Colima ham boʻladi
(GUI talab qilmaydi):

```bash
brew install colima docker docker-compose
mkdir -p ~/.docker/cli-plugins
ln -sfn "$(brew --prefix)/opt/docker-compose/bin/docker-compose" ~/.docker/cli-plugins/docker-compose
colima start --cpu 4 --memory 6 --disk 30
```

### Dockersiz — bevosita

```bash
npm install
cp .env.example .env.local     # va ANTHROPIC_API_KEY ni toʻldiring
npm run dev                    # http://localhost:3000
```

Bu holda MongoDB ni oʻzingiz koʻtarasiz (`MONGODB_URI` sozlanmagan boʻlsa
shaxsiy kabinet va yozishmalar tarixi oʻchadi, qolgan hammasi ishlayveradi).

### Majburiy sozlama

`.env.local` faylida faqat bitta narsa majburiy:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Kalitni <https://console.anthropic.com> dan olasiz. Qolgan sozlamalar ixtiyoriy —
`.env.example` da har biri izohlangan.

## Qonun bazasini toʻldirish

Baza boʻsh boʻlsa ham tizim ishlaydi, lekin javoblarda modda havolalari boʻlmaydi
va model buni ochiq aytadi. Toʻldirish uchun:

1. Qonun matnlarini <https://lex.uz> dan yuklab oling (`.txt`, `.pdf`, `.docx`, `.html`).
2. `data/corpus/` papkasiga joylang.
3. `npm run ingest`

**Fayl nomi hujjat nomiga aylanadi** va har bir havolada koʻrinadi, shuning uchun
aniq nomlang:

```
data/corpus/
  Mehnat kodeksi.txt
  Fuqarolik kodeksi__2024-01-15.txt              # tahrir sanasi bilan
  Oila kodeksi__https---lex.uz-docs-104723.txt   # manba havolasi bilan
```

Matn modda chegarasida boʻlaklarga ajratiladi (`173-modda.`, `Статья 173.`),
shuning uchun javobda aynan kerakli moddaga havola beriladi.

> `data/corpus/NAMUNA (haqiqiy qonun emas).txt` — bu tizimni sinash uchun
> namuna fayl. Haqiqiy qonun EMAS. Ishlatishdan oldin oʻchiring.

### Embedding provayderi

| Provayder | Sifat | Sozlash |
|---|---|---|
| `voyage` | Yaxshi — semantik qidiruv | `VOYAGE_API_KEY` ni qoʻshing ([voyageai.com](https://docs.voyageai.com)) |
| `local` | Past — faqat leksik oʻxshashlik | Standart. Tashqi xizmat kerak emas. |

Ishlab chiqarish uchun `voyage` tavsiya etiladi. Provayder oʻzgarsa, bazani
qayta yuklash kerak (`npm run ingest`) — vektorlar mos kelmaydi.

## Telegram bot

```bash
npm run bot:poll        # lokal ishlab chiqish — ommaviy manzil kerak emas
```

Ishlab chiqarishda webhook:

```bash
# .env.local da PUBLIC_BASE_URL va TELEGRAM_WEBHOOK_SECRET ni toʻldiring
npm run build && npm run start
npm run bot:set-webhook
```

**Bot buyruqlari:** `/start`, `/yordam`, `/hujjat`, `/baza`, `/tozalash`, `/id`

**Admin buyruqlari** (`ADMIN_CHAT_ID` da koʻrsatilgan chat uchun):

| Buyruq | Tavsif |
|---|---|
| `/stat` | Oxirgi 24 soat statistikasi |
| `/stat 7` | Oxirgi 7 kun |
| `/tizim` | Model, baza va sozlamalar holati |
| `/xabar <matn>` | Barcha foydalanuvchilarga ommaviy xabar |

Admin, bundan tashqari, **yangi foydalanuvchi** qoʻshilganda va **xatolik**
yuz berganda avtomatik bildirishnoma oladi.

> Webhook rejimida update darhol qabul qilinadi va fon rejimida ishlanadi
> (Telegram 60 soniya kutadi, model esa undan uzoq ishlashi mumkin). Bu doimiy
> ishlaydigan Node serveri uchun. Serverless muhitda navbat (queue) kerak boʻladi.

## CLI

```bash
npm run cli -- yordam                    # buyruqlar roʻyxati
npm run cli -- holat                     # sozlamalar holati
npm run cli -- yukla                     # qonun bazasini toʻldirish
npm run cli -- baza                      # baza holati
npm run cli -- soragan "Sinov muddati necha oy?"
npm run cli -- qidir "ishdan boʻshatish"          # modelsiz, tez
npm run cli -- tahlil shartnoma.pdf
npm run cli -- tekshir shartnoma.docx
npm run cli -- yarat ijara-shartnomasi "Toshkent, 2 xonali, oyiga 5 mln" --out ijara.docx
```

Parametrlar: `--out <fayl>`, `--k <son>`, `--til <uz|ru|en>`, `--json`, `--tez`.

## REST API

Barcha marshrutlar `Content-Type: application/json` qabul qiladi.
`API_KEY` sozlangan boʻlsa, `Authorization: Bearer <kalit>` talab qilinadi.

| Marshrut | Tavsif |
|---|---|
| `POST /api/chat` | Savol-javob, SSE oqimi (`status`, `citations`, `delta`, `done`, `error`) |
| `POST /api/ask` | Savol-javob, oddiy JSON javob |
| `POST /api/analyze` | Hujjat tahlili (`multipart/form-data` yoki JSON) |
| `POST /api/review` | Majburiy talablar boʻyicha tekshiruv |
| `POST /api/generate` | Hujjat generatsiyasi. `?format=json\|sse\|docx` |
| `GET /api/generate` | Shablonlar roʻyxati |
| `GET /api/search?q=…&k=8` | Bazadan toʻgʻridan-toʻgʻri qidiruv (modelsiz) |
| `GET /api/health` | Tizim holati |
| `POST /api/telegram` | Telegram webhook |

```bash
curl -X POST http://localhost:3000/api/ask \
  -H 'content-type: application/json' \
  -d '{"question":"Sinov muddati necha oy boʻlishi mumkin?"}'

curl -X POST http://localhost:3000/api/analyze \
  -F file=@shartnoma.pdf -F perspective=ijarachi

curl -X POST 'http://localhost:3000/api/generate?format=docx' \
  -H 'content-type: application/json' \
  -d '{"template":"ijara-shartnomasi","details":"Toshkent, 2 xonali, oyiga 5 mln soʻm, 1 yil"}' \
  -o ijara.docx
```

## Loyiha tuzilishi

```
src/
  app/                    Next.js App Router
    page.tsx              Savol-javob (chat)
    tahlil/               Hujjat tahlili va tekshiruv
    hujjat/               Hujjat generatsiyasi
    qonunlar/             Qonun bazasidan qidiruv
    api/                  REST marshrutlar + Telegram webhook
  lib/
    claude.ts             Claude API qatlami (streaming, JSON, refusal)
    prompts.ts            Tizim promptlari
    config.ts             Muhit sozlamalari
    analytics.ts          Foydalanish statistikasi (SQLite)
    bot.ts                Telegram bot
    uz/                   ⭐ Oʻzbek tili qatlami
      orthography.ts        Apostroflar, translitteratsiya
      detect.ts             Til va yozuvni aniqlash
      glossary.ts           Yuridik atamalar lugʻati
      style.ts              Yozish qoidalari (promptga kiradi)
      stream-polish.ts      Streaming paytida imlo tuzatish
    rag/                  Qonun bazasi
      chunk.ts              Modda chegarasida boʻlish
      embeddings.ts         Voyage AI / lokal zaxira
      store.ts              node:sqlite vektor doʻkon
      retrieve.ts           Gibrid qidiruv
      ingest.ts             Yuklash quvuri
    services/             ask · analyze · generate · review
    util/                 extract (pdf/docx) · docx · sse
  cli.ts                  Buyruqlar qatori
scripts/
  lint-uz.mts             Oʻzbek matni linteri
  bot-poll.ts             Bot (polling)
  set-webhook.ts          Webhook sozlash
data/corpus/              Qonun matnlari (siz toʻldirasiz)
```

## Tekshiruv

```bash
npm run check        # typecheck + oʻzbek matni linteri
npm run build
```

## Texnik yechimlar haqida

**Nega `node:sqlite`?** Vektor bazasi uchun tashqi xizmat (Postgres + pgvector,
Pinecone) oʻrnatish shart emas — Node 22.5+ tarkibidagi SQLite yetarli.
50 000 gacha boʻlakda qidiruv tez ishlaydi. Kattaroq korpus uchun `store.ts`
interfeysini saqlab, ichini pgvector bilan almashtirish mumkin.

**Nega modda chegarasida boʻlish?** "Har 500 belgida kes" usuli yuridik matnda
javobda aniq havola berishni imkonsiz qiladi. Modda boʻyicha boʻlinganda
"Mehnat kodeksining 173-moddasi" deb aniq koʻrsatish mumkin.

**Nega gibrid qidiruv?** Foydalanuvchi "ishdan boʻshatish" desa, matnda
"mehnat shartnomasini bekor qilish" yozilgan boʻlishi mumkin — buni vektor
topadi. "173-modda" deb soʻrasa — aniq moslik kerak, buni kalit soʻz topadi.

**Nega streaming paytida alohida imlo tuzatgich?** Apostrof oqim boʻlaklari
chegarasida ikkiga boʻlinishi mumkin (`...boʻ + `'lim...`). Har bir boʻlakni
alohida tuzatsak, `oʻ` oʻrniga `oʼ` chiqadi.

## Ogohlantirish

AI Lawyer advokat emas va yuridik yordam koʻrsatmaydi. Javoblar maʼlumot uchun
beriladi. Model qonun moddalarini oʻylab topmaslik uchun qatʼiy cheklangan —
faqat bazadagi matnlarga havola qiladi va baza boʻsh boʻlsa buni ochiq aytadi.
Shunga qaramay, har bir havolani <https://lex.uz> dagi amaldagi tahrir bilan
solishtirish shart. Aniq ish boʻyicha advokatga murojaat qiling.
