# 02 — Apparat va runtime

## 1. Maqsadli apparat (o'lchangan)

Ishlab chiqish mashinasi haqiqiy o'lchov natijalari:

```
Model:     MacBook Air (Mac16,12)
Chip:      Apple M4 — 10 core CPU (4P + 6E), 10 core GPU
RAM:       24 GB unified memory
Disk:      460 GB, 239 GB bo'sh
OS:        macOS 15.7.4 (24G517), Metal 3
Muhit:     brew 6.0.15, git 2.50.1, node v25.6.1, uv 0.5.9
           python3 3.9.6 (tizim — yetarli emas, 3.11 kerak)
           ollama / MLX / Docker — o'rnatilmagan
```

Bu **cheklovchi apparat**, ammo to'g'ri arxitektura bilan yetarli. Muhim jihat: Apple Silicon da xotira **unified** — CPU va GPU bir xil RAM ni bo'lishadi, ya'ni model uchun alohida VRAM nusxasi kerak emas. Bu 24 GB ni diskret 24 GB GPU dan samaraliroq qiladi.

## 2. Xotira byudjeti

macOS sukut bo'yicha GPU ga umumiy RAM ning ~65–70% ini ajratadi. Uni ko'tarish mumkin:

```bash
# GPU uchun wired memory chegarasi (24 GB dan 20 GB)
sudo sysctl iogpu.wired_limit_mb=20480

# Doimiy qilish
echo "iogpu.wired_limit_mb=20480" | sudo tee -a /etc/sysctl.conf
```

> Diqqat: 22 GB dan yuqori qo'yilsa tizim beqaror bo'ladi. 20 GB — xavfsiz maksimum.

### Byudjet taqsimoti (`local-dev` profili)

| Komponent | Hajm | Izoh |
|-----------|------|------|
| macOS + fon jarayonlari | ~4.0 GB | Ochiq ilovalarga qarab |
| Baza model (14B, 4-bit) | ~8.0 GB | Bir marta yuklanadi |
| LoRA adapterlar (5 × 40 MB) | ~0.2 GB | Hammasi xotirada |
| KV-cache (8k kontekst) | ~1.5 GB | Kontekst uzunligiga proporsional |
| Embedding modeli (BGE-M3) | ~1.2 GB | Kvantlangan |
| Reranker | ~0.6 GB | Kerak bo'lganda yuklanadi |
| Vektor indeks (LanceDB, mmap) | ~0.5 GB | Disk asosiy, RAM da qism |
| Ilova + API + runtime | ~1.0 GB | |
| **Jami** | **~17 GB** | **~7 GB zaxira** |

Zaxira ataylab katta qoldirilgan: brauzer, IDE va trening jarayoni bir vaqtda ishlashi mumkin.

### Nima sig'maydi

| Konfiguratsiya | Hajm | Verdikt |
|----------------|------|---------|
| 14B 4-bit | 8.0 GB | ✅ Qulay |
| 14B 8-bit | 15.0 GB | ⚠️ Ishlaydi, lekin zaxira yo'q |
| 24B 4-bit | 13.5 GB | ⚠️ Faqat inference, trening yo'q |
| 30B-A3B MoE 4-bit | 17.0 GB | ⚠️ Juda qisiq |
| 32B 4-bit | 18.0 GB | ❌ Beqaror |
| 70B har qanday | 35 GB+ | ❌ Imkonsiz |

## 3. Runtime tanlovi: MLX

Apple Silicon uchun uchta variant baholandi:

| Runtime | Tezlik (M4, 14B 4-bit) | LoRA trening | Adapter almashtirish | Verdikt |
|---------|------------------------|--------------|---------------------|---------|
| **MLX** | ~22 tok/s | ✅ Native | ✅ Tez | **Tanlandi** |
| llama.cpp | ~20 tok/s | ⚠️ Cheklangan | ⚠️ Qayta yuklash | Fallback (GGUF eksport) |
| Ollama | ~19 tok/s | ❌ Yo'q | ⚠️ Modelfile orqali | Faqat tez sinov |
| PyTorch MPS | ~9 tok/s | ✅ | ✅ | Sekin |

**Nima uchun MLX:** Apple tomonidan Metal uchun yozilgan, unified memory ni to'g'ri ishlatadi (nusxa ko'chirmaydi), va — hal qiluvchi jihat — **bir xil framework da ham inference, ham LoRA trening** qiladi. Boshqa variantlarda trening uchun alohida stek kerak bo'lardi.

Batafsil: [ADR-004](adr/ADR-004-serving-runtime.md)

## 4. Baza model nomzodlari

Model **o'lchab tanlanadi**, oldindan emas. Faza 0 ning yakuniy natijasi — asoslantirilgan tanlov.

| Nomzod | Params | 4-bit | Kontekst | Kuchli tomoni | Xavfi |
|--------|--------|-------|----------|---------------|-------|
| **Qwen3-14B** | 14B | 8.0 GB | 32k+ | Reasoning, tool-calling, hujjat tuzilishi | O'zbek tili o'rtacha |
| **Gemma-3-12B-it** | 12B | 7.0 GB | 128k | Ko'p tillilik (140 til), turkiy tillar yaxshiroq | Reasoning zaifroq |
| Mistral-Small-3.2-24B | 24B | 13.5 GB | 128k | Kuchli umumiy sifat | LoRA trening qisiq |
| Qwen3-8B | 8B | 4.5 GB | 32k | Tez, arzon, katta zaxira | Murakkab huquqiy mantiq zaif |

### Baholash protokoli (Faza 0)

100 ta savoldan iborat `bench-uz-legal-v0` to'plami, to'rt o'lchov bo'yicha (har biri 1–5 ball, ikki baholovchi):

1. **O'zbek tili ravonligi** — matn tabiiymi, yuridik uslubga mos keladimi
2. **Yuridik atama to'g'riligi** — "vindikatsiya", "sud'ya" emas "sudya", atamalar chalkashmaydimi
3. **Mulohaza sifati** — berilgan kontekstdan to'g'ri xulosa chiqara oladimi
4. **Ko'rsatmaga rioya** — rol, format, "bilmasang aytma" ni bajaradimi

Muhim: bu bosqichda modelning **qonunni bilishi baholanmaydi** — u RAG dan keladi. Baholanadigan narsa: berilgan matn ustida o'zbek tilida qanchalik yaxshi *mulohaza yuritadi*.

```bash
uzlegal models bench \
  --candidates qwen3-14b-4bit,gemma3-12b-4bit,mistral-small-24b-4bit \
  --suite bench-uz-legal-v0 \
  --judges 2 \
  --out reports/model-selection.md
```

### Qaror qoidasi

- Umumiy ball farqi < 0.3 bo'lsa → **kichikroq modelni** tanlash (zaxira muhimroq)
- O'zbek tili balli < 3.0 bo'lsa → nomzod rad etiladi, model qanchalik aqlli bo'lmasin
- Tanlov `docs/adr/ADR-001-base-model.md` ga natijalar bilan yoziladi

## 5. Kvantlash strategiyasi

| Bosqich | Format | Sabab |
|---------|--------|-------|
| Trening | 4-bit NF4 baza + fp16 LoRA | QLoRA: baza muzlatilgan, faqat adapter o'qitiladi |
| Local inference | 4-bit group-size 64 | Sifat/hajm muvozanati |
| Server inference | 8-bit yoki AWQ | Xotira yetarli, sifat yuqori |
| Eksport | GGUF Q4_K_M | llama.cpp / Ollama moslik |

**4-bit sifat yo'qotishi:** 14B modelda perplexity ~2–4% oshadi. Yuridik vazifada bu sezilarli emas, chunki faktlar RAG dan keladi — model faqat qayta ifodalaydi. Bu [T1 tamoyili](01-architecture.md#1-dizayn-tamoyillari) ning amaliy foydasi.

## 6. Kutilayotgan ishlash ko'rsatkichlari (M4 24 GB)

Baholangan qiymatlar, Faza 0 da o'lchanadi va yangilanadi:

| Operatsiya | Kutilgan | Izoh |
|------------|----------|------|
| Model yuklash (sovuq) | 8–12 s | Disk tezligiga bog'liq |
| Adapter almashtirish | ~50 ms | 40 MB ko'chirish |
| Prompt processing | ~180 tok/s | 6k kontekst ≈ 33 s ❗ |
| Generatsiya | ~22 tok/s | 500 token ≈ 23 s |
| Embedding (BGE-M3) | ~40 chunk/s | Indekslashda |
| Retrieval (gibrid + rerank) | 300–600 ms | Indeks hajmiga bog'liq |
| **Bitta agent javobi** | **6–10 s** | |
| **To'liq debate (5 agent)** | **40–70 s** | ❗ Maqsad 45 s |

### Prompt processing muammosi va yechimi

Yuqoridagi jadvalda eng katta xarajat — kontekstni qayta ishlash (33 s), generatsiya emas. Beshta agent bir xil huquqiy kontekstni oladi, ya'ni bu 33 s **besh marta** takrorlanishi mumkin edi.

Yechim — **prefix KV-cache**:

```
[TIZIM PROMPTI] [HUQUQIY KONTEKST — barcha agentlar uchun bir xil] │ [ROL PROMPTI] [SAVOL]
└──────────── bir marta hisoblanadi, cache lanadi ─────────────────┘ └── har agent uchun qisqa ──┘
```

Umumiy prefiks bir marta hisoblanadi va KV-cache da saqlanadi; har bir agent faqat o'z qisqa qismini qayta ishlaydi. Bu debate vaqtini ~2.5 barobar qisqartiradi (70 s → ~28 s).

Bu MLX da `mlx_lm.cache` orqali amalga oshiriladi va [ADR-005](adr/ADR-005-agent-orchestration.md) da tavsiflangan.

## 7. Muhitni o'rnatish

```bash
# 1. Python 3.11 (tizim 3.9 — MLX uchun eski)
brew install python@3.11
uv venv --python 3.11 .venv
source .venv/bin/activate

# 2. MLX stek
uv pip install mlx mlx-lm

# 3. RAG stek
uv pip install lancedb sentence-transformers rank-bm25 FlagEmbedding

# 4. Orkestratsiya va API
uv pip install langgraph fastapi uvicorn typer pydantic-settings

# 5. GPU chegarasi
sudo sysctl iogpu.wired_limit_mb=20480

# 6. Tekshirish
python -c "import mlx.core as mx; print('Metal:', mx.metal.is_available())"
```

Yoki: `make setup-mac`

## 8. Trening apparati

LoRA trening shu mashinada mumkin, lekin uzoq:

| Konfiguratsiya | Vaqt (5k namuna, 2 epoch) | Izoh |
|----------------|---------------------------|------|
| 14B, 4-bit, LoRA r=16, seq 2048 | ~8–10 soat | Kechasi qo'yiladi |
| 14B, 4-bit, LoRA r=32, seq 4096 | ~18–22 soat | Uzun hujjatlar uchun |
| 8B, 4-bit, LoRA r=16, seq 2048 | ~4–5 soat | Tez iteratsiya |

Beshta adapter × 10 soat = **~50 soat**. Bu ketma-ket ~1 hafta.

**Tavsiya:** iteratsiya uchun 8B da tez sinash (4 soat), yakuniy adapterlar uchun bulutda A100 ijaraga olish (~$1.5/soat × 8 soat = **~$12 barcha adapterlar uchun**). Local trening ishlaydi, lekin bulut 10× tezroq va deyarli bepul. Ma'lumot maxfiy bo'lsa — local qoladi.

## 9. Boshqa apparatga o'tish

Arxitektura apparatdan mustaqil. Profil almashtiriladi:

| Profil | Apparat | Model | Runtime | Debate vaqti |
|--------|---------|-------|---------|--------------|
| `local-dev` | M4 24 GB | 14B 4-bit | MLX | ~30 s |
| `workstation` | M4 Max 64 GB | 32B 4-bit | MLX | ~20 s |
| `server` | A100 80 GB | 32B fp16 | vLLM | ~6 s |
| `server-scale` | 2×H100 | 70B AWQ | vLLM + tensor parallel | ~4 s |

Kod o'zgarmaydi — `InferenceBackend` interfeysi bir xil, `configs/profiles/*.yaml` almashadi.

## 10. Keyingi hujjat

→ [03 — Ma'lumot quvuri](03-data-pipeline.md)
