# 21 — Sprint spetsifikatsiyasi: W1 vaqt mashinasi va W2 javob pasporti

**Sana:** 2026-08-14
**Manba:** bozor strategiyasi — W1 va W2 eng yuqori ustuvorlikdagi farqlantiruvchi
imkoniyatlar. Ikkalasi ham *yangi funksiya emas*: mavjud ma'lumot va
infratuzilmani yuzaga chiqarish.

---

## 0. Nima uchun aynan shu ikkisi

| | Nega yagona | Nega arzon |
|---|---|---|
| **W1** Sanaga ko'ra javob | Nizo **voqea sanasidagi** qonun bo'yicha hal qilinadi. Raqiblarda versiya ma'lumoti umuman yo'q | `as_of` allaqachon CLI → core → retrieval bo'ylab o'tadi. Qolgani — teshiklarni yopish |
| **W2** Javob pasporti | AI chiqishini **auditga yaroqli ish mahsulotiga** aylantiradi | Ed25519 va audit zanjiri allaqachon ishlaydi |

---

## 1. W1 — mavjud holat

`as_of: date | None` quyidagi zanjirdan **allaqachon** o'tadi:

```
CLI --as-of  →  ConsultRequest.as_of  →  ConsultState.as_of
             →  HybridRetriever.search(as_of=)  →  version_filter(as_of=)
             →  agents/roles.py  «HOLAT SANASI: …» promptga
```

MCP (`mcp/server.py:61,81`) va SDK (`sdk.py:65,93`) ham uzatadi.

### 1.1 Yopilishi kerak bo'lgan teshiklar

| # | Teshik | Joy |
|---|---|---|
| **W1-A** | `as_of` berilganda bekor qilingan norma filtrdan **o'tib ketadi** | `retrieval/hybrid.py:189` |
| **W1-B** | `/v1/search` da `as_of` yo'q | `api/app.py:579` `SearchRequest`, `:622` chaqiruv |
| **W1-C** | Javobda `as_of` va sana qamrovi qaytarilmaydi | `core.py:69`, `hybrid.py:210`, `api/app.py:586,597` |
| **W1-D** | Telegram botda `as_of` yo'q | `bot/telegram.py` |
| **W1-E** | Audit yozuvida `as_of` yo'q | `audit.py:130` |

---

## 2. W1-A — xavfsizlik teshigi (eng muhim)

Hozirgi kod (`retrieval/hybrid.py:183-198`):

```python
if chunk.status != "in_force" and as_of is None:   # ← teshik shu yerda
    dropped += 1; continue
```

**Ma'nosi:** `as_of` berilganda `status` tekshiruvi **umuman o'tkazib yuboriladi**.
Bo'lak faqat `valid_from`/`valid_to` bo'yicha filtrlanadi. Agar bekor qilingan
bo'lakning `valid_to` si bo'sh bo'lsa — u javobga tushadi.

Bu faraziy emas: `ingest/versioning.py:359-372` sanani aniqlay olmaganda
`valid_to` ni **ataylab bo'sh qoldiradi**.

### 2.1 To'g'ri semantika

`as_of` berilganda niyat — «shu sanada amalda bo'lgan normani ko'rsat».
Demak:

| Holat | Qaror |
|---|---|
| `valid_to` bor va `valid_to <= as_of` | **Chiqarilsin** — o'sha sanada ham amal qilmagan |
| `valid_from` bor va `valid_from > as_of` | **Chiqarilsin** — hali kuchga kirmagan |
| `status != in_force` va `valid_to` **bo'sh** | **Chiqarilsin** — qachon bekor qilingani noma'lum, ya'ni `as_of` da amalda bo'lganini **tasdiqlab bo'lmaydi** |
| `status == in_force`, sanalar bo'sh | **Qoldirilsin**, lekin *sanasi tasdiqlanmagan* deb belgilansin (§3) |

Uchinchi qator — asosiy o'zgarish. Tamoyil o'zgarmaydi:
**tasdiqlab bo'lmaydigan narsa javobga chiqmaydi.**

### 2.2 Mavjud test ataylab o'zgartiriladi

`tests/unit/test_retrieval.py:179-186` — `test_as_of_bilan_tarixiy_holat`
hozirgi xatti-harakatni **to'g'ri deb qayd etgan**. U yangi semantikaga
moslanadi va izohda nima uchun o'zgargani yoziladi. Bu — bilib turib
qilingan shartnoma o'zgarishi, tasodifiy test buzish emas.

---

## 3. W1-C — sana qamrovini oshkor qilish

### 3.1 Nima uchun bu majburiy

Korpusdagi haqiqiy holat (2026-08-14 da o'lchangan):

| Ko'rsatkich | Qiymat | Ulush |
|---|---|---|
| Bo'laklar | 48 527 | — |
| `valid_from` **bor** | 12 367 | 25.5% |
| `valid_from` **yo'q** | **36 160** | **74.5%** |
| `status = repealed` | 24 | 0.05% |
| Hujjatlar | 792 | — |
| Kamida bitta sanasi bor hujjat | 214 | 27% |

`data/raw/lex.uz/*.meta.json` da hujjat qabul qilingan sana **yo'q** —
faqat yuklab olish metama'lumoti.

Ya'ni tizim «2019-yil holatiga ko'ra» deb so'ralganda manbalarning
to'rtdan uch qismi uchun buni **tasdiqlay olmaydi**. Buni jimgina
qilish — loyihaning o'z hujjatlashtirgan nosozlik naqshi:
*«buyruq muvaffaqiyat haqida xabar beradi, lekin ish bajarilmaydi»*.

### 3.2 Talab

`as_of` berilgan har javob o'z qamrovini qaytarsin:

```python
class DateCoverage(BaseModel):
    confirmed: int   # valid_from ma'lum bo'lgan manbalar
    unknown: int     # tahrir tarixi noma'lum
    as_of: date
```

Qo'shiladigan joylar:
- `RetrievalResult` (`hybrid.py:210`) — `as_of` va `coverage`
- `ConsultResult` (`core.py:69`) — `as_of: date | None`, `date_coverage: DateCoverage | None`
- `SearchResponse` (`api/app.py:597`) — `as_of`, `date_coverage`, `dropped_by_version`
- `SearchResult` (`api/app.py:586`) — `valid_from`, `valid_to`, `status`

Va `unknown > 0` bo'lsa `ConsultResult.caveats` ga o'zbekcha ogohlantirish
qo'shilsin, masalan:

> Manbalarning N tasida tahrir tarixi yo'q — ular uchun joriy matn
> keltirildi. Tarixiy holat kafolatlanmaydi.

---

## 4. W2 — javob pasporti

### 4.1 Asosiy cheklov

`signature.py` — bu **litsenziya tizimi**, umumiy imzo vositasi emas.
Repoda faqat **ochiq kalit** bor (`signature.py:71`). Maxfiy kalit
muallif mashinasida. Demak pasport uchun **alohida, joylashtirishga xos
kalit** kerak — bu yangi tushuncha.

`integrity/` moduli — noto'g'ri yo'l: u sud qarorida pora belgilarini
aniqlaydi, kriptografiya emas.

### 4.2 Joylashuv

Yangi modul: **`src/uzlegal/passport.py`**.

`audit.py` va `signature.py` kabi u ham import-qatlam shartnomasidan
tashqarida (`pyproject.toml` `[tool.importlinter]`), ya'ni uni `core`,
`api` va `cli` bemalol import qila oladi.

### 4.3 Kalit boshqaruvi

| Manba | Ustuvorlik |
|---|---|
| `UZLEGAL_PASSPORT_KEY` — muhit o'zgaruvchisi, PEM | 1 |
| `UZLEGAL_PASSPORT_KEY_FILE` — fayl yo'li | 2 |
| `data/keys/passport_ed25519` — birinchi ishlatishda **avtomatik yaratiladi** | 3 |

Avtomatik yaratilganda ogohlantirish chiqarilsin va ochiq kalit barmoq
izi ko'rsatilsin. Maxfiy kalit `.gitignore` da bo'lishi **shart**.

### 4.4 Pasport tarkibi

Faqat tasdiqlanadigan, shaxsga bog'lanmagan maydonlar:

```
version        "uzlegal-pass.v1"
trace_id
issued_at      ISO-8601 UTC
question_hash  sha256 — savol matni SAQLANMAYDI
answer_hash    sha256 — javob matni SAQLANMAYDI
citations      ["doc_id:article", …]
kb_version
model_version
as_of          null yoki YYYY-MM-DD
gate           {passed, dropped}
key_fingerprint
```

**Savol va javob matni pasportga kirmaydi** — `audit.py` allaqachon shu
tamoyilga amal qiladi (`answer_hash` saqlaydi, matnni emas).

### 4.5 Format

`signature.py:376` dagi kanonik shakl **ayni holda** ishlatilsin:

```python
json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
```

Token: `uzlegal-pass.v1.<b64url(payload)>.<b64url(signature)>`
(`signature.py` dagi `_b64url_encode` / `_b64url_decode_strict` qayta ishlatilsin.)

### 4.6 Ommaviy API

```python
def issue_passport(*, trace_id: str, question: str, answer: str,
                   citations: list[str], kb_version: str,
                   model_version: str | None, as_of: date | None,
                   gate: dict[str, Any] | None) -> str | None

def verify_passport(token: str) -> Passport        # xato bo'lsa PassportError
def passport_public_key() -> str                   # barmoq izi bilan
```

`issue_passport` **hech qachon so'rovni yiqitmasin** — `audit.py:184-186`
kabi xatoda `None` qaytarsin.

### 4.7 Ulanish nuqtalari

| Joy | O'zgarish |
|---|---|
| `core.py:69` `ConsultResult` | `passport: str \| None = None` |
| `core.py:140` atrofi | `_write_audit` yonida pasport chiqarilsin |
| `api/app.py` | `POST /v1/passport/verify` — kalitsiz ochiq bo'lsin (tekshirish ommaviy amal) |
| `cli/` | `uzlegal passport verify <token>` · `uzlegal passport key` |
| `schemas/openapi.yaml` | `ConsultResult` o'zgarishi aks etsin |

---

## 5. Qabul mezonlari

Har biri **bajariladigan tekshiruv** bilan bog'langan — matn bilan emas.

### W1

- [x] **A1** `version_filter` da: `status != "in_force"` va `valid_to` bo'sh bo'lgan bo'lak `as_of` **berilganda ham** chiqariladi. Test: `tests/unit/test_retrieval.py`
- [x] **A2** `test_as_of_bilan_tarixiy_holat` yangi semantikaga moslangan, izohi bilan
- [x] **A3** `POST /v1/search` `as_of` qabul qiladi va uni retrieverga uzatadi
- [x] **A4** `SearchResult` da `valid_from`, `valid_to`, `status` bor
- [x] **A5** `ConsultResult` da `as_of` va `date_coverage` bor
- [x] **A6** `unknown > 0` bo'lganda `caveats` ga o'zbekcha ogohlantirish qo'shiladi
- [x] **A7** Audit yozuvida `as_of` bor
- [x] **A8** Telegram bot `--as-of` yoki `/sana` ni qo'llab-quvvatlaydi

### W2

- [x] **B1** `passport.py` mavjud; `issue_passport` → `verify_passport` aylanma testi o'tadi
- [x] **B2** Buzilgan token `PassportError` beradi (imzo, payload, prefiks — uchala yo'l alohida test)
- [x] **B3** Kalit yo'q bo'lsa avtomatik yaratiladi va `.gitignore` da
- [x] **B4** Pasportda savol yoki javob **matni yo'q** — test buni tekshiradi
- [x] **B5** `ConsultResult.passport` to'ldiriladi
- [x] **B6** `POST /v1/passport/verify` ishlaydi va kalitsiz ochiq
- [x] **B7** `uzlegal passport verify` va `uzlegal passport key` ishlaydi
- [x] **B8** Kalit topilmasa yoki imzolash yiqilsa — so'rov **yiqilmaydi**, `passport = None`

### Umumiy

- [x] **C1** `ruff check` va `ruff format --check` toza
- [x] **C2** `mypy --strict src/uzlegal` — 0 xato
- [x] **C3** `lint-imports` o'tadi
- [x] **C4** `pytest tests/unit tests/integration` — **barcha 921+ test yashil**
- [x] **C5** Yangi testlar nomi **o'zbekcha** (`test_bekor_qilingan_norma_chiqmaydi` uslubida)
- [x] **C6** Hech bir mavjud test o'chirilmagan (A2 dan tashqari — u o'zgartiriladi, o'chirilmaydi)

---

## 6. Chegaralar — bu sprintga kirmaydi

- Korpusdagi `valid_from` bo'shliqlarini to'ldirish — bu ingest ishi, alohida sprint
- LanceDB qatoriga `valid_from` qo'shish (`store.py:229`) — optimizatsiya, hozir kerak emas
- Pasport uchun TypeScript tekshiruvchisi (`web/scripts/`) — keyingi sprint
- `tests/e2e/` katalogini tiklash (`make test-e2e` hozir yiqiladi) — alohida ish

---

## 7. Eng katta risk

`version_filter` — bitta chokepoint va u loyihaning **eng muhim
xavfsizlik kafolatini** (bekor qilingan norma sizishi = 0%) ushlab
turadi. Uni o'zgartirish bevosita shu kafolatga tegadi.

Shuning uchun: W1-A o'zgarishi **avval test bilan qoplansin**, keyin kod
o'zgartirilsin. QA bu nuqtani alohida tekshiradi.

---

## 8. Yakuniy tekshiruv — PM tomonidan mustaqil o'lchangan

**Sana:** 2026-08-14. Quyidagi raqamlar agent hisobotidan emas, PM
tomonidan qayta yugurtirilgan buyruqlardan olingan.

| Tekshiruv | Natija |
|---|---|
| `pytest tests/unit tests/integration` | **965 o'tdi**, 0 yiqildi (82 s) |
| `pytest tests/unit/test_api_auth.py` | **21 o'tdi** (598 s — sekinligi sprintdan oldin ham bor edi) |
| Unit test soni | **921 → 972** (+51) |
| O'chirilgan test | **0** — `git diff` bilan tasdiqlandi |
| `ruff check` / `ruff format --check` | Toza · 126 fayl |
| `mypy --strict src/uzlegal` | **0 xato**, 89 fayl |
| `lint-imports` | 1 shartnoma saqlandi, 0 buzildi |
| `data/keys/` `.gitignore` da | ✅ `.gitignore:40` |

### Xavfsizlik kafolati — qayta tasdiqlangan

`version_filter` beshta holatda mustaqil sinovdan o'tkazildi:

| Holat | Kutilgan | Natija |
|---|---|---|
| `repealed`, sanalar bo'sh, `as_of` berilgan | chiqarilsin | ✅ chiqarildi |
| `repealed`, `as_of=None` | chiqarilsin | ✅ chiqarildi |
| `repealed`, `valid_to > as_of` | qolsin | ✅ qoldi |
| `in_force`, sanalar bo'sh | qolsin | ✅ qoldi |
| `valid_from > as_of` | chiqarilsin | ✅ chiqarildi |

### Pasport — mustaqil sindirish urinishi

| Hujum | Natija |
|---|---|
| To'g'ri pasport → `verify` | ✅ o'tdi (729 belgi) |
| Savol matni payloadda | ✅ **yo'q** |
| Javob matni payloadda | ✅ **yo'q** |
| Payload buzildi | ✅ `PassportError` |
| Imzo buzildi | ✅ `PassportError` |
| Prefiks buzildi | ✅ `PassportError` |
| Kalit yo'q → avtomatik yaratildi | ✅ ogohlantirish bilan |

Payload kalitlari: `answer_hash`, `as_of`, `citations`, `gate`,
`issued_at`, `kb_version`, `key_fingerprint`, `model_version`,
`question_hash`, `trace_id`, `version` — §4.4 ga aynan mos.
