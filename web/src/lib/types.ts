/** Loyiha bo'ylab ishlatiladigan umumiy tiplar. */

import type { Lang, Script } from "./uz/detect";

export type { Lang, Script };

// ── Suhbat ─────────────────────────────────────────────────────────────────

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

// ── Qonun bazasi (RAG) ─────────────────────────────────────────────────────

/** Bazadagi bitta qonun bo'lagi (odatda — bitta modda). */
export interface CorpusChunk {
  id: string;
  /** Hujjat nomi: "Mehnat kodeksi". */
  document: string;
  /** Modda raqami: "173". Aniqlanmasa — bo'sh. */
  article?: string;
  /** Modda sarlavhasi. */
  heading?: string;
  /** Matn. */
  text: string;
  /** Manba havolasi (lex.uz va h.k.). */
  url?: string;
  /** Tahrir sanasi (ISO). */
  version?: string;
  lang: Lang;
  script: Script;
}

/** Qidiruv natijasi. */
export interface Retrieved extends CorpusChunk {
  score: number;
}

/** Javobda ko'rsatiladigan havola. */
export interface Citation {
  document: string;
  article?: string;
  heading?: string;
  url?: string;
  snippet: string;
}

// ── Savol-javob ────────────────────────────────────────────────────────────

export interface AskRequest {
  question: string;
  history?: ChatMessage[];
  lang?: Lang | "auto";
  script?: Script | "auto";
  /** Qonun bazasidan nechta bo'lak olinsin. Standart: 8. */
  topK?: number;
  /** Qonun bazasini ishlatmaslik (faqat umumiy bilim). */
  noRag?: boolean;
}

export interface AskResult {
  answer: string;
  citations: Citation[];
  lang: Lang;
  script: Script;
  usage?: Usage;
}

export interface Usage {
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens?: number;
  cacheWriteTokens?: number;
}

// ── Hujjat tahlili ─────────────────────────────────────────────────────────

export type RiskLevel = "yuqori" | "oʻrta" | "past";

export interface Risk {
  /** Xavf sarlavhasi. */
  title: string;
  level: RiskLevel;
  /** Hujjatning qaysi qismi (band/modda yoki iqtibos). */
  location: string;
  /** Nima uchun xavfli. */
  explanation: string;
  /** Nima qilish kerak. */
  recommendation: string;
  /** Tegishli qonun moddasi, bo'lsa. */
  legalBasis?: string;
}

export interface AnalyzeResult {
  /** Hujjat turi: "mehnat shartnomasi", "ijara shartnomasi" va h.k. */
  documentType: string;
  summary: string;
  parties: Array<{ role: string; name: string }>;
  keyTerms: Array<{ label: string; value: string }>;
  risks: Risk[];
  /** Hujjatda yetishmayotgan muhim shartlar. */
  missingClauses: string[];
  /** Umumiy xulosa va tavsiyalar. */
  conclusion: string;
  lang: Lang;
  script: Script;
  usage?: Usage;
}

// ── Hujjat generatsiyasi ───────────────────────────────────────────────────

export type DocTemplateId =
  | "mehnat-shartnomasi"
  | "ijara-shartnomasi"
  | "oldi-sotdi-shartnomasi"
  | "xizmat-korsatish-shartnomasi"
  | "pudrat-shartnomasi"
  | "davo-arizasi"
  | "ishonchnoma"
  | "tilxat"
  | "ariza"
  | "pretenziya"
  | "erkin";

export interface GenerateRequest {
  template: DocTemplateId;
  /** Foydalanuvchi bergan ma'lumotlar (erkin matn yoki maydonlar). */
  details: string;
  /** Qo'shimcha maydonlar (UI formasidan). */
  fields?: Record<string, string>;
  lang?: Lang | "auto";
  script?: Script | "auto";
}

export interface GenerateResult {
  title: string;
  /** Markdown ko'rinishidagi hujjat. */
  markdown: string;
  /** To'ldirilishi kerak bo'lgan joylar. */
  placeholders: string[];
  /** Foydalanuvchiga eslatmalar. */
  notes: string[];
  lang: Lang;
  script: Script;
  usage?: Usage;
}

// ── Qo'shimcha tekshiruvlar ────────────────────────────────────────────────

export type CheckStatus = "oʻtdi" | "ogohlantirish" | "oʻtmadi" | "aniqlanmadi";

export interface ComplianceCheck {
  id: string;
  /** Tekshiruv nomi. */
  title: string;
  status: CheckStatus;
  /** Natija izohi. */
  detail: string;
  legalBasis?: string;
}

export interface ReviewResult {
  checks: ComplianceCheck[];
  score: number; // 0..100
  summary: string;
  lang: Lang;
  script: Script;
  usage?: Usage;
}

// ── Streaming hodisalari ───────────────────────────────────────────────────

export type StreamEvent =
  | { type: "status"; message: string }
  | { type: "citations"; citations: Citation[] }
  | { type: "delta"; text: string }
  | { type: "done"; usage?: Usage }
  | { type: "error"; message: string };
