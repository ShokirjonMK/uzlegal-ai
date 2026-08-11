/**
 * Oqimni «tinglash» — SSE hodisalarini o'zgartirmasdan o'tkazadi va
 * oxirida to'liq yozuvni bazaga tushiradi.
 *
 * Nega shu yerda, servis ichida emas: servis kim so'raganini bilmaydi.
 * Foydalanuvchi kimligi (sessiya, Telegram ID) faqat marshrut darajasida
 * ma'lum, shuning uchun yozuv ham shu darajada olinadi.
 */

import { recordAiCall, type AiCallInput } from "./log";
import { callMeta } from "../llm";
import type { StreamEvent } from "../types";

export type TapMeta = Omit<
  AiCallInput,
  | "output"
  | "model"
  | "provider"
  | "effort"
  | "inputTokens"
  | "outputTokens"
  | "durationMs"
>;

export async function* tapStream(
  stream: AsyncGenerator<StreamEvent, void, unknown>,
  meta: TapMeta,
): AsyncGenerator<StreamEvent, void, unknown> {
  const started = Date.now();
  let output = "";
  let citations: unknown[] | undefined;
  let inputTokens: number | undefined;
  let outputTokens: number | undefined;
  let error: string | undefined = meta.error;

  try {
    for await (const event of stream) {
      switch (event.type) {
        case "delta":
          output += event.text;
          break;
        case "citations":
          citations = event.citations;
          break;
        case "done":
          inputTokens = event.usage?.inputTokens;
          outputTokens = event.usage?.outputTokens;
          break;
        case "error":
          error = event.message;
          break;
      }
      yield event;
    }
  } catch (err) {
    error = err instanceof Error ? err.message : "oqim uzildi";
    throw err;
  } finally {
    // Foydalanuvchi oqimni yarmida uzsa ham, o'sha paytgacha kelgan matn yoziladi.
    recordAiCall({
      ...meta,
      // Faol provayderning modeli. `config.model` emas: lokal provayderda
      // u Claude nomini yozib qo'yardi va yozuvlar tahlilga yaroqsiz bo'lardi.
      ...callMeta(),
      output,
      citations: citations ?? meta.citations,
      inputTokens,
      outputTokens,
      durationMs: Date.now() - started,
      error,
    });
  }
}
