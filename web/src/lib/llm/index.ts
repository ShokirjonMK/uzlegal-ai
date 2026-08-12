/**
 * Provayderni tanlaydigan qatlam.
 *
 * Servislar (`ask`, `analyze`, `review`, `generate`) faqat shu modulni
 * biladi — qaysi provayder ishlayotgani ular uchun ahamiyatsiz.
 */

import { config } from "../config";
import { anthropicProvider, humanError as anthropicHumanError } from "./anthropic";
import { ollamaProvider, OllamaError } from "./ollama";
import { uzlegalProvider, UzlegalLlmError } from "./uzlegal";
import type {
  CallOptions,
  CompleteResult,
  JsonResult,
  LlmProvider,
  Provider,
  StreamOptions,
} from "./types";

export type {
  CallOptions,
  CompleteResult,
  JsonResult,
  LlmProvider,
  Provider,
  StreamOptions,
};

export { MissingApiKeyError, RefusalError } from "./anthropic";
export { OllamaError, pingOllama } from "./ollama";
export { UzlegalLlmError } from "./uzlegal";

/** Joriy provayder. */
export function provider(): LlmProvider {
  if (config.provider === "ollama") return ollamaProvider;
  if (config.provider === "anthropic") return anthropicProvider;
  return uzlegalProvider;
}

/** Faol provayder nomi va modeli — hisobot va panel uchun. */
export function activeModel(): { provider: Provider; model: string } {
  const p = provider();
  return { provider: p.name, model: p.modelName() };
}

/**
 * Yozuvga tushadigan model tavsifi.
 * `effort` faqat Anthropic da maʼnoga ega — lokal modelda yozilmaydi,
 * aks holda yozishmalar tahlilida yoʻq sozlama koʻrinib turardi.
 */
export function callMeta(): {
  provider: Provider;
  model: string;
  effort?: string;
} {
  const active = activeModel();
  return {
    ...active,
    effort: active.provider === "anthropic" ? config.effort : undefined,
  };
}

export function complete(opts: CallOptions): Promise<CompleteResult> {
  return provider().complete(opts);
}

export function completeJSON<T>(
  opts: CallOptions & { schema: Record<string, unknown> },
): Promise<JsonResult<T>> {
  return provider().completeJSON<T>(opts);
}

export function streamText(
  opts: StreamOptions,
): AsyncGenerator<string, void, unknown> {
  return provider().streamText(opts);
}

/** Foydalanuvchiga koʻrsatiladigan xato matni (oʻzbekcha). */
export function humanError(err: unknown): string {
  // Ollama xatolari allaqachon o'zbekcha va aniq — o'zgartirilmaydi.
  if (err instanceof OllamaError) return err.message;
  return anthropicHumanError(err);
}
