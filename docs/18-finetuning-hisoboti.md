# 18 — Fine-tuning hisoboti

**Sana:** 2026-08-12 · **Savol:** modelni fine-tuning qilish qanday bo'ldi, nimalar qilindi?

---

## 1. Qisqa javob

**Fine-tuning HECH QACHON bajarilmagan.** Bitta ham adapter o'qitilmagan,
bitta ham trening namunasi tayyorlanmagan.

Mavjud narsa — **quvur kodi**. U yozilgan, lekin bugungi kunga qadar
**bir marta ham uchidan-uchgacha ishlatilmagan**, va tekshirganimda
birinchi qadamning o'zi yiqilardi (§ 4).

| Nima | Holat |
|------|-------|
| Trening ma'lumoti (`data/sft/samples.jsonl`) | ❌ yo'q |
| O'qitilgan adapterlar (`adapters/`) | ❌ papka umuman yo'q |
| `configs/models.yaml` → `adapters:` | ❌ `{}` — bo'sh |
| Trening yurgizilgan logi | ❌ yo'q |
| Quvur kodi | ✅ bor (~430 satr) |
| Giperparametrlar (`configs/training/role-lora.yaml`) | ✅ yozilgan va asoslangan |

**Ya'ni hozirgi tizimda rollar farqi faqat PROMPTDAN keladi.**

---

## 2. Reja nima edi

`ADR-003` va `docs/05` bo'yicha: **bitta baza model + beshta LoRA adapter**.

| Element | Qiymat | Nega shunday |
|---------|--------|--------------|
| Baza model | Gemma-3-12B (4-bit) | ADR-001 da o'lchab tanlangan: 3.77/5, o'zbek tili 4.82/5 |
| Adapter usuli | LoRA, rank 16 | Rol adapteri **yangi bilim o'rgatmaydi** — bilim RAG dan keladi. Adapter faqat *qanday gapirishni* o'zgartiradi |
| Alpha | 32 (= 2 × rank) | Amaliyotdagi standart nisbat |
| Maqsad modullar | `q_proj, k_proj, v_proj, o_proj` | Faqat attention. MLP qo'shilsa adapter uch barobar kattalashadi |
| Adapter hajmi | ~40 MB | Beshtasi 200 MB; baza model xotirada **bitta nusxada** qoladi |
| Epoch / LR | 3 / 1e-4 | `docs/05` § 5 |

Nima uchun beshta model emas: 24 GB xotirada beshta 12B model sig'maydi
(~40 GB kerak), adapterlar esa 8.2 GB da hammasi joylashadi.

---

## 3. Quvur qanday ishlashi kerak edi

```
korpus ──► urug' savollar ──► sintetik javob ──► avtomatik filtr
                                                       │
                                                       ▼
                                            YURIST TEKSHIRUVI
                                                       │
                                                       ▼
                                   tekshirilgan dataset ──► LoRA trening
```

| Qadam | Buyruq | Kodi bormi |
|-------|--------|:----------:|
| 1. Urug' savollar | `uzlegal train seed --role advocate` | ✅ (bugun tuzatildi) |
| 2. Sintetik javob generatsiyasi | — | ⚠️ CLI da yo'q |
| 3. Avtomatik filtrlar | `check_sample()`, `filter_samples()` | ✅ |
| 4. Yurist tekshiruvi | `uzlegal train verify` | ✅ |
| 5. Statistika | `uzlegal train stats` | ✅ |
| 6. LoRA trening | `uzlegal train lora --role advocate` | ✅ (lekin § 5 ga qarang) |

### Muhim himoya qoidasi — to'g'ri yozilgan

`configs/training/role-lora.yaml`:

```yaml
data:
  require_verified: true
  min_samples: 500
```

Tekshirilmagan namuna treningga **tushmaydi**, va buni chetlab o'tish
uchun `allow_unverified=True` ni ataylab yozish kerak. Izohda sabab ham
bor:

> Tekshirilmagan yuridik data modelni **ishonch bilan xato qilishga**
> o'rgatadi va bu tekshirilmagan modeldan yomonroq.

Bu to'g'ri qaror va u kodda mustahkamlangan.

---

## 4. Bugun topilgan nuqson: `train seed` yiqilardi

Quvurni sinab ko'rganimda **birinchi qadamning o'zi ishlamadi**:

```
TypeError: Object of type Chunk is not JSON serializable
```

`seed_questions()` `Chunk` obyektining **o'zini** qaytarardi, CLI esa uni
`json.dumps` bilan faylga yozmoqchi bo'lardi.

**Nega testlar tutmadi.** Mavjud testlar natijaning faqat `question` va
`role` maydonlarini tekshirardi va uni **hech qachon JSON ga yozmasdi**:

```python
seeds = list(seed_questions(chunks, "jurist"))
assert all(s["role"] == "jurist" for s in seeds)   # o'tadi
```

Bu — bugun uchragan naqshning yana bir ko'rinishi: **kod bor, test bor,
lekin ikkalasi ham haqiqiy yo'ldan o'tmaydi.**

**Tuzatildi:** endi `ContextRef` ko'rinishida serializatsiya qilinadi va
modda havolasi (`chunk_id`, `doc_title`, `article`) saqlanadi. JSON ga
yozishni tekshiradigan test qo'shildi.

Tasdiq:

```
✓ 5 urug' savol → data/sft/advocate/seeds.jsonl
⚠ Bu tekshirilmagan sintetik material. Yurist tekshiruvisiz treningga
  ishlatilmaydi.
```

---

## 5. Ikkinchi to'siq: trening faqat macOS'da mumkin

`training/lora.py` treningni tashqi buyruqqa uzatadi:

```python
command = [sys.executable, "-m", "mlx_lm.lora", "--model", …]
```

`mlx_lm` — **faqat Apple Silicon**. Ya'ni:

* bu Windows + RTX 4060 Ti mashinada trening **umuman ishga tushmaydi**;
* `deploy/` dagi Linux + GPU serverda ham ishlamaydi.

Bu **aynan inference qatlamidagi muammoning ikkinchi nusxasi** — o'sha
muammoni bugun `openai_backend.py` bilan hal qildim (`docs/16` § 2).
Trening tomonida u hali **hal qilinmagan**.

**Yechim:** `peft` + `transformers` + `bitsandbytes` orqali CUDA yo'li
qo'shish. Mavjud `TrainingConfig` va tekshiruvlar o'zgarmaydi — faqat
bajaruvchi qism almashadi, xuddi `InferenceBackend` dagi kabi.

> ⚠️ **8 GB VRAM cheklovi.** 12B modelni QLoRA bilan o'qitish uchun
> ~10–12 GB VRAM kerak. Bu mashinada 12B **o'qitib bo'lmaydi**.
> Realistik variantlar: `gemma3:4b` (sig'adi) yoki bulut GPU (A100 —
> `docs/11` byudjetida ~$50).

---

## 6. Asosiy to'siq — texnik emas

Quvur tuzatilsa ham, trening **boshlanmaydi**, chunki tekshirilgan
ma'lumot yo'q.

| Talab | Miqdor | Manba |
|-------|--------|-------|
| Tekshirilgan namuna | 2 000 (400 × 5 rol) | `docs/11` Faza 3 |
| Yurist vaqti | ~1 500 soat | `docs/14` § 6 |
| Gold set | 500 savol | `docs/11` Faza 3 |

`docs/11` R1 riskida bu ochiq aytilgan:

> Agar ekspert topilmasa — bu faza to'xtaydi va butun loyiha sifati
> cheklanadi.

---

## 7. Fine-tuningsiz nima yo'qotiladi

`docs/11` § 4 ning o'zi shunday deydi:

> Bu bosqich tugagach tizim **allaqachon foydali** — fine-tuningsiz,
> RAG + baza model bilan ~70% aniqlik.

| Xususiyat | Promptdan (hozir) | Adapterdan (reja) |
|-----------|-------------------|-------------------|
| Rol farqi | ✅ ishlaydi | ✅ kuchliroq |
| Rol sodiqligi | o'lchanmagan | maqsad ≥ 90% |
| Format rioyasi | gate bilan majburlanadi | maqsad ≥ 98% |
| Iqtibos odati | promptda talab qilinadi | o'rgatiladi |
| Kechikish | bir xil | bir xil |
| Xotira | bir xil | +200 MB |

**Xulosa: adapterlar sifat oshiradi, lekin ular BLOKER emas.**

---

## 8. Tavsiya: adapterlarni v1.0 dan KEYINGA qoldirish

Sabablari:

1. **1 500 soat yurist vaqti** — loyihaning eng qimmat resursi. Uni
   adapterga sarflashdan oldin **haqiqiy foydalanuvchi qaysi savollarni
   berishini** bilish kerak.
2. Hozir korpus 20 kodeks. Adapter o'qitilsa, korpus kengaygach u
   **qayta o'qitilishi** kerak bo'ladi.
3. Bir xil yurist vaqtini **gold set** (500 savol) ga sarflash
   ko'proq foyda beradi: u sifatni **o'lchash** imkonini beradi, ya'ni
   keyingi har bir qaror taxminga emas, raqamga tayanadi.
4. `retrieval-gold-v1` hozir atigi **36 holat** — statistik jihatdan
   zaif. Uni 200+ ga kengaytirish adapterdan **arzonroq va tezroq**
   natija beradi.

### Taklif qilinadigan tartib

| # | Ish | Yurist vaqti | Natija |
|---|-----|--------------|--------|
| 1 | `retrieval-gold-v1` → 200 holat | ~20 soat | O'lchov ishonchli bo'ladi |
| 2 | `smoke-50` → `gold-300` | ~60 soat | Uchidan-uchgacha sifat o'lchanadi |
| 3 | Beta foydalanuvchilardan real savollar | 0 soat | Haqiqiy taqsimot ma'lum bo'ladi |
| 4 | **Shundan keyin** rol datasetlari | ~1 500 soat | Adapterlar |

1–3 qadamlar **80 soat** oladi va ular 4-qadamni ancha samaraliroq
qiladi: dataset haqiqiy savollar asosida tuziladi, taxmin asosida emas.

---

## 9. Bugun bajarilgan ish

| # | Ish |
|---|-----|
| 1 | Fine-tuning holati to'liq tekshirildi va hujjatlashtirildi |
| 2 | `train seed` yiqilishi tuzatildi — quvurning birinchi qadami endi ishlaydi |
| 3 | JSON serializatsiyasini tekshiradigan test qo'shildi (regressiya qaytmasin) |
| 4 | Trening yo'lidagi platforma cheklovi aniqlandi va yozildi (§ 5) |
| 5 | 8 GB VRAM da 12B o'qitib bo'lmasligi hisoblandi |

**Bajarilmagan va nega:** haqiqiy trening yurgizilmadi — tekshirilgan
ma'lumot yo'q va uni yaratish yurist ekspertni talab qiladi. Sintetik,
tekshirilmagan ma'lumot bilan adapter chiqarish esa loyihaning o'z
qoidasiga zid (`require_verified: true`) va u modelni **ishonch bilan
xato qilishga** o'rgatardi.
