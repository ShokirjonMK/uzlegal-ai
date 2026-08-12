# 1. Bir jumlada

Loyiha **«yaxshi qurilgan, lekin ishga tushmaydigan»** holatdan
**«uchala platformada haqiqiy qonun matni ustida ishlaydigan»** holatga
oʻtdi.

| | Tekshiruvdan oldin | Hozir |
|---|---|---|
| **Kod tayyorligi** | ~80% | **~92%** |
| **Mahsulot tayyorligi** | ~30% | **~70%** |

Qolgan 30% ning katta qismi **texnik emas**: korpus hajmi (vaqt), yurist
tekshiruvi (ekspert), huquqiy hujjatlar (yurist va rahbariyat).

---

# 2. Tekshirish usuli

Har bir daʼvo hujjatdan emas, **bajarilgan buyruq natijasidan** olingan.
Repo toza mashinaga yuklandi, muhit noldan qurildi, tizim amalda ishga
tushirildi.

| Tekshiruv | Natija |
|---|---|
| `pytest` | ✅ **845 test**, 0 skip |
| `ruff check` · `ruff format` | ✅ toza (120 fayl) |
| `mypy --strict` | ✅ **0 xato** (edi: 8) |
| `lint-imports` | ✅ qatlam shartnomasi saqlangan |
| `tsc --noEmit` · `lint:uz` · `next build` | ✅ toza |
| `verify:audit` | ✅ **0 qarz** (edi: 10) |
| CI (`.github/workflows/ci.yml`) | ✅ qoʻshildi |

---

# 3. Uchta qizil bloker — hammasi yopildi

## B1 — Bilim bazasi umuman yoʻq edi

`kb/current` boʻsh, `data/raw` boʻsh. 14 ta e2e test *«Bilim bazasi
qurilmagan»* sababi bilan oʻtkazib yuborilardi — yaʼni 755 yashil test
faqat soxta maʼlumot ustida ishlagan.

**Hozir:** lex.uz dan **20 kodeks · 7 090 modda · 8 636 boʻlak**,
`robots.txt` dagi Crawl-delay 20 s ga toʻliq rioya qilgan holda 380
soniyada yuklandi.

| Kodeks | Modda |
|---|---:|
| Fuqarolik kodeksi (2 qism) | 1 197 |
| Jinoyat-protsessual kodeksi | 769 |
| Maʼmuriy javobgarlik kodeksi | 663 |
| Mehnat kodeksi | 581 |
| Fuqarolik protsessual kodeksi | 508 |
| Soliq kodeksi | 500 |
| Jinoyat kodeksi | 404 |
| … va yana 13 kodeks | 2 468 |

## B2 — macOSʻdan tashqarida model yoʻq edi

`inference/backend.py` `vllm_backend` va `openai_backend` ni import
qilardi, lekin **bu ikki fayl mavjud emasdi** va import xatosi jimgina
yutilardi.

Natijada Linux va Windowsʻda `echo` (soxta) dan boshqa hech narsa yoʻq
edi, `deploy/` dagi GPU-server profili esa **umuman ishga tushmasdi**.

**Hozir:** `openai_backend.py` yozildi — Ollama, vLLM, LM Studio va oʻz
serveringiz bilan ishlaydi. Yangi kutubxona qoʻshilmadi.

## B3 — API butunlay ochiq edi

Tekshirildi: `POST /v1/admin/users` (foydalanuvchi yaratish) va
`/v1/admin/users/{id}/regenerate-key` (kalit qayta tiklash) **hech
qanday kalitsiz** javob berardi.

Ayni paytda `configs/profiles/server.yaml` siyosatni **allaqachon**
eʼlon qilgan edi (`auth: api_key`, `rate_limit`) — kod uni oʻqimasdi.

**Hozir:** kirish nazorati middleware sifatida qoʻyildi — marshrut yoʻli
boʻyicha, yaʼni kelajakdagi har qanday `/v1/admin/...` avtomatik yopiq.

---

# 4. Model qanday holatda

## 4.1 Tanlangan model

| | |
|---|---|
| Model | **Gemma-3-12B** (4-bit kvantlangan) |
| Tanlov asosi | ADR-001, 42 savollik oʻlchov |
| Umumiy ball | 3.77 / 5 |
| **Oʻzbek tili** | **4.82 / 5** |
| Muqobillar | Qwen3-14B (3.28), Qwen3-8B (3.22) |

Oʻzbek tili balli 4.82 boʻlgani uchun **CPT (davomiy oldindan oʻqitish)
shart emas** deb qaror qilingan — bu katta vaqt va pul tejaydi.

## 4.2 Ishlash holati

Model **Ollama** orqali ishlaydi va sinovdan oʻtdi:

> **Savol:** Oʻzbekistonda mehnat shartnomasi qanday shaklda tuziladi?
> **Javob:** Oʻzbekistonda mehnat shartnomasi yozma shaklda tuziladi va
> ikki nusxada rasmiylashtiriladi.

## 4.3 Fine-tuning — bajarilmagan

**Bitta ham rol adapteri oʻqitilmagan.** Sabablari:

1. Tekshirilgan trening maʼlumoti yoʻq (~1 500 soat yurist vaqti kerak);
2. Trening kodi `mlx_lm` ga bogʻlangan — faqat macOSʻda ishlaydi;
3. 8 GB VRAM da 12B modelni QLoRA bilan oʻqitib boʻlmaydi (~10–12 GB kerak).

**Hozir rollar farqi faqat promptdan keladi.** Bu ishlaydi, lekin
adapterlar bergan rol sodiqligidan pastroq.

Batafsil: alohida fine-tuning hisobotida.

## 4.4 Kechikish

| Rejim | Oʻlchandi | Maqsad |
|---|---:|---:|
| `simple` | 61–92 s | ~5 s |

Bu **kod nuqsoni emas, apparat cheklovi**: `gemma3:12b` (8.1 GB) 8 GB
VRAM ga toʻliq sigʻmaydi va bir qismi CPU da ishlaydi.

Bitta buyruq bilan hal boʻladi:

```
uzlegal models use ollama-gemma3-4b     # toʻliq GPU da, sezilarli tez
```

Sifat/tezlik almashuvi — **konfiguratsiya masalasi**, kod masalasi emas.

---

# 5. Oʻlchangan sifat

## 5.1 Qidiruv sifati

`retrieval-gold-v1`, 36 holat:

| Metrika | Natija | Maqsad |
|---|---:|---:|
| Recall@1 | 42% | 60% |
| Recall@3 | 67% | 80% |
| Recall@10 | **89%** | 90% |
| MRR | 0.55 | 0.75 |
| **Deprecated leak** | **0%** | **0%** ✅ |
| Kechikish (median) | 204 ms | — |

Amaliy sinov:

> **Soʻrov:** «mehnat shartnomasida sinov muddati»
> **1-natija:** Mehnat kodeksi 130–131-modda — *«Dastlabki sinov muddati
> uch oydan… oshmasligi kerak»* (ball 0.397)

## 5.2 Xavfsizlik sinovi

`traps-30` — tizim nima **qilmasligi** kerakligini oʻlchaydi:

| Kategoriya | Tuzatishdan oldin | Keyin |
|---|---:|---:|
| Aniqlik | 100% | 100% |
| Chegara | 100% | 100% |
| **Prompt inʼektsiyasi** | 100% | **100%** |
| Noaniq savol | 100% | 100% |
| Xavfsizlik | 100% | 100% |
| Mavjud boʻlmagan modda | 60% | **80%** |
| Versiya (eski tahrir) | 50% | **100%** |
| Qamrov | 0% | **40%** |
| **Umumiy** | **73%** | **87%** |

> Model deterministik emas — chegaradagi holatlar yurishdan yurishga
> oʻzgarishi mumkin. Ishonchli raqam uchun toʻplamni bir necha marta
> yurgizib oʻrtachasini olish kerak.

## 5.3 Reranker — oʻlchandi va OʻCHIRILDI

Profil fayllari rerankerni eʼlon qilgan edi. Oʻlchov:

| Metrika | Rerankersiz | Reranker bilan |
|---|---:|---:|
| Recall@1 | 42% | **47%** |
| **Recall@10** | **89%** | 81% |

Reranker saralashni yaxshilaydi, lekin **Recall@10 ni sakkiz punktga
tushiradi**. Bu eng yomon almashuv: gate faqat kontekstda **bor** normani
tasdiqlay oladi.

---

# 6. Topilgan va tuzatilgan nuqsonlar

## 6.1 Yadro

| Nuqson | Taʼsiri |
|---|---|
| `doctor` macOSʻdan tashqarida **yiqilardi** | Yangi ishtirokchi birinchi buyruqdayoq buzilgan tizimni koʻrardi |
| `/v1/health` boʻsh bazani «tayyor» derdi | Monitoring yolgʻon gapirardi |
| 48 GB mashina **16 GB** deb koʻrinardi | Modellar «sigʻmaydi» deb belgilanardi |
| Embedder **`cuda` ni hech qachon tanlamasdi** | NVIDIA kartada jimgina CPU da ishlardi |
| **Chunker: 63 888 belgilik boʻlak** | Matnning ~60% i embeddingga tushmagan va qidiruvda koʻrinmas edi |
| **Gate toʻqilgan modda raqamini oʻtkazardi** | Quyida alohida |
| **Baholash vositasi hech qachon ishlamagan** | Quyida alohida |
| **F5 xavfsizlik xususiyati refaktorda oʻchgan** | Quyida alohida |

## 6.2 Uchta eng jiddiy topilma

### A. Gate teshigi

Model shunday javob yozardi:

> Mehnat kodeksining **106-moddasiga** koʻra sinov muddati uch oydan
> ortiq boʻlmasligi kerak `[C1]`
> `[C1]` Mehnat kodeksi, **130–131-modda**

Norma **toʻgʻri**, havola **toʻgʻri**, lekin matndagi modda raqami
**oʻylab topilgan**. Leksik qoplama buni tutmaydi — soʻzlar mos keladi.

Foydalanuvchi uchun bu **eng yomon xato turi**: javob ishonchli
koʻrinadi, havola bor, lekin havola boshqa moddaga olib boradi.

**Tuzatildi.** Endi modda raqami iqtibosga mos kelmasa daʼvo oʻchiriladi.

### B. Baholash vositasi hech qachon ishlamagan

`uzlegal eval run` va `eval safety` **har bir holatda** yiqilardi:

```
consult() got an unexpected keyword argument 'mode'
```

Yaʼni `make eval-smoke` — loyihaning eʼlon qilingan **sifat darvozasi** —
hech qachon yurmagan.

**Nega testlar tutmadi:** barcha unit testlar stub ishlatadi va hech biri
haqiqiy `consult` ni ulamaydi.

### C. Regressiya — xavfsizlik xususiyati oʻchib ketgan

«Mavjud boʻlmagan modda ochiq aytiladi» xususiyati mavjud edi:

```
dac4006  feat(F5): mavjud boʻlmagan modda ochiq aytiladi
7cbab06  refactor: F6 interfeyslari consult() shartnomasiga ulandi  ← oʻchirdi
```

Kodi ham, **47 satrlik testlari ham** butunlay yoʻqolgan. Regressiya
sezilmadi, chunki **testlar kod bilan birga oʻchirilgan**.

Natijada «Fuqarolik kodeksining 9999-moddasi nima haqida?» degan savolga
tizim **Oila kodeksining 43-moddasini** keltirardi.

**Tiklandi va mustahkamlandi.**

## 6.3 Web qobigʻi

Audit qarzlari: **10 tasdiqlangan → 0**.

Eng muhimlari: soxta modda yasash (`chunk.ts`), webhook **fail-open**
(sir sozlanmasa tekshiruv butunlay oʻtkazib yuborilardi), `isAdmin`
guruh eskalatsiyasi (bot guruhga qoʻshilsa **har bir aʼzo admin**
boʻlardi), kirill translit ulanmagani.

---

# 7. Xavfsizlik holati

| Nima | Oldin | Hozir |
|---|---|---|
| `/v1/admin/*` | **ochiq** | kalitsiz **401** |
| Ommaviy endpointlar | ochiq | profil boʻyicha (`auth: api_key`) |
| Rate-limit | yoʻq | IP boʻyicha, `429` + `Retry-After` |
| Reja chegaralari | yozilgan, **ulanmagan** | API qatlamida majburlanadi |
| Telegram webhook | **fail-open** | **fail-closed** (503) |
| Prompt inʼektsiyasi | — | `traps-30` da **100%** |

Uchidan-uchgacha tasdiqlandi:

```
GET  /v1/health              (kalitsiz)          200  healthy
GET  /v1/admin/sync          (kalitsiz)          401
GET  /v1/admin/sync          (notoʻgʻri kalit)   401
GET  /v1/admin/sync          (toʻgʻri kalit)     200
POST /v1/search              (kalitsiz)          401
POST /v1/search              (mijoz kaliti)      200
```

---

# 8. Mualliflik himoyasi

Qoʻshildi:

- **API sarlavhalari:** `X-Author`, `X-Developer`, `X-Contact`,
  `X-Project`, `X-Key-Fingerprint` — har javobda, xato javoblarida ham;
- **CLI banneri** va `uzlegal license author`;
- **Litsenziya darvozasi:** Ed25519 ochiq kalitli imzo. `serve`, `bot`,
  `mcp` litsenziyasiz ishga tushmaydi.

Soxtalashtirishning har bir yoʻli sinaldi va yopildi: boshqa kalit bilan
imzolash, nom oʻzgartirish, muddat choʻzish, `scope` kengaytirish —
hammasi rad etiladi.

> ⚠️ **Huquqiy ziddiyat.** `LICENSE` da **MIT** turibdi va u har kimga
> kodni ishlatish huquqini **allaqachon bergan**. Texnik darvozani MIT
> ostida olib tashlash **qonuniy**. Qulf oʻrnatildi, lekin kalit eshik
> yonida osilgan. Bu **huquqiy qaror** va u repo egasidan kutilmoqda.

---

# 9. Tizimni toʻliq ishga tushirish uchun yana nimalar kerak

## 9.1 Texnik — hal qilinadigan

| # | Ish | Muddat | Kim |
|---|---|---|---|
| 1 | Rate-limit ni Redis ga koʻchirish | 1 kun | Dasturchi |
| 2 | Trening uchun CUDA yoʻli (`peft`) | 3 kun | ML muhandis |
| 3 | `retrieval-gold-v1` ni 36 → 200 holat | ~20 soat | Yurist |
| 4 | `smoke-50` → `gold-300` | ~60 soat | Yurist |
| 5 | Web `rag/` ni yadro `/v1/search` ga koʻchirish | 2 kun | Dasturchi |
| 6 | Semantik mos-nomoslik hakami (qamrov muammosi) | 3 kun | ML muhandis |

## 9.2 Vaqt talab qiladigan

| # | Ish | Muddat |
|---|---|---|
| 7 | Toʻliq korpus: 40 000 hujjat | **~17 kun** uzluksiz (Crawl-delay 20 s — chetlab oʻtilmaydi) |
| 8 | Qonunosti hujjatlari, sud amaliyoti, plenum qarorlari | Korpus bilan birga |

## 9.3 Blokerlar — kod bilan hal qilinmaydi

| # | Ish | Kimga bogʻliq |
|---|---|---|
| 9 | **Huquqiy hujjatlar** — foydalanuvchi shartnomasi, maxfiylik siyosati, javobgarlik cheklovi | **Yurist + rahbariyat** |
| 10 | «Shaxsga doir maʼlumotlar» qonuni boʻyicha lokalizatsiya | **Yurist** |
| 11 | Litsenziya turini tanlash (MIT / AGPL / xususiy) | **Repo egasi** |
| 12 | Rol adapterlari uchun dataset | **Yurist, ~1 500 soat** |

> 9-band **eng erta boshlanishi kerak** — u eng uzun muddat oladi va
> texnik ishga parallel ketadi.

---

# 10. Tavsiya etilgan tartib

| Bosqich | Ish | Natija |
|---|---|---|
| **1** | Litsenziya qarori + huquqiy hujjatlarni boshlash | Yuridik toʻsiq olib tashlanadi |
| **2** | Gold set kengaytirish (80 soat yurist) | Sifat **oʻlchanadigan** boʻladi |
| **3** | Korpusni fonda yuklash (17 kun) | Qamrov muammosi tabiiy hal boʻladi |
| **4** | Yopiq beta — 20–50 foydalanuvchi | Haqiqiy savollar taqsimoti maʼlum boʻladi |
| **5** | Shundan keyin rol adapterlari | Dataset **haqiqiy** savollar asosida tuziladi |

Bu tartibning mantigʻi: **1 500 soat yurist vaqtini** taxmin asosida
sarflashdan koʻra, avval 80 soat sarflab **oʻlchov** qurish va haqiqiy
foydalanuvchi savollarini bilish ancha samaraliroq.

---

# 11. Eng katta risk

`docs/11` uni «bus factor 1» deb yozgan. Amalda undan kattarogʻi
koʻrindi: **hujjat va konfiguratsiya kodni ortda qoldiradi.**

Bu naqsh bir tekshiruvda **besh marta** takrorlandi:

| Nima | Qaysi tomon notoʻgʻri edi |
|---|---|
| `deploy/` mavjud boʻlmagan `vllm` backendni talab qilardi | Konfiguratsiya |
| Profillar rerankerni eʼlon qilardi (u sifatni pasaytiradi) | Konfiguratsiya |
| `verify-audit` tuzatilganni buzuq derdi | Vosita |
| `eval` hech qachon ishlamagan | Ulanish |
| F5 xususiyati refaktorda oʻchdi | **Testlar** |

Oxirgisi eng jiddiy: kod va test **birga** oʻchirilganda hech qanday
signal qolmaydi.

**Yechim arzon va u qoʻllanildi:** har daʼvoni **bajariladigan tekshiruv**
bilan bogʻlash — matnga emas. `doctor` va `/v1/health` haqiqiy indeksdan
oʻqiydi, `verify:audit` haqiqiy koddan oʻqiydi, reranker qarori **oʻlchov
bilan birga** YAML ichida yozilgan, CI hammasini har oʻzgarishda
yugurtiradi.

**Kod oʻzi haqida gapirsin.**
