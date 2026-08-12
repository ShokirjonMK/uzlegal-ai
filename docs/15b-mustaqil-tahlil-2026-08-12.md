# UzLegal-AI — mustaqil tahlil va yakunlash strategiyasi

**Sana:** 2026-08-12 · **Usul:** repo yuklandi, muhit qurildi, testlar, linterlar,
CLI, Python API va Next.js web amalda ishga tushirildi. Quyidagi har bir da'vo
hujjatdan emas, **bajarilgan buyruq natijasidan** olingan.

---

## 1. Bir jumlada

Bu **juda yaxshi qurilgan bo'sh dvigatel**: arxitektura, kod sifati va
mulohaza qatlami professional darajada va testlar bilan isbotlangan, lekin
tizimda **bitta ham haqiqiy qonun matni yo'q** va **macOS'dan tashqarida
ishlaydigan bitta ham model yo'q** — shuning uchun bugun u bitta ham real
huquqiy savolga javob bera olmaydi.

---

## 2. Amalda o'lchangan holat

| Tekshiruv | Buyruq | Natija |
|---|---|---|
| O'rnatish | `pip install -e ".[dev]"` | ✅ toza |
| Testlar | `pytest` | ✅ **755 o'tdi**, 18 skip, 13 s |
| Lint | `ruff check` | ✅ toza |
| Qatlam shartnomasi | `lint-imports` | ✅ saqlangan (194 bog'liqlik) |
| Tiplar | `mypy --strict` | ⚠️ 8 xato (3 tasi Windows'ga xos) |
| Format | `ruff format --check` | ⚠️ 8 fayl (CRLF ehtimoli) |
| CLI | `uzlegal --help` | ✅ 12 buyruq |
| Diagnostika | `uzlegal doctor` | ❌ **yiqiladi** (macOS'dan tashqarida) |
| Indeks | `uzlegal index stats` | ❌ **Indeks yo'q** |
| Web tiplar | `tsc --noEmit` | ✅ toza |
| Web matn | `npm run lint:uz` | ✅ toza (99 fayl) |
| Web build | `npm run build` | ✅ 24 marshrut |
| Yadro API | `POST /v1/consult` | ✅ javob berdi |
| CI | `.github/workflows/` | ❌ **umuman yo'q** |

### Skip bo'lgan 18 test — eng muhim signal

14 tasi: *"Bilim bazasi qurilmagan"*. 4 tasi: *"Arxivda -111189 yo'q"*.
Ya'ni **uchidan-uchgacha oqim hech qachon haqiqiy ma'lumotda sinalmagan**.
755 yashil test — bularning hammasi stub retriever va echo model ustida.

---

## 3. Nima haqiqatan qurilgan (va bu kam emas)

**Python yadro — 18 376 satr, 113 fayl:**

- `ingest/` — lex.uz konnektori (Crawl-delay 20 s hurmat qilinadi), HTML parser,
  normalizatsiya, **versiyalash**, havola grafi, PII anonimizatsiya, validatsiya
- `index/` — chunker, BGE-M3 embedder, do'kon
- `retrieval/` — gibrid (vektor + BM25), RRF (`k=3` — asoslangan qaror),
  reranker, so'rov kengaytmasi, hujjat yo'naltirish
- `agents/` + `orchestrator/` — 5 rol, router, munozara, sudya, **groundedness gate**, iz
- `interfaces` — CLI (12 buyruq), REST (26 endpoint) + SSE, MCP server,
  Telegram bot, Python SDK
- Qo'shimcha domenlar: `litigation/`, `court/`, `education/`, `integrity/`, `users/`

**Web (Next.js 15) — 66 TS + 24 TSX fayl:** web UI, admin panel, kabinet,
Telegram bot, hujjat tahlili/generatsiyasi, o'zbek tili qatlami (`fixApostrophes`,
`lint-uz` — bu chindan yaxshi ishlangan).

**Hujjatlar:** 16 hujjat + 8 ADR. Bu darajadagi hujjatlashtirish kamdan-kam uchraydi.

### Bugun men isbotlagan ikki muhim narsa

**1. TS qobiq ↔ Python yadro shartnomasi MOS KELADI.**
`web/BIRLASHTIRISH.md` da bu "tekshirilmagan, birinchi so'rovda tekshirilishi
shart" deb yozilgan edi. Men serverni ko'tarib so'rov yubordim — `ConsultResult`
ning barcha maydonlari (`trace_id`, `answer`, `citations`, `confidence`,
`caveats`, `mode_used`, `latency_ms`, `kb_version`, `disclaimer`) to'g'ri keldi.
**Bu ochiq savol yopildi.**

**2. Asosiy va'da ishlaydi.** Bo'sh bazada tizim javob o'ylab topmadi:

```
"Ishonchli javob shakllantirilmadi. Javobdagi huquqiy da'volarning hech biri
 berilgan manbalarga bog'lanmadi, shuning uchun ular chiqarib tashlandi."
confidence: 0.0
```

Groundedness gate **haqiqatan ishlaydi**. Loyihaning butun mohiyati shu edi.

---

## 4. Blokerlar — nima uchun bugun foydalanib bo'lmaydi

### 🔴 B1. Bilim bazasi umuman yo'q

`kb/current` bo'sh, `data/raw` bo'sh. `docs/14` "20 kodeks, 8 627 chunk"
deydi — **repoda ular yo'q** (`.gitignore` da, bu to'g'ri qaror, lekin
demak yangi mashinada tizim noldan boshlanadi).

Hisob: 40 000 hujjat × 20 s = **~17 kun uzluksiz yuklab olish**.
Chetlab o'tib bo'lmaydi — `robots.txt` majburiy.

### 🔴 B2. macOS'dan tashqarida ishlaydigan model yo'q

`inference/` da faqat ikki backend: `echo` (soxta) va `mlx` (faqat Apple Silicon).

`backend.py:133` `vllm_backend` va `openai_backend` ni import qilishga urinadi —
**bu ikki fayl mavjud emas**. Import xatosi jimgina yutiladi.

Oqibati: `deploy/docker-compose.server.yaml`, `deploy/Dockerfile`,
`configs/profiles/server.yaml`, `docs/09`, `docs/15-gpu-server-deployment.md` —
hammasi Linux + GPU serverni tasvirlaydi, lekin **u profil ishlay olmaydi**.
Hujjat va kod o'rtasida qattiq ziddiyat.

### 🔴 B3. Python API'da autentifikatsiya ham, rate-limit ham yo'q

Men tekshirdim: `POST /v1/admin/users` (foydalanuvchi yaratish) va
`POST /v1/admin/users/{id}/regenerate-key` **hech qanday kalitsiz ochiq**.
`.env.example` da `UZLEGAL_API_KEYS` bor, lekin `api/app.py` da u
**hech qayerda o'qilmaydi**. `users/plans.py` da rejalar va limitlar yozilgan,
lekin API qatlamida majburlanmaydi.

### 🟠 B4. Yurist tekshiruvi (F3/F4)

LoRA quvuri (`training/lora.py` → `mlx_lm.lora`) real, lekin tekshirilgan
trening ma'lumoti yo'q. `docs/14` baholovi: ~1 500 soat yurist ishi.
Bu **texnik emas, tashkiliy** bloker.

### 🟠 B5. CI yo'q

`.github/workflows/` mavjud emas. 755 test bor, lekin ularni hech kim
avtomatik yurgizmaydi. Har push qo'lda ishonchga tayanadi.

---

## 5. Men topgan yangi nuqsonlar

| # | Nuqson | Joy | Isbot |
|---|---|---|---|
| **N1** | `uzlegal doctor` **yiqiladi** macOS'dan tashqarida — `sysctl` shartsiz chaqiriladi, `FileNotFoundError` ushlanmaydi | `cli/main.py:932` | Windows'da bajarildi |
| **N2** | `/v1/health` **yolg'on gapiradi**: `kb_ready: true, kb_version: "v2026.08.10"` — indeks esa umuman yo'q. Salomatlik `data/sync-state.json` dan o'qiydi, haqiqiy indeksdan emas | `api/app.py:338` | So'rov yuborildi |
| **N3** | Bir jarayonda ikki xil haqiqat: `/v1/health` → `model_ready: false`, ayni paytda `/v1/consult` → `model_version: "echo"` bilan ishlaydi | `api/app.py:336` | So'rov yuborildi |
| **N4** | `kb_version` ikki manbadan keladi: health → `"v2026.08.10"`, consult → `""` | `core.py:286` vs `app.py:339` | So'rov yuborildi |
| **N5** | `web/scripts/verify-audit.mts` **eskirgan** — tuzatilgan muammolarni "TASDIQLANDI" deb ko'rsatadi (#12 morfologiya, #13 translit). U `foldForSearch` ni sinaydi, holbuki kod endi `stem()` ishlatadi. Regressiya vositasi o'zi noto'g'ri signal beradi | `verify-audit.mts:49` | Kod solishtirildi |
| **N6** | `api/ask/route.ts:17` izohida `topK` qabul qilinadi deyilgan — birlashtirishdan keyin bunday maydon yo'q | `route.ts:17` | Kod o'qildi |

### Web auditidagi hali tuzatilmagan haqiqiy nuqsonlar

Men shaxsan tekshirdim:

- **Webhook fail-open** — `TELEGRAM_WEBHOOK_SECRET` bo'sh bo'lsa tekshiruv
  **butunlay o'tkazib yuboriladi** (`telegram/route.ts:23`). Har kim webhook'ga
  soxta update yubora oladi.
- **`isAdmin` guruh ID sini qabul qiladi** (`bot.ts:83`) — bot guruhga qo'shilsa
  va guruh ID si `ADMIN_CHAT_ID` ga tushsa, **guruhning har bir a'zosi admin**.
- **Kirill translit ulanmagan** — `cyrillicToLatin()` yozilgan, lekin
  `rag/store.ts` va `rag/ingest.ts` da **ishlatilmaydi**. lex.uz'da ko'p hujjat
  kirillda; lotin so'rov ularni topmaydi.
- **`replyLong` `parse_mode` bermaydi** (`bot.ts:70`) — foydalanuvchi Telegram'da
  `**Qisqa javob:**` ni yulduzchalari bilan xom ko'radi.
- **`chunk.ts` soxta modda yasaydi** — matn ichidagi "173-moddada nazarda
  tutilgan…" satr boshiga tushsa, bazaga soxta 173-modda kiradi (skript
  haqiqiy kodda 2 ta soxta blok topdi).

Tuzatilgani tasdiqlandi: apostrof tokenizatsiyasi (#10a), `foldForSearch` (#10b),
o'zbek morfologiyasi (#12), so'z chegarasi (#52), token limiti (#24).

---

## 6. Tayyorlik bahosi

Ikki xil raqam bor va ularni aralashtirmaslik kerak.

### Kod tayyorligi — **~80%**

| Qatlam | Kod | Izoh |
|---|---:|---|
| Arxitektura va hujjatlar | 100% | 16 hujjat + 8 ADR |
| Ingest quvuri | 90% | To'liq yozilgan, hech qachon to'liq yurmagan |
| RAG / indeks | 90% | Recall@10 89% (36 holatlik kichik namunada) |
| Agentlar / orkestrator | 95% | Gate isbotlangan |
| **Inference** | **40%** | echo + mlx; vLLM va OpenAI backendlari **yo'q** |
| Interfeyslar (CLI/API/MCP/bot/SDK) | 90% | Ishlaydi |
| Web (Next.js) | 85% | Build toza, ~8 nuqson qolgan |
| **Xavfsizlik / auth** | **20%** | API ochiq |
| Trening (F3/F4) | 70% | Quvur bor, data yo'q |
| **Ops / CI / deploy** | **35%** | CI yo'q, server profili ishlamaydi |

### Mahsulot tayyorligi — **~30%**

Foydalanuvchi bugun tizimni o'rnatsa: model yo'q (macOS'dan tashqarida),
baza bo'sh, har savolga "ishonchli javob shakllantirilmadi" oladi.
**Bitta ham foydali javob yo'q.**

`docs/14-yakuniy-hisobot.md` "kod 100%" deydi. Kod bo'yicha bu deyarli to'g'ri,
lekin **inference qatlami 100% emas** (vLLM/OpenAI yo'q) va **xavfsizlik
umuman hisobga olinmagan**. Shuning uchun "100%" raqami optimistik.

---

## 7. Yakunlash strategiyasi

Tartib **ataylab** shunday: har bosqich o'zidan keyingisini o'lchash imkonini beradi.

### Bosqich 0 — Poydevor (1 hafta) · bularsiz qolgani ko'r ishlaydi

| # | Ish | Nega birinchi |
|---|---|---|
| 0.1 | **`openai_backend.py` yozish** (OpenAI-mos API: Ollama, vLLM, o'z serveri) | Bitta fayl butun loyihani macOS qamog'idan chiqaradi. `backend.py` allaqachon uni kutadi. **Eng katta ta'sir/mehnat nisbati.** |
| 0.2 | **CI o'rnatish** (`.github/workflows/ci.yml`: pytest + ruff + mypy + tsc + next build) | 755 test bor, ularni hech kim yurgizmaydi |
| 0.3 | `uzlegal doctor` ni platformaga bog'liq qilish (N1) | Yangi ishtirokchi birinchi buyruqdayoq yiqilgan tizimni ko'radi |
| 0.4 | `/v1/health` ni haqiqiy indeksdan o'qish (N2–N4) | Monitoring yolg'on gapirsa, u monitoring emas |
| 0.5 | `verify-audit.mts` ni kodga qayta ulash (N5) | Noto'g'ri signal beradigan vosita — yo'qidan yomon |

**Chiqish mezoni:** CI yashil, `doctor` har platformada ishlaydi, Ollama orqali
Linux'da javob olinadi.

### Bosqich 1 — Ma'lumot (3–4 hafta, fonda) · eng uzun yo'l

| # | Ish |
|---|---|
| 1.1 | 20 ustuvor kodeksni yuklash (`PRIORITY_DOCS`) — ~7 soat. **Darhol boshlansin** |
| 1.2 | `uzlegal index build` va e2e testlarni yoqish (14 skip → 0) |
| 1.3 | Qolgan korpusni fonda yuklash (`kb discover` → `sync`), ~17 kun |
| 1.4 | Kirill hujjatlar uchun translitni ulash (web tomonida ham) |
| 1.5 | Har 500 hujjatda `pipeline validate` — karantin ≤ 5% |

**Muhim:** 1.1 dan keyin tizim **allaqachon foydali** — 20 kodeks eng ko'p
so'raladigan savollarning katta qismini qoplaydi. Demo nuqtasi shu yerda,
17 kun kutish shart emas.

**Chiqish mezoni:** 20 kodeks indekslangan, e2e testlar yashil,
`retrieval-gold-v1` haqiqiy korpusda qayta o'lchangan.

### Bosqich 2 — Xavfsizlik (1 hafta) · ommaviy chiqishdan oldin majburiy

| # | Ish |
|---|---|
| 2.1 | Python API'ga API-key autentifikatsiyasi (`UZLEGAL_API_KEYS` ni ulash) |
| 2.2 | `/v1/admin/*` ni alohida admin kalit ostiga olish |
| 2.3 | `users/limits.py` ni API qatlamiga majburlash (reja limitlari) |
| 2.4 | Rate-limit (IP + kalit bo'yicha) |
| 2.5 | Web: webhook fail-open, `isAdmin` guruh eskalatsiyasi, DOCX zip-bomba |
| 2.6 | CORS va so'rov hajmi chegaralari |

**Chiqish mezoni:** kalitsiz `/v1/admin/*` → 401. Xavfsizlik testlari CI da.

### Bosqich 3 — Sifat o'lchovi (1 hafta) · bularsiz keyingi hamma narsa taxmin

| # | Ish |
|---|---|
| 3.1 | `smoke-50` va `traps-30` ni **haqiqiy korpusda** yurgizish |
| 3.2 | `gold-500` ni kengaytirish (hozir 36 holat — statistik jihatdan kam) |
| 3.3 | Hallucination o'lchovi: gate'siz vs gate bilan |
| 3.4 | `make eval-smoke` ni CI ga ulash (regressiya bloki) |

**Chiqish mezoni:** Recall@10 ≥ 90%, deprecated leak = 0%, refusal rate o'lchangan.

### Bosqich 4 — Foydalanuvchi yuzasi (1–2 hafta)

Web auditidan qolgan P2 lar: markdown render (`parse_mode`), `.docx` to'ldirish
joyi, mobil moslashuv (`@media` umuman yo'q), rasm/ovoz xabariga javob,
`chunk.ts` soxta modda regexi.

### Bosqich 5 — Model sifati (uzoq, parallel)

F3/F4: yurist tekshiruvi. **Bu yo'lni qisqartirish mumkin** — LoRA'siz ham
RAG + yaxshi prompt ~70% aniqlik beradi (`docs/11` o'zi shunday deydi).
Adapterlarni **v1.0 dan keyinga** qoldirish va avval haqiqiy foydalanuvchi
fikrini olish oqilona.

### Bosqich 6 — Huquqiy (eng uzun muddat, eng erta boshlanadi)

Foydalanuvchi shartnomasi, maxfiylik siyosati, javobgarlik cheklovi,
"Shaxsga doir ma'lumotlar to'g'risida"gi qonun bo'yicha lokalizatsiya.
**Yurist talab qiladi — bugun boshlansin**, chunki texnik ishga parallel ketadi.

---

## 8. Tavsiya etilgan darhol qadamlar (bu hafta)

1. **`openai_backend.py` yozish** — bir kunlik ish, loyihani platformadan ozod qiladi
2. **20 kodeksni yuklashni bugun boshlash** — 7 soat, fonda ketadi
3. **CI qo'shish** — yarim kunlik ish, keyingi har bir o'zgarishni himoya qiladi
4. **API'ni yopish** — `/v1/admin/*` hozir ochiq
5. **`docs/14` dagi "kod 100%" ni tuzatish** — inference 40%, xavfsizlik 20%

---

## 9. Eng katta risk

`docs/11` R9 ni "bus factor 1" deb yozgan va **bu to'g'ri**. Lekin men
undan kattaroq riskni ko'rdim:

**Hujjat kodni ortda qoldirmoqda.** `docs/14` "kod 100%" deydi, README esa
hamon "Faza 0 — dizayn bosqichi" deydi; `deploy/` GPU serverni tasvirlaydi,
lekin unga kerakli backend yo'q; `verify-audit` tuzatilgan narsani buzuq deydi.
Har biri alohida kichik, birgalikda esa **loyihaning haqiqiy holatini
bilib bo'lmay qoladi** — bu bir kishilik loyihada eng qimmat nosozlik turi.

Yechim arzon: har fazani **bajariladigan tekshiruv** bilan bog'lash
(CI, `verify-audit`, `doctor`), matnga emas. Kod o'zi haqida gapirsin.
