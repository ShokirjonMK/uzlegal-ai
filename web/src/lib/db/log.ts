/**
 * Modelga qilingan murojaatlarni bazaga yozish.
 *
 * Ikki qoida:
 *  1. Yozuv hech qachon asosiy ishni to'xtatmaydi — Mongo o'chiq bo'lsa ham
 *     foydalanuvchi javobini oladi. Shuning uchun xatolik yutiladi.
 *  2. Matn qisqartirilmaydi. Savol ham, javob ham, tizim prompti ham to'liq
 *     saqlanadi (docs/TASKS.md, #65 — foydalanuvchi qarori).
 */

import { ObjectId } from "mongodb";
import { aiCalls, events, type AiCallDoc, type EventDoc } from "./collections";
import { isMongoConfigured } from "./mongo";
import type { EventKind, Surface } from "../analytics";

export interface AiCallInput {
  kind: EventKind;
  surface: Surface;
  userId?: ObjectId | string | null;
  telegramId?: number;
  anonId?: string;
  provider?: string;
  model: string;
  effort?: string;
  systemPrompt?: string;
  input: string;
  output: string;
  citations?: unknown[];
  inputTokens?: number;
  outputTokens?: number;
  durationMs?: number;
  error?: string;
  label?: string;
}

function toObjectId(v: ObjectId | string | null | undefined): ObjectId | null {
  if (!v) return null;
  if (typeof v !== "string") return v;
  return ObjectId.isValid(v) ? new ObjectId(v) : null;
}

/**
 * Murojaatni yozadi. `await` qilish SHART EMAS — chaqiruvchi kutmasa ham
 * yozuv fonda tugaydi va xatolik yutiladi.
 */
export async function logAiCall(input: AiCallInput): Promise<void> {
  if (!isMongoConfigured()) return;
  try {
    const doc: Omit<AiCallDoc, "_id"> = {
      kind: input.kind,
      surface: input.surface,
      userId: toObjectId(input.userId),
      telegramId: input.telegramId,
      anonId: input.anonId,
      provider: input.provider,
      model: input.model,
      effort: input.effort,
      systemPrompt: input.systemPrompt,
      input: input.input,
      output: input.output,
      citations: input.citations,
      inputTokens: input.inputTokens,
      outputTokens: input.outputTokens,
      durationMs: input.durationMs,
      error: input.error,
      label: input.label,
      createdAt: new Date(),
    };
    const col = await aiCalls();
    await col.insertOne(doc as AiCallDoc);
  } catch (err) {
    console.error("[mongo] murojaatni yozib boʻlmadi:", err);
  }
}

export interface EventInput {
  kind: EventKind;
  surface: Surface;
  userId?: ObjectId | string | null;
  telegramId?: number;
  durationMs?: number;
  error?: string;
  label?: string;
}

/** Yengil hodisa yozuvi (matnsiz) — sanoq va grafiklar uchun. */
export async function logEvent(input: EventInput): Promise<void> {
  if (!isMongoConfigured()) return;
  try {
    const col = await events();
    await col.insertOne({
      kind: input.kind,
      surface: input.surface,
      userId: toObjectId(input.userId),
      telegramId: input.telegramId,
      durationMs: input.durationMs,
      error: input.error,
      label: input.label,
      createdAt: new Date(),
    } as EventDoc);
  } catch (err) {
    console.error("[mongo] hodisani yozib boʻlmadi:", err);
  }
}

/** `await` qilinmaydigan qisqa shakl — javob yo'lini sekinlashtirmaydi. */
export function recordAiCall(input: AiCallInput): void {
  void logAiCall(input);
}
