# 15 — GPU serverda ishga tushirish

**Sana:** 2026-08-11 · **Holat:** reja

Bu hujjat uzlegal-ai ni GPU serverda toʻliq ishga tushirish uchun
**aniq qadamlar** beradi. Hozir Mac da kod 100% tayyor — faqat GPU
serverdagi ishlar qolgan.

---

## 1. Server talablari

| Talab | Minimum | Tavsiya |
|-------|---------|---------|
| GPU | NVIDIA A100 40GB | A100 80GB yoki H100 |
| RAM | 64 GB | 128 GB |
| Disk | 200 GB SSD | 500 GB NVMe |
| OS | Ubuntu 22.04+ | Ubuntu 24.04 |
| CUDA | 12.1+ | 12.4+ |
| Docker | 24.0+ | 27.0+ |
| nvidia-container-toolkit | 1.14+ | latest |

---

## 2. Model tanlovi (serverda)

Mac da `gemma3-12b` (4-bit, 8GB) ishlatildi. Serverda **yaxshiroq model**:

| Model | Hajm | GPU xotira | Oʻzbek sifati | Tavsiya |
|-------|------|------------|---------------|---------|
| **Qwen2.5-32B-Instruct** | 32B fp16 | ~65 GB | Juda yaxshi | ✅ A100 80GB |
| Qwen2.5-72B-Instruct-GPTQ-Int4 | 72B 4-bit | ~40 GB | Eng yaxshi | A100 80GB, sekinroq |
| Llama-3.1-70B-Instruct-GPTQ-Int4 | 70B 4-bit | ~38 GB | Yaxshi | A100 80GB |
| Gemma-3-27B-Instruct | 27B fp16 | ~55 GB | Yaxshi | A100 80GB |
| **Mistral-Small-3.2-24B** | 24B fp16 | ~50 GB | Oʻrtacha | ✅ A100 40GB |

**Tavsiya:** `Qwen2.5-32B-Instruct` — oʻzbek tilida eng kuchli ochiq model,
A100 80GB da fp16 da ishlaydi, vLLM multi-LoRA qoʻllab-quvvatlaydi.

---

## 3. Arxitektura (server profili)

```
┌──────────────────────────────────────────────────────────┐
│                    docker compose                         │
│                                                           │
│  ┌─────────┐  ┌──────────┐  ┌───────────────┐           │
│  │ vLLM    │  │ Qdrant   │  │ Elasticsearch │           │
│  │ :8000   │  │ :6333    │  │ :9200         │           │
│  │ GPU     │  │ vectors  │  │ lexical       │           │
│  └────┬────┘  └────┬─────┘  └──────┬────────┘           │
│       │            │               │                     │
│  ┌────┴────────────┴───────────────┴──────┐              │
│  │           uzlegal-api :8080            │              │
│  │  consult() → RAG → agents → gate      │              │
│  └────────────────┬───────────────────────┘              │
│                   │                                      │
│  ┌────────────────┴───────────────────────┐              │
│  │           uzlegal-web :3000            │              │
│  │           uzlegal-bot (TG)             │              │
│  │           uzlegal-mcp :8081            │              │
│  └────────────────────────────────────────┘              │
│                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ embedder │  │ reranker │  │ postgres │               │
│  │ :8002    │  │ :8001    │  │ :5432    │               │
│  └──────────┘  └──────────┘  └──────────┘               │
│                                                           │
│  ┌──────────────────────┐                                │
│  │ otel-collector :4317 │  → Grafana/Prometheus          │
│  └──────────────────────┘                                │
└──────────────────────────────────────────────────────────┘
```

---

## 4. Qadamlar

### 4.1. Serverga ulanish va tayyorgarlik

```bash
ssh user@gpu-server
sudo apt update && sudo apt upgrade -y
sudo apt install -y git docker.io docker-compose-plugin nvidia-container-toolkit
sudo systemctl enable --now docker
sudo nvidia-smi  # GPU koʻrinishini tekshir
```

### 4.2. Repo klonlash

```bash
git clone https://github.com/ShokirjonMK/uzlegal-ai.git
cd uzlegal-ai
cp .env.example .env
```

### 4.3. `.env` ni toʻldirish

```bash
# .env (server uchun)
UZLEGAL_PROFILE=server

# Model
VLLM_MODEL=Qwen/Qwen2.5-32B-Instruct
VLLM_GPU_MEMORY_UTILIZATION=0.90
VLLM_TENSOR_PARALLEL_SIZE=1  # 1 GPU uchun, 2+ GPU bo'lsa o'zgartir

# Telegram bot
UZLEGAL_TELEGRAM_BOT_TOKEN=<token>
UZLEGAL_TELEGRAM_CHAT_ID=<chat_id>

# PostgreSQL
POSTGRES_PASSWORD=<kuchli_parol>
POSTGRES_DSN=postgresql://uzlegal:<parol>@postgres:5432/uzlegal

# API
UZLEGAL_API_KEY=<api_kaliti>

# HuggingFace (model yuklab olish uchun)
HF_TOKEN=<huggingface_token>
```

### 4.4. Docker compose (server uchun yozish kerak)

`deploy/docker-compose.server.yaml` yaratilishi kerak:

```yaml
services:
  # ── LLM ──────────────────────────────────────────────
  vllm:
    image: vllm/vllm-openai:latest
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    volumes:
      - hf-cache:/root/.cache/huggingface
      - ./adapters:/adapters:ro
    environment:
      - HF_TOKEN=${HF_TOKEN}
      - VLLM_ATTENTION_BACKEND=FLASHINFER
    command: >
      --model ${VLLM_MODEL:-Qwen/Qwen2.5-32B-Instruct}
      --dtype bfloat16
      --max-model-len 32768
      --gpu-memory-utilization ${VLLM_GPU_MEMORY_UTILIZATION:-0.90}
      --tensor-parallel-size ${VLLM_TENSOR_PARALLEL_SIZE:-1}
      --enable-lora
      --max-loras 5
      --max-lora-rank 16
      --enable-prefix-caching
      --port 8000
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s

  # ── Embedding ────────────────────────────────────────
  embedder:
    image: ghcr.io/huggingface/text-embeddings-inference:1.5
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    command: --model-id BAAI/bge-m3 --port 8002
    ports:
      - "8002:8002"

  # ── Reranker ─────────────────────────────────────────
  reranker:
    image: ghcr.io/huggingface/text-embeddings-inference:1.5
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    command: --model-id BAAI/bge-reranker-v2-m3 --port 8001
    ports:
      - "8001:8001"

  # ── Vektor DB ────────────────────────────────────────
  qdrant:
    image: qdrant/qdrant:v1.12.4
    volumes:
      - qdrant-data:/qdrant/storage
    ports:
      - "6333:6333"

  # ── Leksik qidiruv ──────────────────────────────────
  elasticsearch:
    image: elasticsearch:8.15.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - ES_JAVA_OPTS=-Xms512m -Xmx2g
    volumes:
      - es-data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"

  # ── PostgreSQL ───────────────────────────────────────
  postgres:
    image: postgres:17-alpine
    environment:
      - POSTGRES_USER=uzlegal
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=uzlegal
    volumes:
      - pg-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  # ── Asosiy API ───────────────────────────────────────
  api:
    build:
      context: .
      dockerfile: deploy/Dockerfile
    environment:
      - UZLEGAL_PROFILE=server
      - UZLEGAL_TELEGRAM_BOT_TOKEN=${UZLEGAL_TELEGRAM_BOT_TOKEN}
      - UZLEGAL_TELEGRAM_CHAT_ID=${UZLEGAL_TELEGRAM_CHAT_ID}
      - POSTGRES_DSN=${POSTGRES_DSN}
    depends_on:
      vllm: { condition: service_healthy }
      qdrant: { condition: service_started }
      elasticsearch: { condition: service_started }
      postgres: { condition: service_started }
    ports:
      - "8080:8080"
    command: ["python", "-m", "uzlegal.api"]

  # ── Telegram bot ─────────────────────────────────────
  bot:
    build:
      context: .
      dockerfile: deploy/Dockerfile
    environment:
      - UZLEGAL_PROFILE=server
      - UZLEGAL_TELEGRAM_BOT_TOKEN=${UZLEGAL_TELEGRAM_BOT_TOKEN}
      - UZLEGAL_TELEGRAM_CHAT_ID=${UZLEGAL_TELEGRAM_CHAT_ID}
      - POSTGRES_DSN=${POSTGRES_DSN}
    depends_on:
      - api
    command: ["python", "-m", "uzlegal.bot"]

  # ── MCP server ───────────────────────────────────────
  mcp:
    build:
      context: .
      dockerfile: deploy/Dockerfile
    environment:
      - UZLEGAL_PROFILE=server
      - POSTGRES_DSN=${POSTGRES_DSN}
    depends_on:
      - api
    ports:
      - "8081:8081"
    command: ["python", "-m", "uzlegal.mcp"]

  # ── Observability ────────────────────────────────────
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.112.0
    volumes:
      - ./deploy/otel-config.yaml:/etc/otelcol-contrib/config.yaml
    ports:
      - "4317:4317"   # OTLP gRPC
      - "9090:9090"   # Prometheus metrics

volumes:
  hf-cache:
  qdrant-data:
  es-data:
  pg-data:
```

### 4.5. Dockerfile (server uchun)

`deploy/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
COPY configs/ configs/

RUN pip install --no-cache-dir -e ".[server]"

EXPOSE 8080
```

### 4.6. Ishga tushirish

```bash
# 1. Model yuklash (birinchi marta)
docker compose -f deploy/docker-compose.server.yaml up vllm -d
# vLLM model yuklaydi — 10-30 daqiqa (tarmoqqa bogʻliq)
docker logs -f uzlegal-ai-vllm-1  # "Started" ni kuting

# 2. Qolgan xizmatlar
docker compose -f deploy/docker-compose.server.yaml up -d

# 3. Qonun bazasini indekslash
docker compose exec api python -m uzlegal.cli pipeline ingest \
  --source ./data/corpus/ --profile server

# 4. Tekshirish
curl http://localhost:8080/v1/health
curl -X POST http://localhost:8080/v1/consult \
  -H "content-type: application/json" \
  -d '{"question": "Mehnat shartnomasi qanday bekor qilinadi?"}'
```

---

## 5. Serverda qilinadigan ishlar (Mac da qilib boʻlmaydi)

| # | Ish | Sabab |
|---|-----|-------|
| 1 | **Haqiqiy model bilan end-to-end test** | Mac dagi 12B model sifati past, 32B kerak |
| 2 | **LoRA adapterlarni trening qilish** | GPU kerak (A100 da ~2 soat/adapter) |
| 3 | **Toʻliq korpusni indekslash** | 40,000 hujjat × embedding = GPU kerak |
| 4 | **Embedding fine-tuning** | GPU kerak |
| 5 | **vLLM multi-LoRA bilan agentlar** | 5 agent parallel = faqat vLLM |
| 6 | **Yuk testi** | 50+ parallel foydalanuvchi |
| 7 | **Canary deploy tizimi** | Ishlab chiqarish muhiti kerak |
| 8 | **Qdrant + Elasticsearch migratsiya** | LanceDB/tantivy dan koʻchirish |
| 9 | **OTLP tracing sozlash** | Grafana/Prometheus kerak |
| 10 | **PII masking testi** | Haqiqiy maʼlumot bilan |

### 5.1. LoRA trening tartibi (serverda)

```bash
# 1. Trening maʼlumoti tayyorlash
uzlegal train generate --role jurist --count 500 --output data/training/jurist/

# 2. Yurist tekshiruvi (qoʻlda — 500 namuna × 2 daq = ~17 soat)
uzlegal train verify --input data/training/jurist/

# 3. LoRA trening
uzlegal train lora \
  --base Qwen/Qwen2.5-32B-Instruct \
  --data data/training/jurist/verified.jsonl \
  --output adapters/jurist/v1 \
  --config configs/training/role-lora.yaml

# 4. Har bir rol uchun takrorlash (advocate, prosecutor, professor, judge)
```

### 5.2. Korpus indekslash tartibi

```bash
# 1. Qonun matnlarini yuklash (17 kun — robots.txt cheklovi)
uzlegal pipeline crawl --source lex.uz --output data/corpus/

# 2. Tozalash va validatsiya
uzlegal pipeline validate --input data/corpus/

# 3. Indekslash (GPU bilan — ~2 soat)
uzlegal pipeline ingest --input data/corpus/ --profile server
```

---

## 6. Mac da qolgan ishlar (GPU kerak emas)

| # | Ish | Holat |
|---|-----|-------|
| 1 | Barcha testlarni yashil qilish | ✅ 549 test yashil |
| 2 | Docstringlar toʻliq boʻlsin | bajarilmoqda |
| 3 | Linting (ruff) toza | bajarilmoqda |
| 4 | deploy/ papkasini yaratish | shu hujjatdan keyin |
| 5 | GitHub ga push | bajarilmoqda |
| 6 | TG bot ishlashini tekshirish | bajarilmoqda |

---

## 7. Monitoring (serverda)

```yaml
# deploy/otel-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

exporters:
  prometheus:
    endpoint: 0.0.0.0:9090

processors:
  batch:

service:
  pipelines:
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp]
```

Canary deploy sozlamasi `configs/profiles/server.yaml` da allaqachon bor:
- 5% trafik yangi versiyaga
- 30 daqiqa kuzatish
- Hallucination rate > 2% → avtomatik rollback
