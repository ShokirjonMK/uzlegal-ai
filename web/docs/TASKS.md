# Topshiriqlar roʻyxati

Tartib va qoidalar: [`CLAUDE.md`](../CLAUDE.md).

Holatlar: `reja` · `bajarilmoqda` · `testda` · `qaytarildi` · `yopildi`

| # | Topshiriq | Holat | QA | Sana |
|---|---|---|---|---|
| 1 | Loyiha skeleti va konfiguratsiya | yopildi | ✅ build | 2026-08-08 |
| 2 | Yadro: Claude klienti, promptlar, tiplar | yopildi | ✅ typecheck | 2026-08-08 |
| 3 | RAG: chunk, embedding, vektor qidiruv | yopildi | ✅ ingest + qidiruv sinovi | 2026-08-08 |
| 4 | Servislar: ask, analyze, generate, review | yopildi | ✅ typecheck + build | 2026-08-08 |
| 5 | Oʻzbek tili qatlami | yopildi | ✅ kod nuqtalari tekshirildi | 2026-08-08 |
| 6 | Yuzalar: Web, API, Telegram bot, CLI | yopildi | ✅ server + curl + getMe | 2026-08-08 |
| 7 | Oʻrnatish, typecheck, build, smoke-test | yopildi | ✅ | 2026-08-08 |
| 8 | Ish jarayoni qoidalari + git + diagramma | yopildi (8.3 qisman) | ✅ check + build | 2026-08-09 |
| 9 | Tizim auditi — nima qilish kerak | yopildi | ✅ 12/12 daʼvo tasdiqlandi | 2026-08-09 |
| 10–60 | Audit topilmalari — [`AUDIT.md`](AUDIT.md) | reja | — | — |
| 61 | Dizayn: aurora fon va zamonaviy koʻrinish | yopildi | ✅ check + build + kontrast | 2026-08-11 |
| 62 | Admin panel (`/admin`) — himoyalangan | yopildi | ✅ curl bilan 12 ta stsenariy | 2026-08-11 |
| 63 | Foydalanuvchi qulayligi (UX) — mavjud sahifalar | yopildi | ✅ 4 sahifa 200 + build | 2026-08-11 |
| 64 | Texnologiya asosi: Tailwind + shadcn/ui, MongoDB | yopildi | ✅ build + CSS qatlamlari | 2026-08-11 |
| 65 | Maʼlumot qatlami: kolleksiyalar + AI yozishmalari | yopildi | ✅ haqiqiy Mongo bilan | 2026-08-11 |
| 66 | Autentifikatsiya: uch usul | yopildi | ✅ uchalasi ham sinaldi | 2026-08-11 |
| 67 | Foydalanuvchi kabineti (`/kabinet`) | yopildi | ✅ tarix + hisob | 2026-08-11 |
| 68 | Docker: butun tizim bitta buyruq bilan | yopildi | ✅ 3 konteyner + qayta yuklash | 2026-08-11 |
| 69 | Lokal LLM (Ollama) — Anthropic kalitisiz ishlash | yopildi | ✅ check + build + haqiqiy javob | 2026-08-11 |
| 70 | Qidiruv korrektligi: #10a, #10b, #12, #14, #24, #52, #10 | yopildi | ✅ 26 ta tekshiruv + check + build | 2026-08-11 |

---

## #61 — Dizayn: aurora fon va zamonaviy koʻrinish

**Senior PM tahlili.** Foydalanuvchi saytning umumiy koʻrinishini
zamonaviylashtirish, jumladan `aurora-bg` skilidagi mesh gradient fon va uchta
pastel float blob (indigo / violet / cyan) qoʻshishni soʻradi. Cheklov aniq:
`ui-komponent` skilining token tizimidan chiqilmaydi — rang faqat `--`
oʻzgaruvchilar orqali beriladi, light va dark rejim ikkalasi ham toʻgʻri
ishlaydi, fokus konturi buzilmaydi.

**Diqqat talab qiladigan nuqta.** Hozir `body { background: var(--bg) }` —
xira boʻlmagan fon. Aurora qatlami `z-index: -1` da turadi, yaʼni body foni
uni butunlay bekitib qoʻyadi. Shu sababli body foni shaffofga oʻtkaziladi va
sahifa asosi `--aurora-base` zimmasiga oʻtadi; `--bg` esa aurora asosi bilan
bir xil qiymatga keltiriladi, aks holda `.nav` va `.composer` chetlarida
koʻrinadigan chegara paydo boʻladi.

| Qadam | Tavsif | Holat |
|---|---|---|
| 61.1 | `globals.css` ga aurora tokenlari (`:root` + dark bloki) | reja |
| 61.2 | `.aurora` qatlami, mesh gradient, 3 blob, keyframe animatsiya | reja |
| 61.3 | `AuroraBackground` komponenti + `layout.tsx` ga bir marta ulash | reja |
| 61.4 | Mavjud yuzalarni auroraga moslash (body shaffof, nav/karta/composer) | reja |
| 61.5 | `prefers-reduced-motion` va gorizontal skroll tekshiruvi | reja |

**Xavflar:**

- Aurora fon matn kontrastini pasaytirishi mumkin — asosiy matn `--aurora-base`
  ga nisbatan 4.5:1 boʻlishi tekshiriladi.
- Blob `filter: blur()` bilan — katta radius skrollni sekinlashtiradi.
- Dark rejim faqat shaffoflik bilan boshqariladi, yangi rang kiritilmaydi.

---

## Ish oʻrtasida oʻzgargan qamrov

Ish boshlangandan keyin foydalanuvchi texnologiya tanlovi kelishilmaganini
aytdi va yangi talab qoʻshdi — foydalanuvchi kabineti. Berilgan javoblar:

| Savol | Qaror |
|---|---|
| Admin himoyasi | Parol + Telegram tasdigʻi (ikki bosqich) |
| Ommaviy xabar | Avval sinov, keyin qoʻlda tasdiq |
| NoSQL baza | MongoDB — lokal |
| SPA | Next.js ichida, SPA sifatida |
| UI kutubxonasi | Tailwind + shadcn/ui, bosqichma-bosqich |
| Kabinet kirishi | Uchala usul: bot, widget, login+parol |
| AI yozishmalari | **Toʻliq saqlansin, cheklovsiz** |

Oxirgi qator boʻyicha eʼtiroz bildirildi (saqlanadigan narsa — odamlarning
ajrashish, qarz, ishdan boʻshatish kabi muammolari) va foydalanuvchi qarorini
tasdiqladi. Shunga koʻra `ai_calls` va `messages` da TTL indeksi yoʻq, matn
qisqartirilmaydi, avtomatik oʻchirish yoʻq. Bu ongli qaror, texnik nuqson emas.

---

## #62 — Admin panel (`/admin`)

**Senior PM tahlili.** Hozir admin faqat Telegram botda: `/stat`, `/tizim`,
`/baza`, `/xabar`. Web paneli yoʻq. Kerak: qonun bazasi holati va hujjatlarni
boshqarish (ingest va oʻchirish), statistika, tizim holati, ommaviy xabar.

**Foydalanuvchi qarori (soʻralgan va olingan):**

1. **Kirish himoyasi — parol + Telegram tasdigʻi (ikki bosqich).**
   `checkApiKey` naqshi rad etildi, sababi: kalit brauzer JS ga koʻrinadigan
   joyda yotadi, `/admin` HTML sahifasi himoyasiz qolar edi va `API_KEY` butun
   REST API ga umumiy kalit — admin huquqi ajratilmas edi.
   Yangi oqim: parol server tomonda timing-safe solishtiriladi → bot
   `ADMIN_CHAT_ID` ga 6 xonali kod yuboradi → kod tasdiqlangach `HttpOnly`,
   `Secure`, `SameSite=Strict` HMAC bilan imzolangan sessiya cookie beriladi.
   Sahifa server komponenti — cookie boʻlmasa panel HTML umuman chiqmaydi.
2. **Ommaviy xabar — avval sinov, keyin tasdiq.** Birinchi bosqichda xabar
   faqat adminning oʻziga yuboriladi; haqiqiy yuborish uchun qabul qiluvchilar
   soni qoʻlda yozib tasdiqlanadi.

**Zaxira yoʻli.** `TELEGRAM_BOT_TOKEN` yoki `ADMIN_CHAT_ID` sozlanmagan boʻlsa
ikkinchi bosqich oʻtkazib yuboriladi (parol yetarli) va panelda bu ochiq
yoziladi — aks holda bot ishlamay qolganda panelga umuman kirib boʻlmaydi.

| Qadam | Tavsif | Holat |
|---|---|---|
| 62.1 | Sozlamalar: `ADMIN_PASSWORD`, `ADMIN_SESSION_SECRET` | reja |
| 62.2 | Sessiya: HMAC imzo, muddat, `requireAdmin()` qorovuli | reja |
| 62.3 | Telegram yuborish yordamchisi (botdan mustaqil) | reja |
| 62.4 | `/api/admin/kirish`, `/kod`, `/chiqish` — kirish oqimi | reja |
| 62.5 | `/api/admin/holat` — tizim, korpus, statistika | reja |
| 62.6 | `/api/admin/baza` — hujjat roʻyxati, ingest, oʻchirish | reja |
| 62.7 | `/api/admin/xabar` — sinov va tasdiqlangan ommaviy yuborish | reja |
| 62.8 | `/admin` sahifasi: kirish formasi + panel | reja |

**Xavflar:**

- Parol sozlanmagan boʻlsa panel **butunlay yopiq** turadi (ochiq qolmaydi).
- Ingest uzoq davom etadi — soʻrov muddati (timeout) chegarasi bor.
- Hujjat oʻchirish va ommaviy xabar — qaytarib boʻlmaydigan amallar,
  ikkalasi ham qoʻlda yoziladigan tasdiq talab qiladi.
- Sessiya sirri jarayon xotirasida emas, `.env.local` da boʻlishi kerak, aks
  holda server qayta ishga tushganda sessiyalar uziladi.

---

## #63 — Foydalanuvchi qulayligi (UX)

**Senior PM tahlili.** Mavjud toʻrt sahifa (`/`, `/tahlil`, `/hujjat`,
`/qonunlar`) ishlaydi, lekin: yuklanish holatlari faqat tugma matni bilan
koʻrsatiladi, xato xabarlari xom (`Server xatosi (500)`), mobil koʻrinish
alohida sozlanmagan, klaviatura bilan yurish uchun oʻtkazib yuborish havolasi
yoʻq, natijani nusxalash faqat `/hujjat` da bor va u muvaffaqiyat haqida
hech narsa demaydi.

| Qadam | Tavsif | Holat |
|---|---|---|
| 63.1 | Xato xabarlarini insoniy shaklga keltirish (tarmoq, 401, 413, 500) | reja |
| 63.2 | Yuklanish holatlari: skelet, jonli holat matni, `aria-live` | reja |
| 63.3 | Mobil koʻrinish: nav, forma, kartalar, `kv` roʻyxati | reja |
| 63.4 | Klaviatura: oʻtkazib yuborish havolasi, fokus, tugma tartibi | reja |
| 63.5 | Natijani nusxalash va yuklab olish — barcha sahifalarda | reja |

**Xavflar:**

- Nusxalash `navigator.clipboard` ga tayanadi — HTTPS boʻlmagan muhitda
  ishlamaydi, zaxira yoʻl kerak.
- Model yoʻllari haqiqiy kalitsiz sinalmaydi (`ANTHROPIC_API_KEY` yoʻq), shu
  sababli tahlil va hujjat sahifalarida faqat xato yoʻli tekshiriladi.

---

## #8 — Ish jarayoni qoidalari + git + diagramma

**Senior PM tahlili.** Foydalanuvchi doimiy ish tartibini oʻrnatishni soʻradi:
raqamlash, TG hisobotlari, PM → Dev → QA → PM zanjiri. Bundan tashqari
loyihani git ga yuklash va tayyor holatni diagrammada koʻrsatish.

| Qadam | Tavsif | Holat |
|---|---|---|
| 8.1 | TG hisobot kanali (`scripts/tg-report.mts`) | yopildi |
| 8.2 | Ish qoidalari (`CLAUDE.md`) va roʻyxat (`docs/TASKS.md`) | yopildi |
| 8.3 | Git: lokal commit + GitHub push | qisman — avtorizatsiya oqimi ochildi |
| 8.4 | Holat tahlili va diagrammalar | yopildi |

**Xavflar:**

- GitHub push mustaqil bajarilmaydi — `gh auth login` foydalanuvchidan talab qilinadi.
- `ANTHROPIC_API_KEY` yoʻq: model yoʻllari kod darajasida tayyor, lekin
  haqiqiy javob bilan sinab koʻrilmagan.
- Qonun bazasida haqiqiy qonun matnlari yoʻq, faqat namuna fayl.

---

## #64 — Texnologiya asosi

Tailwind v4 va shadcn/ui uslubidagi komponentlar qoʻshildi, mavjud sof CSS
buzilmadi.

**Asosiy texnik nuqta — CSS qatlamlari.** Qatlamga solinmagan CSS qoidalar
har qanday `@layer` dan ustun turadi. Yaʼni eski `globals.css` ni shundayligicha
qoldirsak, undagi `button { background: … }` Tailwind ning `bg-…` utilitasini
bosib ketardi. Yechim: eski uslublar `legacy.css` ga koʻchirildi va `legacy`
qatlamiga solindi, tartib `theme → base → legacy → components → utilities`.
Tailwind ning `preflight` qismi ataylab ulanmadi — u `button`, `input`, `h1`
uslubini nolga tushirib, hozirgi toʻrt sahifani buzardi.

Tokenlar `@theme inline` orqali ulandi: `--color-primary: var(--accent)`.
Shuning uchun dark rejim oʻz-oʻzidan ishlaydi, `dark:` variantiga ehtiyoj yoʻq.

| Qadam | Tavsif | Holat |
|---|---|---|
| 64.1 | Tailwind v4 + PostCSS, preflightsiz | yopildi |
| 64.2 | `legacy.css` va qatlam tartibi | yopildi |
| 64.3 | Tokenlarni Tailwind mavzusiga ulash | yopildi |
| 64.4 | Komponentlar: button, card, input, badge, tabs, dialog | yopildi |
| 64.5 | MongoDB ulanish qatlami (dangasa, xatoga chidamli) | yopildi |

---

## #65 — Maʼlumot qatlami

Kolleksiyalar: `users`, `sessions`, `login_codes`, `conversations`,
`messages`, `ai_calls`, `events`.

TTL indeksi faqat `sessions` va `login_codes` da — bular xavfsizlik uchun
muddatli boʻlishi shart. `ai_calls` da TTL yoʻq (yuqoridagi qarorga koʻra).

Modelga qilingan har bir murojaat toʻliq yoziladi: kirish matni, chiqish
matni, model, chuqurlik, tokenlar, davomiylik, xatolik. Oqim (SSE) yoʻllari
uchun `tapStream` yordamchisi — hodisalarni oʻzgartirmasdan oʻtkazadi va
oxirida yozadi. Foydalanuvchi oqimni yarmida uzsa ham oʻsha paytgacha kelgan
matn saqlanadi.

**Mongo oʻchiq boʻlsa sayt toʻxtamaydi** — savol-javob, hujjat tahlili va
qonun bazasi Mongo ga bogʻliq emas; faqat kabinet va tarix oʻchadi.

---

## #66 — Autentifikatsiya

| Usul | Qanday ishlaydi |
|---|---|
| Telegram bot | Sayt 6 belgilik kod beradi → botga `/kirish KOD` → sessiya |
| Telegram widget | Telegram imzosi bot tokeni bilan server tomonda tekshiriladi |
| Pochta + parol | `scrypt` xeshi, har parol uchun alohida tuz |

Uchalasi ham bitta `users` yozuviga olib keladi. Telegram ID boʻyicha
bogʻlanish tufayli botdagi savollar kabinetda ham koʻrinadi — QA da xuddi
shu tasdiqlandi: bot orqali va widget orqali kirish bir xil hisobni berdi.

Bot kodi Mongo da saqlanadi (jarayon xotirasida emas), chunki bot alohida
jarayonda ishlashi mumkin (`npm run bot:poll`).

---

## #67 — Foydalanuvchi kabineti

`/kabinet` — hisob maʼlumoti va savollar tarixi (sayt va Telegram birga).
Tarix filtri har doim sessiyadan olinadi: soʻrov parametri bilan boshqa
birovning tarixini soʻrab boʻlmaydi.

---

## #68 — Docker: butun tizim bitta buyruq bilan

**Senior PM tahlili.** Foydalanuvchi kerakli dasturlarni oʻzim oʻrnatishimni
va butun tizim Docker orqali bitta buyruq bilan koʻtarilishini soʻradi.
Bu #65 dagi «MongoDB ni foydalanuvchi oʻrnatadi» qarzini ham yopadi.

**Nega Colima, Docker Desktop emas.** macOS da Docker Desktop — GUI ilova,
oʻrnatish uchun administrator paroli soʻraladi va uni buyruq satridan
bermayman. Colima esa Homebrew ning asosiy formulasi, CLI orqali ishlaydi va
uchinchi tomon tapiga ishonch talab qilmaydi (#65 da MongoDB tapi aynan shu
sababdan toʻxtagan edi). Natija bir xil: ishlaydigan Docker demoni.

| Qadam | Tavsif | Holat |
|---|---|---|
| 68.1 | Colima + Docker CLI + Compose oʻrnatish | yopildi |
| 68.2 | `Dockerfile` — Debian asosida, toʻliq `node_modules` | yopildi |
| 68.3 | `compose.yaml` — mongo + web + bot, sogʻliq tekshiruvi | yopildi |
| 68.4 | Doimiy hajmlar: mongo, korpus bazasi, qonun matnlari | yopildi |
| 68.5 | `npm run docker:*` buyruqlari va README | yopildi |

**`standalone` chiqishdan voz kechildi.** Next ning `output: "standalone"`
rejimi tasvirni kichraytiradi, lekin unda faqat web ishlaydi. Bizga esa
oʻsha tasvir ichida `npm run bot:poll`, `npm run ingest` va `npm run report`
ham kerak — ular `tsx` va `src/` ga tayanadi. Shuning uchun toʻliq
`node_modules` qoldirildi: tasvir kattaroq, lekin bot ham, CLI ham ishlaydi.

**Alpine emas, Debian.** `node:sqlite`, `unpdf` va `mammoth` tizim
kutubxonalariga tayanadi va musl da kutilmagan xatolar beradi.

**QA natijasi.** Uchala konteyner ham sogʻlom; bot `@uzlegalAiroBot` ga
ulandi; olti sahifa 200; Mongo `ulandi`; roʻyxatdan oʻtish, savol yozuvi va
kabinet tarixi ishladi; `docker compose down` + `up` dan keyin hisob ham,
yozishma ham, qonun bazasi ham joyida qoldi; konteyner ichida `ingest`
ishladi. QA maʼlumotlari keyin oʻchirildi.

**Xavflar:**

- `node:sqlite` va `unpdf` mahalliy modullar — Alpine (musl) da muammo
  chiqishi mumkin, shuning uchun Debian asosidagi tasvir olinadi.
- Konteyner ichida `MONGODB_URI` xost nomi `mongo` boʻladi, `127.0.0.1` emas.
- `.env.local` maxfiy — tasvirga koʻchirilmaydi, ishga tushganda beriladi.
- Colima birinchi ishga tushganda VM tasvirini yuklaydi, bu vaqt oladi.

---

## #69 — Lokal LLM (Ollama)

**Senior PM tahlili.** Foydalanuvchi lokal LLM koʻtarilishini soʻradi — yaʼni
tizim Anthropic kalitisiz ham javob bera olishi kerak. Hozir `claude.ts`
bevosita Anthropic SDK ga bogʻlangan, shuning uchun avval provayder qatlami
ajratiladi.

**Nega Ollama Docker ichida EMAS.** Mashina — Apple M4. Colima VM ichida
Metal GPU koʻrinmaydi, yaʼni konteynerdagi Ollama faqat protsessorda ishlaydi
va bir necha barobar sekin boʻladi. Shuning uchun Ollama xostda (mahalliy)
ishlaydi, konteynerlar unga `host.docker.internal` orqali murojaat qiladi.
Portativlik uchun `compose.yaml` ga ixtiyoriy konteyner varianti ham
qoʻshiladi (`llm` profili) — Linux serverda yoki GPU boʻlmagan muhitda
oʻsha ishlatiladi.

**Model:** `qwen2.5:7b-instruct` (~4.7 GB). Bu oʻlchamdagi modellar orasida
koʻp tilli sifati eng yaxshilaridan. `OLLAMA_MODEL` bilan almashtiriladi.

| Qadam | Tavsif | Holat |
|---|---|---|
| 69.1 | Provayder qatlami: `src/lib/llm/` (tiplar va yoʻnaltiruvchi) | yopildi |
| 69.2 | Anthropic provayderi — mavjud kod koʻchiriladi | yopildi |
| 69.3 | Ollama provayderi — `fetch`, NDJSON oqimi, JSON schema | yopildi |
| 69.4 | Sozlamalar: `AI_LOWYER_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | yopildi |
| 69.5 | Ollama oʻrnatish va model yuklash (7B va 14B) | yopildi |
| 69.6 | Compose: xost Ollama + ixtiyoriy konteyner profili | yopildi |
| 69.7 | Admin panelda faol provayder koʻrsatilishi | yopildi |

**QA natijasi (2026-yil 11-avgust).**

- `npm run check` — typecheck toza, 95 fayl oʻzbek matni linteridan oʻtdi.
- `npm run build` — 21 marshrut va 6 sahifa yigʻildi.
- Lokal model bilan haqiqiy savol-javob: `activeModel` →
  `ollama / qwen2.5:7b-instruct`, `pingOllama` ikkala modelni koʻrdi,
  RAG uchta boʻlak topdi, javob sitata bilan qaytdi
  (`[2] NAMUNA (haqiqiy qonun emas), 3-modda`) va ogohlantirish qoʻshildi.
  Vaqt: **117.8 soniya** — Claude ga qaraganda sezilarli sekin, buni
  foydalanuvchi his qiladi.

**Ochiq qolgani:** 7B va 14B ni bir xil savollar bilan yonma-yon
solishtirish (`.qa-taqqos.mts`) — har bir savol ~2 daqiqa olgani uchun
toʻliq oʻlchov alohida ish sifatida qilinadi. Standart hozircha 7B.

**Xavflar — ochiq aytiladi:**

- **Sifat pasayadi.** 7B model Claude Opus 5 bilan tenglasha olmaydi:
  oʻzbek tili gʻalizroq boʻladi, apostroflar buziladi, eng muhimi — modda
  raqamlarini oʻylab topish ehtimoli sezilarli darajada yuqori. CLAUDE.md
  buni aniq taqiqlaydi, shuning uchun RAG asosi saqlanadi va lokal
  provayder uchun tizim prompti qatʼiyroq qilinadi.
- Ollama da prompt keshlash va `effort` yoʻq — bu sozlamalar eʼtiborsiz
  qoldiriladi, xato tashlanmaydi.
- Ollama xostda ishlagani uchun `brew services` ga bogʻliq: mashina
  oʻchsa qayta ishga tushadi, lekin bu Docker nazoratidan tashqarida.
- Yangi kutubxona qoʻshilmaydi — Ollama bilan oddiy `fetch` orqali
  gaplashiladi (OpenAI SDK yoki boshqa paket olinmaydi).

---

## #70 — Qidiruv korrektligi (audit qarzlari)

Audit topilmalari orasidan javob toʻgʻriligiga bevosita taʼsir qiladiganlari.

| # | Audit | Nima qilindi |
|---|---|---|
| 70.1 | #10a | `foldForSearch` apostrofni ASCII `'` ga emas, BUTUNLAY olib tashlaydi. Ilgari apostrof soʻzni yorib yuborardi: `yoʻl` butunlay yoʻqolardi, `toʻlov` → `lov`, `boʻshatish` → `shatish`. |
| 70.2 | #10b | Shu bilan `oʻzbek` · `o'zbek` · `ozbek` — uchalasi bir xil qidiriladi. `detect.ts` lugʻati apostrofsiz yozuvga koʻchirildi. |
| 70.3 | #52 | Kalit soʻz mosligi qism satr emas, SOʻZ boʻyicha: `kor` endi `bekor` ichidan topilmaydi. |
| 70.4 | #12 | Oʻzbek qoʻshimchalari qirqiladi: `shartnomaning` va `shartnomasining` bitta oʻzakka tushadi, `qilish` va `qilinishi` ham. |
| 70.5 | #24 | Soʻrov tokenlari takrorsiz va 32 ta bilan cheklangan. 500 soʻzli soʻrov: ilgari 15.5 s bloklangan event loop, hozir **5 ms**. |
| 70.6 | #14 | Baza boshqa embedder bilan yozilgan boʻlsa ogohlantirish chiqadi (ilgari jimgina buzilardi). Lokal embedder nomi `local:hashed-ngrams-v2`. |
| 70.7 | #10 | `RAG_MIN_SCORE` qayta kalibrlandi: **0.3 → 0.4**. |

**Kalibrlash oʻlchovi.** Mos savollar eng yuqori bali `0.468` va `0.587`;
bazada javobi YOʻQ savollar `0.347` va `0.263`. Boʻshliq oʻrtasi — 0.4.
Endi bazada javobi yoʻq savol **boʻsh natija** qaytaradi (ilgari oltita
begona boʻlak "huquqiy asos" sifatida modelga uzatilardi).

**Kalit soʻz manbasi oʻzgardi.** Endi `chunks.folded` ustuni emas, boʻlak
matnining oʻzi tokenlashtiriladi (obyektga bogʻlab keshlanadi). Sabab:
ustun baza yozilgan paytdagi `foldForSearch` bilan hisoblangan va funksiya
oʻzgarsa jimgina eskiradi.

**Sitata tekshiruvi (`rag/verify.ts`)** — allaqachon `ask.ts` ga ulangan
ekan, ishlashi tasdiqlandi: manbadagi moddaga ogohlantirish chiqmaydi,
`234-modda` kabi toʻqilgan havolaga chiqadi.

**QA:** `.qa-qidiruv.mts` — 26 ta tekshiruv, hammasi oʻtdi. `npm run check`
toza (95 fayl), `npm run build` toza. Korpus qayta yuklandi.

**Ochiq qolgani — ochiq aytiladi:** kalibrlash olti boʻlakli NAMUNA
korpusida va xesh embedderda olingan. Haqiqiy qonun matnlari yuklangach
yoki Voyage ga oʻtilgach chegara QAYTA oʻlchanishi shart.

---

## Yopilmagan qarzlar

Bular alohida topshiriq sifatida ochiladi:

| # | Nima | Nega kerak |
|---|---|---|
| — | Model yoʻllarini haqiqiy kalit bilan uchdan-uchgacha sinash | Hozir faqat kalitsiz xato yoʻli tekshirilgan |
| — | Haqiqiy qonun matnlarini bazaga yuklash (lex.uz) | Hozir namuna fayl; havolalar ishonchsiz |
| — | Voyage AI embedding ga oʻtish | Lokal embedder sifati past |
| — | Avtomatik testlar (`node --test`) | Hozir tekshiruv qoʻlda |
| — | Serverless uchun Telegram navbati | Webhook hozir doimiy server talab qiladi |
| — | Eski 4 sahifani Tailwind ga koʻchirish | Hozir `legacy` qatlamida ishlayapti |
| — | Statistikani SQLite dan Mongo ga birlashtirish | Hozir ikki manba yonma-yon |
| — | Parol tiklash (pochta orqali) | SMTP xizmati kerak |
