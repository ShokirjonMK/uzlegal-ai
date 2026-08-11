# Tizim auditi — nima qilish kerak

**Sana:** 2026-yil 9-avgust · **Topshiriq:** #9

Besh mustaqil auditor (xavfsizlik, korrektlik, ishlab chiqarish, RAG sifati,
oʻzbek tili va UX) kod bazasini tekshirdi. Har bir muhim daʼvo keyin
`scripts/verify-audit.mts` orqali kod ustida amalda sinaldi — **12 tadan 12 tasi
tasdiqlandi, birortasi rad etilmadi**.

Tekshirish: `npm run verify:audit`

---

## Xulosa

Loyiha **texnik jihatdan yaxshi qurilgan, lekin ishlab chiqarishga tayyor emas**.

Eng jiddiy topilma ochiq gapirganda shu: **hozirgi holatda tizim ishonchli
koʻrinadigan, lekin notoʻgʻri javob berishi mumkin.** Uchta mustaqil nuqson
birlashib shu natijani beradi:

1. Qidiruv hech qachon "topilmadi" demaydi — har savolga 8 ta boʻlak qaytaradi;
2. Model esa qatʼiy koʻrsatma bilan **faqat shu boʻlaklardan** javob yozadi;
3. Boʻlaklar orasida matn ichidagi havoladan yasalgan **soxta moddalar** boʻlishi mumkin.

Yaʼni foydalanuvchi mehnat huquqi haqida soʻrasa, bazada esa faqat Soliq
kodeksi boʻlsa — tizim "menda bu boʻyicha norma yoʻq" demaydi, balki soliq
moddalariga havola bilan mehnat savoliga javob yozadi.

Bu — loyihaning butun mohiyatiga zid (README: "model faqat haqiqiy qonun
matnidan javob beradi").

---

## P0 — Javob toʻgʻriligi (bularsiz chiqarib boʻlmaydi)

| # | Muammo | Fayl | Tekshirildi |
|---|---|---|---|
| **10a** | **⚠️ Apostrof qidiruv tokenlarini parchalaydi — eng ogʻir nuqson.** `tokens()` harf boʻlmagan belgilar boʻyicha boʻladi, apostrof esa ajratuvchi. Natijada: `yoʻl` → **butunlay yoʻqoladi**, `toʻlov` → `lov`, `boʻshatish` → `shatish`, `koʻchmas` → `chmas`. Eng koʻp uchraydigan oʻzbek yuridik atamalari qidiruvda yarim yoki umuman ishlamaydi. | `retrieve.ts:28` | ✅ |
| **10b** | **`foldForSearch` oʻz izohidagi vaʼdani bajarmaydi.** Izohda «foydalanuvchi "ozbek" deb yozsa ham topilsin» deyilgan, lekin `oʻzbek` → `o'zbek`, `ozbek` → `ozbek` — mos kelmaydi. Apostrofni butunlay olib tashlash **10a** ni ham hal qiladi. | `orthography.ts:89` | ✅ |
| **10** | **Qidiruv hech qachon boʻsh natija qaytarmaydi.** `minScore = 0.05`, lekin butunlay begona matn ham 0.29–0.41 ball oladi. `sourcesBlock` dagi "baza boʻsh" tarmogʻi hech qachon ishlamaydi. | `retrieve.ts:94` | ✅ |
| **11** | **Matn ichidagi havola soxta modda yasaydi.** `"173-moddada nazarda tutilgan tartibda…"` satr boshiga tushsa, u sarlavha deb oʻqiladi va bazaga soxta "173-modda" tushadi. Modda raqami boʻyicha `+0.5` bonus aynan shuni koʻtaradi. | `chunk.ts:27` | ✅ 2 ta soxta blok |
| **12** | **Oʻzbek morfologiyasi ishlamaydi.** `includes()` bilan qidiruv: `"shartnomaning"` soʻrovi `"shartnomasining"` matnida topilmaydi. Foydalanuvchilar aynan qoʻshimchali yozadi. | `retrieve.ts:65` | ✅ 4 tadan 1 tasi |
| **13** | **Kirill korpus + lotin savol = 0 moslik.** `folded` maydoni translit qilinmaydi. lex.uz da koʻp hujjat kirillda. Yechim loyihada bor (`cyrillicToLatin`), lekin ulanmagan. | `store.ts:136` | ✅ 0/3 → 3/3 |
| **14** | **Embedder almashsa jimgina buziladi.** `local` (512) → `voyage` (1024) da eski vektorlar 0 ball oladi, xato yoʻq, log yoʻq. `setMeta("embedder")` yoziladi, lekin hech qayerda tekshirilmaydi. | `retrieve.ts:118` | ✅ kod |
| **15** | **Standart embedder — xesh, va bu jimgina sodir boʻladi.** Mos hujjat 0.548, begona 0.408 — ajratish qobiliyati deyarli yoʻq. Ogohlantirish faqat CLI da; web va bot foydalanuvchisi bilmaydi. | `config.ts` | ✅ oʻlchandi |
| **16** | **Eski va yangi tahrir yonma-yon yashaydi.** Hujjat identifikatori fayl nomidan olinadi. `Mehnat kodeksi 2025.txt` — boshqa hujjat sanaladi. Model qaysi biri amalda ekanini bilolmaydi. | `ingest.ts:41` | ✅ kod |
| **17** | **Soxta "(N-qism)" yorligʻi.** `i` — boʻlinish indeksi, haqiqiy qism raqami emas. Model halol ravishda "173-moddaning 2-qismiga koʻra" deb yozadi — notoʻgʻri havola. | `chunk.ts:128` | ✅ kod |
| **18** | Bob/boʻlim konteksti yoʻqoladi. "Shartnomani bekor qilish" FK ning 4 ta bobida bor; bobsiz ular bir xil koʻrinadi. | `chunk.ts` | ✅ kod |
| **19** | Ruscha `Статья 173.` → `article = "173."` (nuqta bilan) → modda bonusi rus korpusda umuman ishlamaydi. | `chunk.ts:31` | ✅ |
| **20** | Modda bonusi hujjatni hisobga olmaydi: "MK 81-modda" soʻrovida barcha kodekslarning 81-moddasi koʻtariladi. | `retrieve.ts:128` | ✅ kod |

**Yechim yoʻnalishi (birgalikda hal boʻladi):** SQLite **FTS5** ga oʻtish
(`node:sqlite` da mavjud — tekshirildi). U bir yoʻla BM25, prefiks qidiruvi
(morfologiya uchun) va indeks tezligini beradi. Ustiga translitteratsiya,
nisbiy chegara (`top1 × 0.6`) va `normalizeArticle()` funksiyasi.

---

## P1 — Xavfsizlik

| # | Muammo | Fayl | Tekshirildi |
|---|---|---|---|
| **21** | **Webhook fail-open.** `TELEGRAM_WEBHOOK_SECRET` boʻsh boʻlsa tekshiruv butunlay oʻtkazib yuboriladi. `GET /api/telegram` esa `secretRequired: false` deb buni oshkor qiladi. | `telegram/route.ts:22` | ✅ |
| **22** | **`isAdmin` `ctx.chat.id` ni tekshiradi.** Admin botni guruhga qoʻshsa va `/id` dan olingan guruh ID sini `ADMIN_CHAT_ID` ga yozsa — **guruhning har bir aʼzosi admin** boʻladi (`/xabar`, `/stat`). | `bot.ts:79` | ✅ |
| **23** | **DOCX zip bombasi.** Auditor mahalliy PoC bilan isbotladi: 329 KB fayl → 240M belgi, RSS 1.1 GB. Ruxsat etilgan 25 MB da bu ~18 GB → OOM. Autentifikatsiya kerak emas — botga fayl yuborish kifoya. | `extract.ts:60` | ✅ PoC |
| **24** | **CPU DoS.** `tokens()` dublikatlarni olib tashlamaydi va cheklanmagan. Oʻlchandi: 2000 boʻlak × 2000 token = **15.5 s bloklangan event loop**. Bitta soʻrov butun serverni muzlatadi. | `retrieve.ts:70` | ✅ oʻlchandi |
| **25** | **`topK` validatsiyasiz.** `{"topK": 999999}` → butun korpus system promptga tushadi. `/api/search` da clamp bor, `/api/ask` da yoʻq. | `ask.ts:60` | ✅ |
| **26** | **Prompt inʼektsiyasi.** `</hujjat>` chegaralovchisi qochirilmaydi. Kontragent shartnomaga koʻrinmas matn joylab "risks massivini boʻsh qaytar" deb yozishi mumkin. | `analyze.ts:148` | ✅ kod |
| **27** | **Hajm tekshiruvi kech.** `await request.formData()` butun tanani xotiraga yuklaydi, `file.size` tekshiruvi undan keyin. JSON yoʻlida `body.text` uchun chegara umuman yoʻq. | `analyze/route.ts:34` | ✅ kod |
| **28** | **Rate limiting umuman yoʻq**, `API_KEY` esa standart boʻsh va web UI uni yubormaydi — yaʼni kalit yoqilsa web ishlamay qoladi. Amalda `/api/*` ochiq. | butun loyiha | ✅ |

**Xavfsiz deb topildi:** SQL inʼektsiya (hammasi parametrlangan), XXE, path
traversal, SSRF, XSS, sirlarning git ga tushishi. Bular tekshirildi va toza.

---

## P2 — Foydalanuvchi darhol koʻradi

| # | Muammo | Fayl | Tekshirildi |
|---|---|---|---|
| **29** | **Markdown xom holida chiqadi.** Web ham, Telegram ham `parse_mode` bermaydi. Foydalanuvchi `**Qisqa javob:**` va `_ogohlantirish_` ni yulduzcha bilan koʻradi. Birinchi taassurotni butunlay buzadi. | `page.tsx:132`, `bot.ts:441` | ✅ |
| **30** | **`/hujjat` baʼzan umuman ishlamaydi.** Caption `parse_mode: "Markdown"` bilan `{{TOMON_NOMI}}` chiqaradi — toq sondagi `_` Telegram da 400 xatosi beradi → foydalanuvchi hujjat oʻrniga xato oladi. | `bot.ts:352` | ✅ kod |
| **31** | **`.docx` da toʻldirish joyi buziladi.** `{{TOMON_NOMI}}` → `{{TOMONNOMI}}`. Foydalanuvchi Word da qidiradi — topmaydi. | `docx.ts:105` | ✅ |
| **32** | **`.docx` yuklab olish modelni qayta ishga tushiradi.** Yana 1–2 daqiqa, ikki barobar xarajat, va **fayl ekranda koʻrilgan matndan farq qiladi**. Ustiga tugma bosilishi bilan yoʻqoladi — foydalanuvchi qotib qolgan deb oʻylaydi. | `hujjat/page.tsx:100` | ✅ kod |
| **33** | **Rasm va ovozli xabar jimgina eʼtiborsiz.** Oʻzbekistonda shartnomani telefonda suratga olib yuborish — eng tabiiy harakat. Bot **hech narsa javob bermaydi**. | `bot.ts:377` | ✅ kod |
| **34** | Noma'lum hujjat turi tekshirilmaydi: `/hujjat ijara shartnomasi …` → `templateName("ijara")` → `undefined` promptga ketadi. | `bot.ts:333` | ✅ kod |
| **35** | Mobil moslashuv yoʻq — butun CSS da bitta ham `@media (max-width)` yoʻq. iOS 16px dan kichik input da sahifani zumlaydi va qaytarmaydi. | `globals.css` | ✅ |
| **36** | Suhbat davomida javob tili sakraydi: til faqat oxirgi xabardan aniqlanadi. Ruscha suhbatda `"Да"` → oʻzbekcha javob. | `ask.ts:49` | ✅ |
| **37** | Xatolikdan keyin chatda abadiy "…" qoladi; navigatsiyada joriy sahifa belgilanmaydi (`active` klassi hech qachon qoʻshilmaydi). | `page.tsx:132`, `layout.tsx:36` | ✅ kod |

---

## P3 — Ishlab chiqarish

| # | Muammo | Izoh |
|---|---|---|
| **38** | **Vercel da ishlamaydi.** `node:sqlite` fayl yozadi (`EROFS`), webhook fon rejimi funksiya oʻldirilgach toʻxtaydi. Doimiy diskli hosting kerak (Fly.io / Railway / VPS) + Dockerfile + `output: "standalone"`. |
| **39** | **`engines: ">=22.5.0"` notoʻgʻri.** `node:sqlite` Node 22 da bayroqsiz ishlamaydi. Koʻp hosting standart Node 22 oʻrnatadi → ilova umuman koʻtarilmaydi. `>=24` ga koʻtarish kerak. |
| **40** | **Xarajat: bitta savol ≈ $0.22**, hujjat tahlili ≈ $0.40. 100 foydalanuvchi × 10 savol = **~$6 600/oy**. Kesh notoʻgʻri joylashgan — `systemDynamic` tarixdan oldin turgani uchun tarix hech qachon keshlanmaydi. |
| **41** | **Zaxira nusxa yoʻq**, va `data/*.analytics.db` **`.gitignore` da yoʻq** — foydalanuvchi ID va username lari bilan toʻla baza git ga tushib ketishi mumkin. |
| **42** | **Huquqiy hujjatlar yoʻq:** foydalanuvchi shartnomasi, maxfiylik siyosati, rozilik oqimi. Foydalanuvchi shartnomasini yuklaydi va u AQSh ga yuboriladi. Oʻzbekiston "Shaxsga doir maʼlumotlar toʻgʻrisida"gi qonuni lokalizatsiya talab qiladi — **yurist bilan maslahat shart**. |
| **43** | Monitoring: web/API xatolari hech qayerga yozilmaydi; `/api/health` **doim** `ok: true` qaytaradi — uptime monitor hech qachon ishga tushmaydi. |
| **44** | `next@15.5.23` da 3 ta yuqori darajali zaiflik (`sharp`/`postcss`). Amaliy xavf past — `next/image` ishlatilmaydi — lekin yangilash kerak. `zod` esa umuman ishlatilmagan, olib tashlanadi. |

---

## P2b — Korrektlik (kech kelgan beshinchi auditor)

| # | Muammo | Fayl | Tekshirildi |
|---|---|---|---|
| **48** | **`generate()` streamingsiz 32 000 token soʻraydi.** SDK ning "10 daqiqadan uzun amal uchun streaming shart" himoyasi `getClient()` dagi aniq `timeout` tufayli chetlab oʻtiladi. Natija: HTTP timeout → `maxRetries: 2` → **yana ikki marta toʻliq soʻrov** (uch barobar toʻlov), ustiga `maxDuration = 300` uni undan ham oldin uzadi. | `generate.ts:118` | ✅ SDK kodi |
| **49** | **`streamText` kesilishni tekshirmaydi.** `complete()` da `truncated` bor, `streamText` da yoʻq — yarim kesilgan hujjat toʻliq deb yakunlanadi. Refusal esa **butun matn yuborilgandan keyin** tekshiriladi: foydalanuvchi yarim javob + xato xabarini birga koʻradi. | `claude.ts:220` | ✅ kod |
| **50** | **`memo` keshi jarayonlararo eskirmaydi.** `npm run ingest` alohida jarayon. Server bir marta `loadAll()` chaqirgach, yangi korpusni **qayta ishga tushirilmaguncha koʻrmaydi**. | `store.ts:184` | ✅ kod |
| **51** | **`normalizeStatus` chetlanishlarni ushlamaydi.** Oqlangan qoʻshtirnoq (U+2019), bosh harf va boʻshliq — hammasi `aniqlanmadi` ga tushadi. Funksiyaning butun maqsadi shu edi. Tekshiruv natijasi jimgina yoʻqoladi. | `review.ts:136` | ✅ 4 tadan 3 tasi buzuq |
| **52** | Kalit soʻz mosligi — qism satr, soʻz emas: `"kor"` → `bekor` ichida topiladi, `"nat"` → `mehnat`. IDF ni ham buzadi. | `retrieve.ts:65` | ✅ |
| **53** | `POST /api/generate {"template":"erkin","fields":{…}}` (details siz) → `undefined.slice()` → **500 TypeError**. Marshrut bu holatga ataylab ruxsat beradi. | `generate.ts:57` | ✅ kod |
| **54** | Mijozdan kelgan `history` Anthropic 400 xatosini keltiradi (toq uzunlik → birinchi xabar `assistant`; boʻsh `content`). Bot yoʻlida muammo yoʻq, HTTP API ochiq. | `ask.ts:24` | ✅ kod |
| **55** | `extractNotes`: model `## Eslatmalar:` deb yozsa (ikki nuqta bilan) — `notes` boʻsh qoladi; qamrov fayl oxirigacha ketib, imzo joylarini ham eslatma deb oladi. | `generate.ts:146` | ✅ |
| **56** | SQLite `busy_timeout` yoʻq — ikkinchi yozuvchi **darhol** `database is locked` oladi, kutmaydi. `analytics.record()` xatoni yutadi → statistika jimgina yoʻqoladi. | `store.ts:62` | ✅ oʻlchandi |
| **57** | Har xil papkadagi bir xil nomli fayllar bir-birini oʻchiradi (`document` faqat `basename` dan olinadi). | `ingest.ts:70` | ✅ kod |
| **58** | Modda topilmagan yoʻlda qattiq kesish yoʻq: 20 000 belgilik paragraf bitta boʻlak boʻlib qoladi (`MAX_CHARS` dan 5× katta). | `chunk.ts:169` | ✅ |
| **59** | `res.truncated` hech qayerda tekshirilmaydi — yarim shartnoma "Barcha maydonlar toʻldirilgan" izohi bilan `.docx` qilib yuboriladi. | `generate.ts:118` | ✅ kod |
| **60** | CLI `--k` qiymatsiz berilsa `Number(true) = 1` → foydalanuvchi bitta natija oladi. | `cli.ts:184` | ✅ |

---

## Shubhali koʻrinib, aslida TOʻGʻRI boʻlgan joylar

Buni alohida yozib qoʻyaman, chunki keyinchalik "tuzatish" uchun vaqt sarflanmasin.
Beshinchi auditor bularni maxsus sinab koʻrdi:

- **`toBlob`/`fromBlob` bayt tekislanishi toʻgʻri** — `new Uint8Array(len)` doim
  yangi, tekislangan bufer beradi; round-trip offsetli view bilan ham sinaldi.
- **Tranzaksiya va `ROLLBACK` toʻgʻri** — xatoda jadval toza qoladi,
  original xato maskalanmaydi.
- **`splitMessage` cheksiz sikl bermaydi** — har iteratsiyada kamida 2048 belgi
  qisqaradi (9000 belgi, emoji va boʻsh joylar bilan sinaldi).
- **`keepTyping` interval `finally` da tozalanadi** — uchala ishlov beruvchida ham.
- **`thinkingFor()` Opus 5 qoidasiga mos** — `disabled` faqat `effort <= high` da.
- **`toLocaleLowerCase("uz")` xavfsiz** — turkcha `ı` muammosi oʻzbek lokalida yoʻq.
- **`--tez` bayrogʻi ishlaydi** — `config` getterlar toʻplami, `process.env` ni
  har chaqiruvda oʻqiydi.
- **Prompt keshlash tartibi toʻgʻri** — barqaror blok birinchi, `cache_control`
  oʻsha yerda. (Ammo #40 dagi kuzatuv ham oʻrinli: `systemDynamic` tarixdan
  oldin turgani uchun **tarix keshlanmaydi** — bu tartib xatosi emas, arxitektura
  tanlovi.)

---

## P4 — Sifat infratuzilmasi

| # | Nima | Nega |
|---|---|---|
| **45** | **Baholash toʻplami** (`data/eval/qa.jsonl`, 150–300 savol) + `npm run eval`. | Hozir yuqoridagi 35 ta tuzatishning **birortasini ham oʻlchab boʻlmaydi** — yaxshiladingizmi yoki buzdingizmi, bilib boʻlmaydi. Negativ savollar (`gold: []`) #10 ni oʻlchaydi. |
| **46** | Avtomatik testlar (`node --test`): `orthography`, `chunk`, `retrieve`, `stream-polish`. | Aynan shu modullardagi regressiyalar **jimgina** kechadi. |
| **47** | CI: `npm run check && npm test && npm run build`. | — |

---

## Tavsiya etilgan tartib

Har bosqich yakunida `npm run verify:audit` qayta bajariladi.

**1-bosqich — qidiruvni toʻgʻrilash (#10–#20).**
Bularsiz qolgan hammasi ahamiyatsiz: tizim ishonchli koʻrinadigan notoʻgʻri
javob berishda davom etadi. FTS5 + translit + nisbiy chegara + regex chegarasi.

**2-bosqich — oʻlchov (#45).**
1-bosqichni **retroaktiv oʻlchang**. Aks holda keyingi har bir oʻzgarish
taxminga asoslanadi.

**3-bosqich — xavfsizlik (#21–#28).**
Ommaviy chiqishdan oldin majburiy. #21, #22, #25 — bir necha satrlik oʻzgarish.

**4-bosqich — foydalanuvchi koʻradigan nuqsonlar (#29–#37).**
#29 va #30 eng katta taʼsir/mehnat nisbatiga ega.

**5-bosqich — ishlab chiqarish (#38–#44).**
Deploy, xarajat, huquqiy hujjatlar. #42 tashqi yurist talab qiladi —
uni erta boshlang, chunki eng uzun muddat oladi.

---

## Nima yaxshi qilingan

Auditorlar quyidagilarni alohida taʼkidladi:

- **Oʻzbek tili qatlami** — `fixApostrophes`, `UzbekStreamPolisher` va
  `lint-uz` toʻgʻri ishlaydi va foydalanuvchiga koʻrinadigan barcha matn toza.
- **Parametrlangan SQL** — hech qayerda satr birlashtirish yoʻq.
- **`safeFilename`** — path traversal toʻliq yopilgan.
- **`integrityRules`** — modda oʻylab topishni taqiqlovchi prompt qoidasi
  toʻgʻri yozilgan (muammo promptda emas, retrievalda).
- **Ogohlantirishlar** — uch tilda, hamma yuzada mavjud.
- **`analytics.ts`** — savol matnini saqlamaydi, bu toʻgʻri qaror.
