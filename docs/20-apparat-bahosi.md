# 20 — Apparat bahosi: bu kompyuter loyihani ko'tara oladimi

**Sana:** 2026-08-13 · **Usul:** taxmin emas, **shu mashinada o'lchangan**

---

## 1. Qisqa javob

| Maqsad | Baho |
|--------|------|
| **Ishlab chiqish va tadqiqot** | ✅ **A'lo** — talabdan ortiq |
| **Bir foydalanuvchi uchun demo** | ✅ Ishlaydi, lekin sekin (60–90 s) |
| **Yopiq beta (10–30 foydalanuvchi)** | ⚠️ Chegarada — navbat paydo bo'ladi |
| **Ishlab chiqarish (100+ foydalanuvchi)** | ❌ **Yetmaydi** — GPU bitta va kichik |
| **12B modelni fine-tuning qilish** | ❌ **Mumkin emas** — VRAM yetmaydi |
| **4B modelni fine-tuning qilish** | ✅ Mumkin |

**Yagona to'siq — 8 GB VRAM.** Qolgan hamma narsa ortig'i bilan yetarli.

---

## 2. Apparat

| Komponent | Qiymat | Baho |
|-----------|--------|------|
| CPU | Intel i7-14700KF · 20 yadro / 28 oqim | ✅ Kuchli |
| RAM | **47.8 GB** DDR5-5600 | ✅ Loyiha mo'ljallagan M4 24 GB dan **2×** |
| GPU | NVIDIA RTX 4060 Ti · **8 GB VRAM** · CUDA 13.1 | ⚠️ **Tor joy** |
| Disk | E: 666 GB · D: 439 GB · C: 166 GB bo'sh | ✅ Ortig'i bilan |
| OS | Windows 11 Pro | ✅ |

Tayyor dasturiy ta'minot: Ollama 0.18.2 (`gemma3:12b`, `gemma3:27b`,
`gemma3:4b`, `qwen3.5` va boshqalar allaqachon yuklangan), Docker 28.3.3,
Python 3.13, Node 22.15, Git 2.53.

---

## 3. O'lchangan tezliklar

Bularning hammasi **shu mashinada**, shu sessiyada olingan.

### 3.1 Embedding (BGE-M3, indeks qurish)

| Qurilma | Tezlik | 8 636 bo'lak uchun |
|---------|-------:|-------------------:|
| **CUDA** | **33 bo'lak/s** | **~4.4 daqiqa** |
| CPU (20 yadro) | 1.4 bo'lak/s | ~100 daqiqa |

GPU CPU dan **24 barobar** tez. Indeks qurish — GPU ning eng foydali ishi.

### 3.2 Qidiruv (modelsiz)

| Metrika | Qiymat | Maqsad |
|---------|-------:|-------:|
| Median | **204 ms** | — |
| p95 | **279 ms** | 600 ms ✅ |

Qidiruv **maqsaddan tez**. Bu mashina uchun umuman muammo emas.

### 3.3 Model javobi (gemma3:12b, Ollama)

| Rejim | O'lchandi | Maqsad |
|-------|----------:|-------:|
| `simple` | **61–92 s** | ~5 s ❌ |

**Sabab aniq:** `gemma3:12b` 4-bit da **8.1 GB**, VRAM esa **8.0 GB**.
Model to'liq sig'maydi va bir qismi CPU ga tushadi. Har token uchun
ma'lumot PCIe orqali borib-keladi.

### 3.4 Reranker (CPU da)

| | |
|---|---|
| Median | **32 044 ms** |
| p95 | 41 185 ms |

Amalda ishlatib bo'lmaydi. Lekin bu ahamiyatsiz — reranker o'lchov
asosida **o'chirilgan** (`reports/retrieval-rerank-2026-08-12.md`): u
Recall@10 ni 8 punktga tushirardi.

### 3.5 Korpus yuklash

| | |
|---|---|
| 863 hujjat | ~4.8 soat |
| Tezlik | 20 s/hujjat |

**Bu mashina cheklovi emas** — `robots.txt` dagi `Crawl-delay: 20`.
Eng kuchli serverda ham xuddi shuncha vaqt oladi.

---

## 4. Tor joy: 8 GB VRAM

Butun muammo bitta raqamda.

| Model | Hajm (4-bit) | 8 GB VRAM ga sig'adimi | Kutilayotgan tezlik |
|-------|-------------:|:----------------------:|--------------------:|
| `gemma3:4b` | 3.3 GB | ✅ To'liq | **tez** (~5–10 s) |
| `qwen3.5` | 6.6 GB | ✅ Zichroq | tez |
| **`gemma3:12b`** ⭐ | **8.1 GB** | ❌ Chegarada | **61–92 s** |
| `gemma3:27b` | 17 GB | ❌ Yo'q | juda sekin |
| `gpt-oss:120b` | 65 GB | ❌ Yo'q | ishlamaydi |

⭐ — ADR-001 da tanlangan model.

### Nima uchun 12B sekin

VRAM 8.0 GB, model 8.1 GB. Ustiga KV-cache va kontekst kerak (huquqiy
kontekst ~6 000 token). Natijada modelning bir qismi tizim xotirasida
qoladi va har token uchun PCIe orqali ko'chiriladi.

Bu **arifmetik cheklov** — kod bilan hal qilinmaydi.

### Uchta yo'l

| Yo'l | Tezlik | Sifat | Xarajat |
|------|--------|-------|---------|
| **A.** `gemma3:4b` ga o'tish | ~5–10 s | pastroq | **0** |
| **B.** 16–24 GB GPU | ~8–12 s | to'liq | ~$800–1600 |
| **C.** Server (A100/H100) | ~6 s, parallel agentlar | to'liq | oyiga ~$350–1100 |

**A yo'li bitta buyruq bilan sinaladi:**

```bash
uzlegal models use ollama-gemma3-4b
uzlegal eval safety --suite traps-30
```

Agar 4B da `traps-30` natijasi 12B nikidan sezilarli past bo'lmasa —
bu mashinada beta uchun yetarli.

---

## 5. Nima uchun RAM va CPU muammo emas

Loyiha `docs/02` da **24 GB unified memory** (MacBook Air M4) uchun
mo'ljallangan va byudjet shunga qurilgan (`RESERVED_GB = 9.0`).

Bu mashinada **47.8 GB** bor — ya'ni ikki barobar. Indeks qurish paytida
eng yuqori sarf **40.9 GB** ni ko'rsatdi va u ham bemalol sig'di.

20 yadro esa parsing, chunking va BM25 uchun ortig'i bilan yetarli:
863 hujjatni chunklash bir necha soniya oladi.

---

## 6. Loyihaning uchta rejimi va ularning talabi

| Rejim | Nima kerak | Bu mashinada |
|-------|-----------|--------------|
| **Ma'lumot quvuri** (`kb sync`, `index build`) | Disk + GPU | ✅ A'lo |
| **Qidiruv** (`search`, `/v1/search`) | Faqat embedding | ✅ A'lo (204 ms) |
| **To'liq maslahat** (`ask`, `/v1/consult`) | LLM inference | ⚠️ Sekin (60–90 s) |

**Muhim xulosa:** loyihaning **ikkita rejimidan uchtasi** bu mashinada
mukammal ishlaydi. Faqat model javobi sekin, va u ham konfiguratsiya
bilan hal qilinadi.

---

## 7. Nechta foydalanuvchini ko'taradi

GPU **bitta** va model **navbat bilan** javob beradi (Ollama parallel
so'rovlarni ketma-ket bajaradi).

| Foydalanuvchi | Kutish vaqti | Baho |
|---------------|-------------:|------|
| 1 | 60–90 s | ✅ Maqbul |
| 5 (bir vaqtda) | 5–7 daqiqa | ⚠️ Chegarada |
| 20 (bir vaqtda) | 20–30 daqiqa | ❌ Yaramaydi |

`gemma3:4b` bilan bu raqamlar taxminan **6–10 barobar** yaxshilanadi.

Qidiruv (`/v1/search`) esa modelsiz ishlaydi va **yuzlab** so'rovni
bemalol ko'taradi — bu muhim, chunki foydalanuvchilarning katta qismi
aslida qidiruv qiladi, maslahat emas.

---

## 8. Fine-tuning imkoniyati

| Model | QLoRA uchun VRAM | Bu mashinada |
|-------|-----------------:|--------------|
| 12B | ~10–12 GB | ❌ **Yetmaydi** |
| 4B | ~5–6 GB | ✅ Sig'adi |

Ustiga trening kodi hozir `mlx_lm` ga bog'langan — u **faqat macOS**.
CUDA yo'li (`peft` + `transformers`) hali yozilmagan (`docs/18` § 5).

Ya'ni bu mashinada fine-tuning uchun **ikkita ish** kerak: kod yo'li va
kichikroq model. Yoki bulut GPU (~$50, `docs/11` bahosi).

---

## 9. Ishga tushirish rejasi — shu mashinada

### Bugun ishlaydigan holat

```bash
uzlegal doctor                  # muhit tekshiruvi
uzlegal search "sinov muddati"  # 204 ms
uzlegal serve                   # API + Web
```

Qidiruv, hujjat tahlili va bilim bazasi — hammasi tayyor.

### Beta uchun tavsiya

1. **`gemma3:4b` ga o'ting** va `traps-30` ni qayta o'lchang.
   Sifat farqi kichik bo'lsa — 6–10× tezlik tekinga keladi.
2. **Rate-limit ni pasaytiring** (`per_ip_minute`) — navbat cho'zilib
   ketmasin.
3. **Qidiruvni alohida targ'ib qiling** — u tez va modelsiz ishlaydi.

### Ishlab chiqarish uchun

Repo egasi serverga ega. `deploy/docker-compose.server.yaml` tayyor va
`openai` backend orqali vLLM ga ulanadi. Serverning GPU si 24 GB dan
katta bo'lsa — `gemma3:12b` to'liq tezlikda ishlaydi.

---

## 10. Xulosa

Bu mashina loyiha uchun **kutilganidan yaxshi**: RAM ikki barobar,
CPU kuchli, disk yetarli, GPU esa ishlaydi va embeddingda 24× tezlik
beradi.

Yagona cheklov — **VRAM hajmi**, va u faqat bitta narsaga ta'sir
qiladi: 12B modelning javob tezligiga. Bu ham **konfiguratsiya
masalasi**, arxitektura masalasi emas — model almashtirish bitta buyruq
(`uzlegal models use`), va ADR-003 dagi «bitta yadro, almashadigan
model» qarori aynan shuni ko'zlagan edi.

**Ishlab chiqish va beta uchun: yetarli.**
**Ishlab chiqarish uchun: server kerak** — u repo egasida bor.
