# UzLegal-AI — server profili (docs/15 § 4.5)
#
# Bu tasvir **faqat ilova qatlamini** oladi: API, bot, MCP. Model, vektor
# bazasi va leksik qidiruv alohida xizmatlar sifatida ishlaydi
# (`docker-compose.server.yaml`).
#
# Nima uchun `slim`, `cuda` emas: bu konteynerda GPU ishlatilmaydi —
# model chaqiruvi vLLM ga, embedding esa TEI ga HTTP orqali boradi.
# CUDA tasviri 6 GB qo'shardi va hech qanday foyda bermasdi.

FROM python:3.11-slim AS base

# `PYTHONUNBUFFERED` — konteyner loglari darhol ko'rinsin (buferlanmasin).
# `PIP_NO_CACHE_DIR` — tasvir hajmini ~200 MB kamaytiradi.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UZLEGAL_PROFILE=server

WORKDIR /app

# `curl` — healthcheck uchun; `git` — ba'zi paketlar o'rnatishda so'raydi.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------------------------------- #
# Bog'liqliklar — kod o'zgarganda qayta o'rnatilmasligi uchun alohida qatlam
# --------------------------------------------------------------------------- #

COPY pyproject.toml README.md ./
COPY src/uzlegal/__init__.py src/uzlegal/__init__.py

# `[rag]` — LanceDB va sentence-transformers mijozi. `[mac]` (MLX) bu yerda
# **kerak emas**: serverda inference vLLM da bajariladi.
RUN pip install --upgrade pip && pip install ".[rag]"

# --------------------------------------------------------------------------- #
# Ilova
# --------------------------------------------------------------------------- #

COPY src/ src/
COPY configs/ configs/
COPY prompts/ prompts/
COPY schemas/ schemas/

RUN pip install --no-deps -e .

# Ildiz bo'lmagan foydalanuvchi — konteyner buzilsa zarar cheklangan bo'ladi.
RUN useradd --create-home --uid 10001 uzlegal \
    && chown -R uzlegal:uzlegal /app
USER uzlegal

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8080/v1/health || exit 1

# Standart buyruq — API. Bot va MCP `command:` bilan almashtiradi.
CMD ["uzlegal", "serve", "--host", "0.0.0.0", "--port", "8080"]
