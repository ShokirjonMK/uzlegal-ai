/**
 * Provayderlar uchun umumiy shartnoma.
 *
 * Uchta provayder bor:
 *
 *   uzlegal    yadro orqali (`POST /v1/generate`) — STANDART
 *   ollama     to'g'ridan-to'g'ri lokal Ollama
 *   anthropic  bulut (ixtiyoriy, kalit talab qiladi)
 *
 * Servislar (`ask`, `analyze`, `review`, `generate`) qaysi biri
 * ishlayotganini bilmasligi kerak — ular faqat shu tiplarga tayanadi.
 *
 * NEGA `uzlegal` STANDART. `ollama` ishlaydi, lekin u yadrodan
 * MUSTAQIL: `uzlegal models use` bilan modelni almashtirsangiz web
 * eski modelda qolaveradi va bir savolga ikki xil javob chiqadi.
 * Yadro orqali borilsa model tanlovi bitta joyda bo'ladi.
 */

import type { Effort } from "../config";
import type { Usage } from "../types";
import type { MessageParam } from "@anthropic-ai/sdk/resources/messages";

export type { Usage };

/** Provayder nomi. */
export type Provider = "uzlegal" | "anthropic" | "ollama";

export interface CallOptions {
  /**
   * Tizim promptining barqaror qismi. Anthropic da keshlanadi;
   * Ollama da shunchaki tizim xabarining boshiga qo'yiladi.
   */
  systemStable: string;
  /** Tizim promptining o'zgaruvchan qismi (topilgan qonun bo'laklari). */
  systemDynamic?: string;
  messages: MessageParam[];
  maxTokens?: number;
  /** Faqat Anthropic da amal qiladi. Ollama uni e'tiborsiz qoldiradi. */
  effort?: Effort;
  /** Faqat Anthropic da amal qiladi. */
  disableThinking?: boolean;
}

export interface CompleteResult {
  text: string;
  usage: Usage;
  truncated: boolean;
}

export interface JsonResult<T> {
  data: T;
  usage: Usage;
}

export interface StreamOptions extends CallOptions {
  onDone?: (usage: Usage) => void;
}

/** Har bir provayder shu uchta amalni bajaradi. */
export interface LlmProvider {
  readonly name: Provider;
  /** Ishlatilayotgan model nomi — hisobot va panel uchun. */
  modelName(): string;
  complete(opts: CallOptions): Promise<CompleteResult>;
  completeJSON<T>(
    opts: CallOptions & { schema: Record<string, unknown> },
  ): Promise<JsonResult<T>>;
  streamText(opts: StreamOptions): AsyncGenerator<string, void, unknown>;
}

/** Tizim promptining ikki qismini bitta matnga qo'shadi (Ollama uchun). */
export function joinSystem(opts: CallOptions): string {
  const dynamic = opts.systemDynamic?.trim();
  return dynamic ? `${opts.systemStable}\n\n${dynamic}` : opts.systemStable;
}
