# syntax=docker/dockerfile:1

# AI Lawyer — web, bot va CLI uchun yagona tasvir.
#
# NEGA ALPINE EMAS. Loyihada `node:sqlite`, `unpdf` va `mammoth` bor — bular
# tizim kutubxonalariga tayanadi va musl (Alpine) da kutilmagan xatolar beradi.
# Debian (bookworm) katta, lekin ishonchli.
#
# NEGA `output: standalone` EMAS. Standalone chiqishda faqat web ishlaydi;
# bizga esa o'sha tasvir ichida `npm run bot:poll`, `npm run ingest` va
# `npm run report` ham kerak — ular `tsx` va `src/` ga tayanadi. Shuning uchun
# to'liq `node_modules` qoldiriladi.

FROM node:24-bookworm-slim AS deps
WORKDIR /app

# Avval faqat manifestlar — kod o'zgarganda `npm ci` qayta ishlamaydi.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund


FROM node:24-bookworm-slim AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# `curl` — konteyner sog'lig'ini tekshirish uchun (compose healthcheck).
RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build vaqtida maxfiy qiymatlar kerak emas: `config.ts` ularni ishlash
# paytida o'qiydi, shuning uchun `.env.local` tasvirga umuman tushmaydi
# (`.dockerignore` ga qarang).
RUN npm run build

# Qonun bazasi va yuklangan matnlar shu yerda — compose ularni hajm sifatida
# ulaydi, aks holda konteyner o'chganda baza yo'qoladi.
RUN mkdir -p /app/data/corpus

EXPOSE 3000

CMD ["npm", "run", "start"]
