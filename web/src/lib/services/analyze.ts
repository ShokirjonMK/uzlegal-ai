/**
 * Hujjat tahlili: xavflarni, yetishmayotgan shartlarni va muhim bandlarni topadi.
 * Natija qat'iy JSON sxemasi bo'yicha qaytadi — UI har doim bir xil shaklni oladi.
 */

import { completeJSON } from "../llm";
import { config } from "../config";
import { analyzeSystemStable, sourcesBlock } from "../prompts";
import { retrieve } from "../rag/retrieve";
import { resolveLang } from "../uz/detect";
import { polishUzbek } from "../uz/orthography";
import type { AnalyzeResult, Lang, Script } from "../types";

/** Modelga yuboriladigan hujjat matnining maksimal uzunligi. */
const MAX_DOC_CHARS = 120_000;

const ANALYZE_SCHEMA: Record<string, unknown> = {
  type: "object",
  additionalProperties: false,
  required: [
    "documentType",
    "summary",
    "parties",
    "keyTerms",
    "risks",
    "missingClauses",
    "conclusion",
  ],
  properties: {
    documentType: {
      type: "string",
      description: "Hujjat turi, masalan: mehnat shartnomasi, ijara shartnomasi.",
    },
    summary: {
      type: "string",
      description: "Hujjat nima haqidaligi — 2-4 gap.",
    },
    parties: {
      type: "array",
      description: "Hujjatdagi tomonlar.",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["role", "name"],
        properties: {
          role: { type: "string", description: "Masalan: Ish beruvchi, Ijarachi." },
          name: {
            type: "string",
            description: "Nomi. Hujjatda koʻrsatilmagan boʻlsa: 'koʻrsatilmagan'.",
          },
        },
      },
    },
    keyTerms: {
      type: "array",
      description: "Muhim shartlar: summa, muddat, hisob-kitob tartibi va h.k.",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["label", "value"],
        properties: {
          label: { type: "string" },
          value: { type: "string" },
        },
      },
    },
    risks: {
      type: "array",
      description: "Aniqlangan xavflar, eng muhimi birinchi.",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["title", "level", "location", "explanation", "recommendation", "legalBasis"],
        properties: {
          title: { type: "string", description: "Xavf qisqa nomi." },
          level: { type: "string", enum: ["yuqori", "oʻrta", "past"] },
          location: {
            type: "string",
            description: "Hujjatning qaysi bandi yoki qisqa iqtibos.",
          },
          explanation: { type: "string", description: "Nima uchun xavfli." },
          recommendation: { type: "string", description: "Nima qilish kerak." },
          legalBasis: {
            type: "string",
            description:
              "Manbalar blokidagi tegishli modda. Aniq manba boʻlmasa — boʻsh satr.",
          },
        },
      },
    },
    missingClauses: {
      type: "array",
      description: "Hujjatda yoʻq, lekin boʻlishi kerak boʻlgan shartlar.",
      items: { type: "string" },
    },
    conclusion: {
      type: "string",
      description: "Umumiy xulosa va asosiy tavsiyalar.",
    },
  },
};

export interface AnalyzeRequest {
  /** Hujjat matni. */
  text: string;
  /** Fayl nomi (kontekst uchun). */
  filename?: string;
  /** Kim nuqtai nazaridan tahlil qilinsin: "ishchi", "ijarachi" va h.k. */
  perspective?: string;
  lang?: Lang | "auto";
  script?: Script | "auto";
}

export async function analyze(req: AnalyzeRequest): Promise<AnalyzeResult> {
  const text = req.text.trim();
  if (text.length < 50) {
    throw new Error("Hujjat matni juda qisqa yoki fayldan matn ajratib boʻlmadi.");
  }

  const truncated = text.length > MAX_DOC_CHARS;
  const body = truncated ? text.slice(0, MAX_DOC_CHARS) : text;

  const { lang, script } = resolveLang(
    body.slice(0, 2000),
    req.lang ?? config.lang,
    req.script ?? config.script,
  );

  // Hujjat mavzusiga oid qonun normalarini topamiz — xavflarni qonunga
  // bog'lash uchun.
  const found = await retrieve(body.slice(0, 3000), { topK: 10 });

  const perspective = req.perspective?.trim()
    ? `\n\nTahlilni quyidagi tomon nuqtai nazaridan qiling: ${req.perspective.trim()}.`
    : "";

  const filenameNote = req.filename ? `\nFayl nomi: ${req.filename}` : "";
  const truncNote = truncated
    ? "\n\nDIQQAT: hujjat uzun boʻlgani uchun faqat boshlangʻich qismi berildi."
    : "";

  const { data, usage } = await completeJSON<Omit<AnalyzeResult, "lang" | "script" | "usage">>({
    systemStable: analyzeSystemStable(lang, script),
    systemDynamic: sourcesBlock(found, lang),
    messages: [
      {
        role: "user",
        content: `Quyidagi hujjatni tahlil qiling.${filenameNote}${perspective}${truncNote}\n\n<hujjat>\n${body}\n</hujjat>`,
      },
    ],
    schema: ANALYZE_SCHEMA,
    maxTokens: 16000,
  });

  const result: AnalyzeResult = { ...data, lang, script, usage };
  return lang === "uz" && script === "latn" ? polishAnalyze(result) : result;
}

/** Natijadagi barcha matn maydonlarini o'zbek imlosi bo'yicha tozalaydi. */
function polishAnalyze(r: AnalyzeResult): AnalyzeResult {
  return {
    ...r,
    documentType: polishUzbek(r.documentType),
    summary: polishUzbek(r.summary),
    conclusion: polishUzbek(r.conclusion),
    parties: r.parties.map((p) => ({
      role: polishUzbek(p.role),
      name: polishUzbek(p.name),
    })),
    keyTerms: r.keyTerms.map((k) => ({
      label: polishUzbek(k.label),
      value: polishUzbek(k.value),
    })),
    missingClauses: r.missingClauses.map(polishUzbek),
    risks: r.risks.map((risk) => ({
      ...risk,
      title: polishUzbek(risk.title),
      location: polishUzbek(risk.location),
      explanation: polishUzbek(risk.explanation),
      recommendation: polishUzbek(risk.recommendation),
      legalBasis: risk.legalBasis ? polishUzbek(risk.legalBasis) : undefined,
    })),
  };
}
