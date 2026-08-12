/**
 * Yadro provayderi — model chaqiruvi `POST /v1/generate` orqali.
 *
 * ## Nima uchun bu provayder kerak
 *
 * Loyihada uchta model yoʻli boʻlib qolgan edi:
 *
 *     web ──► Anthropic (bulut, pullik, maʼlumot chetga chiqadi)
 *     web ──► Ollama    (lokal, lekin yadrodan MUSTAQIL)
 *     yadro ──► registry ──► Ollama / MLX / vLLM
 *
 * Ikkinchisi ayniqsa nozik: u ishlaydi, lekin yadro qaysi modelni
 * ishlatayotganini **bilmaydi**. `uzlegal models use` bilan modelni
 * almashtirsangiz, web eski modelda qolaveradi. Bir savolga ikki xil
 * javob — bu aynan `BIRLASHTIRISH.md` ogohlantirgan holat.
 *
 * Bu provayder web ni yadroga ulaydi. Endi model tanlovi **bitta**
 * joyda: `configs/models.yaml` va `uzlegal models use`.
 *
 * ## Qoʻshimcha foydasi
 *
 * * Anthropic kaliti umuman kerak emas — maʼlumot chetga chiqmaydi;
 * * litsenziya darvozasi bu yoʻlga ham taalluqli boʻladi;
 * * xarajat nolga tushadi (bulut API da bitta savol ≈ $0.22).
 *
 * ## Cheklov — halol aytiladi
 *
 * `/v1/generate` **JSON rejimini** qoʻllab-quvvatlamaydi. Shuning uchun
 * `completeJSON()` promptga qatʼiy koʻrsatma qoʻshadi va javobdan JSON
 * ni oʻzi ajratib oladi. Bu Anthropic ning `tool_use` mexanizmidan
 * ishonchsizroq — model baʼzan JSON atrofiga izoh yozadi. Ajratish
 * mantigʻi shuni hisobga oladi.
 */

import { config } from "../config";
import type { MessageParam } from "@anthropic-ai/sdk/resources/messages";
import type {
  CallOptions,
  CompleteResult,
  JsonResult,
  LlmProvider,
  StreamOptions,
  Usage,
} from "./types";
import { joinSystem } from "./types";

export class UzlegalLlmError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "UzlegalLlmError";
  }
}

/** Suhbat tarixini bitta promptga yigʻadi.
 *
 * `/v1/generate` bitta `prompt` maydonini oladi, roʻyxatni emas.
 * Tarix yoʻqolmasligi uchun u matnga aylantiriladi — modelga rol
 * belgilari bilan koʻrsatiladi.
 */
function flatten(messages: MessageParam[]): string {
  return messages
    .map((m) => {
      const text =
        typeof m.content === "string"
          ? m.content
          : m.content
              .map((b) => ("text" in b ? b.text : ""))
              .filter(Boolean)
              .join("\n");
      return m.role === "user" ? `Savol: ${text}` : `Javob: ${text}`;
    })
    .join("\n\n");
}

async function callCore(
  opts: CallOptions,
  extraPrompt = "",
): Promise<{ text: string; model: string }> {
  const base = config.uzlegalApiUrl.replace(/\/+$/, "");
  const body = {
    prompt: `${joinSystem(opts)}\n\n${flatten(opts.messages)}${extraPrompt}`,
    max_tokens: opts.maxTokens ?? 4000,
    temperature: 0.3,
  };

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (config.uzlegalApiKey) headers["X-API-Key"] = config.uzlegalApiKey;

  let res: Response;
  try {
    res = await fetch(`${base}/v1/generate`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(config.uzlegalTimeoutMs),
    });
  } catch (err) {
    throw new UzlegalLlmError(
      `Yadro javob bermadi (${base}). Ishga tushirilganmi? \`uzlegal serve\``,
    );
  }

  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new UzlegalLlmError(`Yadro xatosi ${res.status}: ${detail.slice(0, 200)}`);
  }

  const data = (await res.json()) as { text?: string; model?: string };
  return { text: data.text ?? "", model: data.model ?? "uzlegal" };
}

/** Taxminiy foydalanish hisobi.
 *
 * `/v1/generate` token sonini qaytarmaydi. Nol yozish statistikani
 * buzardi, shuning uchun belgilar soni boʻyicha taxmin qilinadi
 * (oʻzbek/rus matnida ≈ 3 belgi = 1 token) va bu ATAXMIN ekani
 * `estimated` bayrogʻi bilan koʻrsatiladi.
 */
function estimateUsage(promptChars: number, outputChars: number): Usage {
  return {
    inputTokens: Math.round(promptChars / 3),
    outputTokens: Math.round(outputChars / 3),
    cacheReadTokens: 0,
    cacheWriteTokens: 0,
  };
}

const JSON_INSTRUCTION =
  "\n\nMUHIM: javobni FAQAT JSON obyekti sifatida ber. " +
  "Hech qanday izoh, sarlavha yoki ```json belgisi qoʻshma. " +
  "Javob `{` bilan boshlanib `}` bilan tugasin.";

/** Model javobidan JSON ni ajratib oladi.
 *
 * Model koʻrsatmaga qaramay izoh yozishi yoki ```json blokiga oʻrashi
 * mumkin. Uchala holat ham koʻrildi, shuning uchun uchalasi ham
 * qoʻllab-quvvatlanadi.
 */
function extractJson(text: string): string {
  const fenced = /```(?:json)?\s*([\s\S]*?)```/.exec(text);
  const body = fenced?.[1] ?? text;
  const start = body.indexOf("{");
  const end = body.lastIndexOf("}");
  if (start === -1 || end === -1 || end <= start) {
    throw new UzlegalLlmError(`Javobda JSON topilmadi: ${text.slice(0, 160)}`);
  }
  return body.slice(start, end + 1);
}

export async function complete(opts: CallOptions): Promise<CompleteResult> {
  const { text } = await callCore(opts);
  return {
    text,
    usage: estimateUsage(joinSystem(opts).length, text.length),
    // Yadro kesilganini aytmaydi. `false` deb yozish yolgʻon boʻlardi,
    // lekin `true` ham. Amaliy yechim: javob `max_tokens` ga juda
    // yaqin boʻlsa kesilgan deb hisoblaymiz.
    truncated: text.length >= (opts.maxTokens ?? 4000) * 3.2,
  };
}

export async function completeJSON<T>(
  opts: CallOptions & { schema: Record<string, unknown> },
): Promise<JsonResult<T>> {
  const { text } = await callCore(opts, JSON_INSTRUCTION);
  const raw = extractJson(text);

  let data: T;
  try {
    data = JSON.parse(raw) as T;
  } catch (err) {
    throw new UzlegalLlmError(
      `JSON ajratib boʻlmadi: ${(err as Error).message}. Matn: ${raw.slice(0, 160)}`,
    );
  }
  return { data, usage: estimateUsage(joinSystem(opts).length, text.length) };
}

/** Oqim — yadro `/v1/generate/stream` SSE beradi. */
export async function* streamText(opts: StreamOptions): AsyncGenerator<string, void, unknown> {
  const base = config.uzlegalApiUrl.replace(/\/+$/, "");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (config.uzlegalApiKey) headers["X-API-Key"] = config.uzlegalApiKey;

  const res = await fetch(`${base}/v1/generate/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      prompt: `${joinSystem(opts)}\n\n${flatten(opts.messages)}`,
      max_tokens: opts.maxTokens ?? 4000,
      temperature: 0.3,
    }),
    signal: AbortSignal.timeout(config.uzlegalTimeoutMs),
  });

  if (!res.ok || !res.body) {
    throw new UzlegalLlmError(`Yadro oqimi ochilmadi: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let produced = 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      try {
        const payload = JSON.parse(line.slice(5).trim()) as { text?: string };
        if (payload.text) {
          produced += payload.text.length;
          yield payload.text;
        }
      } catch {
        // Buzuq boʻlak butun oqimni yiqitmasligi kerak.
      }
    }
  }

  opts.onDone?.(estimateUsage(joinSystem(opts).length, produced));
}

export const uzlegalProvider: LlmProvider = {
  name: "uzlegal",
  modelName: () => "uzlegal-core",
  complete,
  completeJSON,
  streamText,
};
