/**
 * Qo'shimcha tekshiruvlar: hujjatni majburiy talablar bo'yicha nuqta-ma-nuqta
 * tekshirib, har biri uchun alohida natija beradi.
 *
 * Tahlildan (analyze) farqi: tahlil erkin shaklda xavflarni topadi,
 * tekshiruv esa qat'iy ro'yxat bo'yicha "o'tdi / o'tmadi" javobini beradi.
 */

import { completeJSON } from "../llm";
import { config } from "../config";
import { reviewSystemStable, sourcesBlock } from "../prompts";
import { retrieve } from "../rag/retrieve";
import { resolveLang } from "../uz/detect";
import { polishUzbek } from "../uz/orthography";
import type { CheckStatus, ComplianceCheck, Lang, ReviewResult, Script } from "../types";

const MAX_DOC_CHARS = 120_000;

/** Standart tekshiruvlar ro'yxati. */
export const DEFAULT_CHECKS: Array<{ id: string; title: string }> = [
  { id: "rekvizitlar", title: "Tomonlar rekvizitlari toʻliq" },
  { id: "predmet", title: "Shartnoma predmeti aniq belgilangan" },
  { id: "narx", title: "Narx va toʻlov tartibi koʻrsatilgan" },
  { id: "muddat", title: "Amal qilish muddati belgilangan" },
  { id: "javobgarlik", title: "Tomonlar javobgarligi mutanosib" },
  { id: "bekor-qilish", title: "Bekor qilish tartibi belgilangan" },
  { id: "fors-major", title: "Fors-major sharti mavjud" },
  { id: "nizolar", title: "Nizolarni hal qilish tartibi aniq" },
  { id: "imperativ", title: "Imperativ normalarga zid shartlar yoʻq" },
  { id: "shakl", title: "Hujjat shakli talabga muvofiq" },
];

const REVIEW_SCHEMA: Record<string, unknown> = {
  type: "object",
  additionalProperties: false,
  required: ["checks", "score", "summary"],
  properties: {
    checks: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["id", "title", "status", "detail", "legalBasis"],
        properties: {
          id: { type: "string" },
          title: { type: "string" },
          status: {
            type: "string",
            enum: ["oʻtdi", "ogohlantirish", "oʻtmadi", "aniqlanmadi"],
          },
          detail: {
            type: "string",
            description: "Nima uchun shu holat qoʻyildi — aniq, 1-3 gap.",
          },
          legalBasis: {
            type: "string",
            description: "Tegishli modda. Manba boʻlmasa — boʻsh satr.",
          },
        },
      },
    },
    score: {
      type: "integer",
      description: "Umumiy holat bahosi, 0 dan 100 gacha.",
    },
    summary: { type: "string", description: "Qisqa umumiy xulosa." },
  },
};

export interface ReviewRequest {
  text: string;
  filename?: string;
  /** Qo'shimcha tekshiruvlar (standartga qo'shiladi). */
  extraChecks?: Array<{ id: string; title: string }>;
  lang?: Lang | "auto";
  script?: Script | "auto";
}

export async function review(req: ReviewRequest): Promise<ReviewResult> {
  const text = req.text.trim();
  if (text.length < 50) {
    throw new Error("Hujjat matni juda qisqa yoki fayldan matn ajratib boʻlmadi.");
  }

  const body = text.slice(0, MAX_DOC_CHARS);
  const { lang, script } = resolveLang(
    body.slice(0, 2000),
    req.lang ?? config.lang,
    req.script ?? config.script,
  );

  const checks = [...DEFAULT_CHECKS, ...(req.extraChecks ?? [])];
  const checklist = checks.map((c) => `- ${c.id}: ${c.title}`).join("\n");

  const found = await retrieve(body.slice(0, 3000), { topK: 10 });

  const { data, usage } = await completeJSON<{
    checks: ComplianceCheck[];
    score: number;
    summary: string;
  }>({
    systemStable: reviewSystemStable(lang, script),
    systemDynamic: sourcesBlock(found, lang),
    messages: [
      {
        role: "user",
        content:
          `Quyidagi hujjatni shu roʻyxat boʻyicha tekshiring. ` +
          `Har bir bandga aynan shu "id" bilan javob qaytaring:\n${checklist}\n\n` +
          (req.filename ? `Fayl nomi: ${req.filename}\n\n` : "") +
          `<hujjat>\n${body}\n</hujjat>`,
      },
    ],
    schema: REVIEW_SCHEMA,
    maxTokens: 12000,
  });

  const normalized: ComplianceCheck[] = data.checks.map((c) => ({
    id: c.id,
    title: lang === "uz" ? polishUzbek(c.title) : c.title,
    status: normalizeStatus(c.status),
    detail: lang === "uz" ? polishUzbek(c.detail) : c.detail,
    legalBasis: c.legalBasis ? polishUzbek(c.legalBasis) : undefined,
  }));

  return {
    checks: normalized,
    score: clamp(data.score, 0, 100),
    summary: lang === "uz" ? polishUzbek(data.summary) : data.summary,
    lang,
    script,
    usage,
  };
}

function normalizeStatus(s: string): CheckStatus {
  const valid: CheckStatus[] = ["oʻtdi", "ogohlantirish", "oʻtmadi", "aniqlanmadi"];
  if ((valid as string[]).includes(s)) return s as CheckStatus;
  // Apostrof varianti boshqacha kelgan bo'lishi mumkin.
  const folded = s.replace(/[''ʻʼ`]/g, "");
  if (folded === "otdi") return "oʻtdi";
  if (folded === "otmadi") return "oʻtmadi";
  if (folded === "ogohlantirish") return "ogohlantirish";
  return "aniqlanmadi";
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, Math.round(n)));
}
