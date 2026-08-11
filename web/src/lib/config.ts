/** Muhit o'zgaruvchilaridan o'qiladigan markazlashgan sozlamalar. */

import type { Lang, Script } from "./uz/detect";

function env(name: string): string | undefined {
  const v = process.env[name];
  return v && v.trim() ? v.trim() : undefined;
}

export type Effort = "low" | "medium" | "high" | "xhigh" | "max";

const EFFORTS: readonly Effort[] = ["low", "medium", "high", "xhigh", "max"];

function parseEffort(v: string | undefined, fallback: Effort): Effort {
  return EFFORTS.includes(v as Effort) ? (v as Effort) : fallback;
}

function parseLang(v: string | undefined): Lang | "auto" {
  return v === "uz" || v === "ru" || v === "en" ? v : "auto";
}

function parseScript(v: string | undefined): Script | "auto" {
  return v === "latn" || v === "cyrl" ? v : "auto";
}

export const config = {
  /** Anthropic API kaliti. Yo'q bo'lsa SDK muhitdan o'zi qidiradi. */
  get anthropicApiKey(): string | undefined {
    return env("ANTHROPIC_API_KEY");
  },

  /** Asosiy model (Anthropic provayderi uchun). */
  get model(): string {
    return env("AI_LOWYER_MODEL") ?? "claude-opus-5";
  },

  // ── uzlegal-ai yadrosi ───────────────────────────────────────────────────

  /**
   * Yadro API manzili (`POST /v1/consult`).
   *
   * Savol-javob yo'li endi Claude SDK ni to'g'ridan-to'g'ri chaqirmaydi:
   * qidiruv, agentlar va iqtibos tekshiruvi yadroda bajariladi.
   */
  get uzlegalApiUrl(): string {
    return (env("UZLEGAL_API_URL") ?? "http://localhost:8080").replace(/\/+$/, "");
  },

  /** Yadro kaliti. Yadro himoyalanmagan bo'lsa kerak emas. */
  get uzlegalApiKey(): string | undefined {
    return env("UZLEGAL_API_KEY");
  },

  /**
   * Yadro javobini kutish muddati (ms).
   *
   * `complex` rejimda beshta agent ketma-ket ishlaydi va yadro hujjatida
   * ~45 soniya deb yozilgan. Uch daqiqa — zaxirasi bilan.
   */
  get uzlegalTimeoutMs(): number {
    const n = Number(env("UZLEGAL_TIMEOUT_MS") ?? 180_000);
    return Number.isFinite(n) && n >= 5_000 ? n : 180_000;
  },

  /** Yadro rejimi: auto | simple | standard | complex. */
  get uzlegalMode(): "auto" | "simple" | "standard" | "complex" {
    const v = env("UZLEGAL_MODE");
    return v === "simple" || v === "standard" || v === "complex" || v === "auto"
      ? v
      : "auto";
  },

  // ── Provayder tanlovi ────────────────────────────────────────────────────

  /**
   * Qaysi model xizmati ishlatiladi.
   *
   * Aniq ko'rsatilmagan bo'lsa: Anthropic kaliti bor bo'lsa — `anthropic`,
   * aks holda `ollama`. Ya'ni kalitsiz muhitda tizim o'zi lokal modelga
   * o'tadi va "kalit sozlanmagan" xatosi o'rniga javob beradi.
   */
  get provider(): "anthropic" | "ollama" {
    const explicit = env("AI_LOWYER_PROVIDER");
    if (explicit === "anthropic" || explicit === "ollama") return explicit;
    return env("ANTHROPIC_API_KEY") || env("ANTHROPIC_AUTH_TOKEN")
      ? "anthropic"
      : "ollama";
  },

  get ollamaBaseUrl(): string {
    return (env("OLLAMA_BASE_URL") ?? "http://127.0.0.1:11434").replace(
      /\/+$/,
      "",
    );
  },

  get ollamaModel(): string {
    return env("OLLAMA_MODEL") ?? "qwen2.5:7b-instruct";
  },

  /**
   * Kontekst oynasi (token). Ollama standarti — 4096, bu yetmaydi: topilgan
   * qonun bo'laklari bilan so'rov undan oshib ketadi va manbalar JIMGINA
   * kesiladi. Kesilgan manba esa modelni uydirmaga majbur qiladi.
   */
  get ollamaContext(): number {
    const n = Number(env("OLLAMA_CONTEXT") ?? 16384);
    return Number.isFinite(n) && n >= 2048 ? n : 16384;
  },

  /**
   * Lokal model chiqishining QATʼIY chegarasi.
   *
   * Servislar Claude uchun 16000 token so'raydi — kichik model uchun bu
   * xavfli: sinovda 7B model javobni topa olmay, bir xil bandni 30 martadan
   * ortiq takrorlab, o'n daqiqa davomida yozishda davom etdi. Chegara shu
   * holatni kesib tashlaydi. Yuridik javob uchun 2048 token yetarli.
   */
  get ollamaMaxOutput(): number {
    const n = Number(env("OLLAMA_MAX_OUTPUT") ?? 2048);
    return Number.isFinite(n) && n >= 256 ? n : 2048;
  },

  /** Fikrlash chuqurligi. */
  get effort(): Effort {
    return parseEffort(env("AI_LOWYER_EFFORT"), "high");
  },

  /** Majburiy javob tili (`auto` — foydalanuvchi tiliga moslashadi). */
  get lang(): Lang | "auto" {
    return parseLang(env("AI_LOWYER_LANG"));
  },

  /** Majburiy yozuv (`auto` — savol yozuviga moslashadi). */
  get script(): Script | "auto" {
    return parseScript(env("AI_LOWYER_SCRIPT"));
  },

  // ── RAG ──────────────────────────────────────────────────────────────────

  get corpusDbPath(): string {
    return env("CORPUS_DB_PATH") ?? "./data/corpus.db";
  },

  get corpusDir(): string {
    return env("CORPUS_DIR") ?? "./data/corpus";
  },

  /**
   * Qidiruv natijasi shu balldan past bo'lsa — manba sifatida berilmaydi.
   *
   * NEGA MUHIM. Ilgari chegara 0.05 edi, ya'ni amalda hech narsa
   * filtrlanmasdi va bazada javobi YO'Q savolga ham oltita begona bo'lak
   * "huquqiy asos" sifatida uzatilardi. Model esa ularga tayanib javob
   * to'qib chiqarardi.
   *
   * O'LCHOV (2026-08-11, apostrof va o'zak tuzatilgandan keyin qayta
   * kalibrlandi; `.qa-qidiruv.mts`):
   *
   *     mos savollar eng yuqori ball : 0.468 · 0.587
   *     bazada javobi YO'Q savollar  : 0.347 · 0.263
   *
   * Ya'ni bo'shliq 0.347 va 0.468 orasida — chegara uning o'rtasida.
   *
   * DIQQAT: o'lchov olti bo'lakli NAMUNA korpusida va xesh embedderda
   * olingan. Haqiqiy qonun matnlari yuklangach yoki Voyage ga o'tilgach
   * bu qiymat QAYTA kalibrlanishi shart.
   */
  get ragMinScore(): number {
    const n = Number(env("RAG_MIN_SCORE") ?? 0.4);
    return Number.isFinite(n) && n >= 0 && n <= 1 ? n : 0.4;
  },

  get voyageApiKey(): string | undefined {
    return env("VOYAGE_API_KEY");
  },

  get voyageModel(): string {
    return env("VOYAGE_MODEL") ?? "voyage-3-large";
  },

  /** Embedding provayderi. Kalit bo'lsa voyage, aks holda local zaxira. */
  get embeddingProvider(): "voyage" | "local" {
    const explicit = env("EMBEDDING_PROVIDER");
    if (explicit === "voyage" || explicit === "local") return explicit;
    return env("VOYAGE_API_KEY") ? "voyage" : "local";
  },

  // ── Telegram ─────────────────────────────────────────────────────────────

  get telegramToken(): string | undefined {
    return env("TELEGRAM_BOT_TOKEN");
  },

  get telegramWebhookSecret(): string | undefined {
    return env("TELEGRAM_WEBHOOK_SECRET");
  },

  /** Super adminlar chat ID'lari — statistika va bildirishnomalar shularga boradi. */
  get adminChatIds(): number[] {
    const raw = env("ADMIN_CHAT_ID");
    if (!raw) return [];
    return raw
      .split(",")
      .map((s) => Number(s.trim()))
      .filter((n) => Number.isFinite(n) && n !== 0);
  },

  get publicBaseUrl(): string | undefined {
    return env("PUBLIC_BASE_URL")?.replace(/\/+$/, "");
  },

  // ── API himoyasi ─────────────────────────────────────────────────────────

  get apiKey(): string | undefined {
    return env("API_KEY");
  },

  // ── MongoDB ──────────────────────────────────────────────────────────────

  /**
   * Ulanish satri. Sozlanmagan bo'lsa Mongo ga tegishli barcha imkoniyat
   * (kabinet, yozishmalar tarixi, admin statistikasi) o'chadi, lekin sayt
   * ishlashda davom etadi — savol-javob va hujjat yo'llari Mongo ga bog'liq emas.
   */
  get mongoUri(): string | undefined {
    return env("MONGODB_URI");
  },

  get mongoDbName(): string {
    return env("MONGODB_DB") ?? "ai_lowyer";
  },

  get mongoEnabled(): boolean {
    return Boolean(env("MONGODB_URI"));
  },

  // ── Web admin panel ──────────────────────────────────────────────────────

  /**
   * `/admin` paneli paroli. Sozlanmagan bo'lsa panel BUTUNLAY yopiq turadi —
   * himoyasiz ochilib qolishi mumkin emas.
   */
  get adminPassword(): string | undefined {
    return env("ADMIN_PASSWORD");
  },

  /**
   * Sessiya cookie'sini imzolash siri. `.env.local` da turishi shart:
   * jarayon xotirasida yaratilsa, server qayta ishga tushganda barcha
   * sessiyalar uziladi va bir nechta nusxa bir-birining cookie'sini tanimaydi.
   */
  get adminSessionSecret(): string | undefined {
    return env("ADMIN_SESSION_SECRET");
  },

  /** Sessiya muddati, soatda (standart 12, eng ko'pi bir hafta). */
  get adminSessionHours(): number {
    const n = Number(env("ADMIN_SESSION_HOURS") ?? 12);
    return Number.isFinite(n) && n > 0 ? Math.min(n, 168) : 12;
  },

  /**
   * Telegram orqali ikkinchi bosqich tasdiqlash mumkinmi.
   * Bot tokeni yoki admin chat ID bo'lmasa — parolning o'zi yetarli bo'ladi,
   * aks holda bot ishlamay qolganda panelga umuman kirib bo'lmaydi.
   */
  get adminTwoFactor(): boolean {
    return Boolean(env("TELEGRAM_BOT_TOKEN")) && this.adminChatIds.length > 0;
  },
} as const;

/** API kaliti sozlangan bo'lsa, so'rov sarlavhasini tekshiradi. */
export function checkApiKey(request: Request): boolean {
  const expected = config.apiKey;
  if (!expected) return true; // himoya o'chirilgan
  const header = request.headers.get("authorization") ?? "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  return timingSafeEqual(token, expected);
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
