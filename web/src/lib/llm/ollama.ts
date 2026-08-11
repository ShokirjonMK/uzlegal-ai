/**
 * Lokal model bilan ishlash qatlami (Ollama).
 *
 * Yangi kutubxona olinmadi — Ollama oddiy HTTP API beradi va `fetch` yetarli.
 *
 * Anthropic dan farqlari:
 *  - prompt keshlash yo'q (`systemStable` va `systemDynamic` shunchaki
 *    birlashtiriladi);
 *  - `effort` va fikrlash rejimi yo'q — bu sozlamalar e'tiborsiz qoldiriladi,
 *    xato tashlanmaydi, chunki servislar ularni har doim uzatadi;
 *  - rad javobi (`refusal`) alohida holat sifatida qaytmaydi.
 *
 * Oqim NDJSON ko'rinishida keladi: har qatorda bitta JSON obyekt.
 */

import { config } from "../config";
import type { Usage } from "../types";
import {
  joinSystem,
  type CallOptions,
  type CompleteResult,
  type JsonResult,
  type LlmProvider,
  type StreamOptions,
} from "./types";
import type { MessageParam } from "@anthropic-ai/sdk/resources/messages";

/** Lokal model sekin bo'lishi mumkin — taymaut keng. */
const TIMEOUT_MS = 10 * 60 * 1000;

export class OllamaError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "OllamaError";
  }
}

interface OllamaMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

interface OllamaChunk {
  message?: { content?: string };
  done?: boolean;
  done_reason?: string;
  prompt_eval_count?: number;
  eval_count?: number;
  error?: string;
}

/**
 * Anthropic xabar shaklini Ollama shakliga o'tkazadi.
 * Loyihada xabar tanasi doim oddiy matn, lekin blokli shakl ham kelishi
 * mumkin — shuning uchun ikkalasi ham qo'llab-quvvatlanadi.
 */
function toOllamaMessages(messages: MessageParam[]): OllamaMessage[] {
  return messages.map((m) => ({
    role: m.role,
    content:
      typeof m.content === "string"
        ? m.content
        : m.content
            .map((b) => (b.type === "text" ? b.text : ""))
            .filter(Boolean)
            .join("\n"),
  }));
}

/*
 * Kichik modellar uchun qo'shimcha tiyish.
 *
 * NEGA KERAK. Tizim promptida ishonchlilik qoidalari allaqachon bor va Claude
 * ularga amal qiladi. 7B model esa amal qilmaydi: sinovda u bazada umuman
 * yo'q "Fuqarolik kodeksi 380-moddasi" ni o'ylab topdi. CLAUDE.md buni aniq
 * taqiqlaydi, shuning uchun qoida promptning OXIRIGA qayta qo'yiladi —
 * kichik modellar oxirgi ko'rsatmaga kuchliroq amal qiladi.
 */
const LOCAL_GUARD = `
## ENG MUHIM QOIDA — BUZILMAYDI

Modda raqami yoki hujjat nomini faqat yuqoridagi "HUQUQIY MANBALAR" blokida
AYNAN yozilgan boʻlsa keltiring. Blokda yoʻq raqamni yozish — eng ogʻir xato.
Manbalarda javob boʻlmasa, shunday deb yozing: "Menda bu masala boʻyicha
norma matni yoʻq" — va lex.uz da tekshirishni tavsiya qiling.
Xotirangizdan modda raqami yozmang. Taxmin qilmang.

CRITICAL: Only cite article numbers that appear verbatim in the sources above.
If the answer is not in the sources, say you do not have the provision text.
Never recall article numbers from memory.`;

function buildMessages(opts: CallOptions): OllamaMessage[] {
  return [
    { role: "system", content: `${joinSystem(opts)}\n${LOCAL_GUARD}` },
    ...toOllamaMessages(opts.messages),
  ];
}

/**
 * Model sozlamalari.
 *
 * `num_ctx` — Ollama standarti 4096, bu bizga YETMAYDI: topilgan qonun
 * bo'laklari bilan birga so'rov 4000 tokendan oshadi va manbalar jimgina
 * kesilib qoladi (birinchi sinovdagi uydirma aynan shundan chiqqan).
 *
 * `temperature` — standarti 0.8, yuridik matn uchun juda yuqori. Bu sozlama
 * Claude Opus 5 da ishlatilmaydi (u qabul qilmaydi), lekin Ollama da
 * o'rinli va zarur.
 */
function modelOptions(maxTokens?: number): Record<string, unknown> {
  return {
    num_ctx: config.ollamaContext,
    // Servislar Claude uchun 16000 so'raydi — lokal model uchun bu qat'iy
    // chegaralanadi (sabab `config.ollamaMaxOutput` izohida).
    num_predict: Math.min(maxTokens ?? 2048, config.ollamaMaxOutput),
    // Yuridik matnda ijodkorlik kerak emas: 0 — har safar bir xil javob.
    temperature: 0,
    top_p: 0.9,
    // Takrorlanib ketishga qarshi. 1.05 kuchsiz bo'lib chiqdi: model bir xil
    // bandni o'ttiz martadan ortiq yozdi.
    repeat_penalty: 1.15,
    repeat_last_n: 256,
  };
}

function usageOf(chunk: OllamaChunk): Usage {
  return {
    inputTokens: chunk.prompt_eval_count ?? 0,
    outputTokens: chunk.eval_count ?? 0,
  };
}

async function post(
  path: string,
  body: Record<string, unknown>,
): Promise<Response> {
  const url = `${config.ollamaBaseUrl}${path}`;

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (err) {
    // Eng ko'p uchraydigan holat: Ollama umuman ishlamayapti.
    if (err instanceof DOMException && err.name === "TimeoutError") {
      throw new OllamaError(
        "Lokal model javob bermadi (vaqt tugadi). Model juda katta boʻlishi mumkin.",
      );
    }
    throw new OllamaError(
      `Lokal modelga ulanib boʻlmadi (${config.ollamaBaseUrl}). ` +
        `Ollama ishga tushganini tekshiring: \`ollama serve\` yoki ` +
        `\`brew services start ollama\`.`,
    );
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    if (res.status === 404) {
      throw new OllamaError(
        `«${config.ollamaModel}» modeli topilmadi. ` +
          `Yuklab oling: \`ollama pull ${config.ollamaModel}\`.`,
      );
    }
    throw new OllamaError(
      `Lokal model xatosi (${res.status}): ${text.slice(0, 200) || "nomaʼlum"}`,
    );
  }

  return res;
}

/**
 * NDJSON oqimini bo'lak-bo'lak o'qiydi.
 *
 * Tarmoq bo'laklari qator chegarasida kelmaydi, shuning uchun tugallanmagan
 * qator keyingi bo'lakka qo'shib o'qiladi.
 */
async function* readNdjson(res: Response): AsyncGenerator<OllamaChunk> {
  const reader = res.body?.getReader();
  if (!reader) throw new OllamaError("Lokal modeldan javob oqimi kelmadi.");

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        yield JSON.parse(trimmed) as OllamaChunk;
      }
    }

    const tail = buffer.trim();
    if (tail) yield JSON.parse(tail) as OllamaChunk;
  } finally {
    reader.releaseLock();
  }
}

interface Collected {
  text: string;
  usage: Usage;
  truncated: boolean;
}

async function collect(res: Response): Promise<Collected> {
  let text = "";
  let usage: Usage = { inputTokens: 0, outputTokens: 0 };
  let truncated = false;

  for await (const chunk of readNdjson(res)) {
    if (chunk.error) throw new OllamaError(chunk.error);
    text += chunk.message?.content ?? "";
    if (chunk.done) {
      usage = usageOf(chunk);
      truncated = chunk.done_reason === "length";
    }
  }

  return { text, usage, truncated };
}

// ── Amallar ────────────────────────────────────────────────────────────────

export async function complete(opts: CallOptions): Promise<CompleteResult> {
  const res = await post("/api/chat", {
    model: config.ollamaModel,
    messages: buildMessages(opts),
    stream: true,
    options: modelOptions(opts.maxTokens),
  });

  const { text, usage, truncated } = await collect(res);
  return { text: text.trim(), usage, truncated };
}

export async function completeJSON<T>(
  opts: CallOptions & { schema: Record<string, unknown> },
): Promise<JsonResult<T>> {
  const res = await post("/api/chat", {
    model: config.ollamaModel,
    messages: buildMessages(opts),
    stream: true,
    // Ollama JSON schema ni to'g'ridan-to'g'ri qabul qiladi.
    format: opts.schema,
    options: modelOptions(opts.maxTokens),
  });

  const { text, usage, truncated } = await collect(res);

  if (truncated) {
    throw new Error(
      "Javob juda uzun boʻlib kesildi. Hujjatni qisqartiring yoki qismlarga boʻling.",
    );
  }

  try {
    return { data: JSON.parse(text) as T, usage };
  } catch {
    throw new Error("Lokal model qaytargan JSON oʻqib boʻlmadi.");
  }
}

export async function* streamText(
  opts: StreamOptions,
): AsyncGenerator<string, void, unknown> {
  const res = await post("/api/chat", {
    model: config.ollamaModel,
    messages: buildMessages(opts),
    stream: true,
    options: modelOptions(opts.maxTokens),
  });

  for await (const chunk of readNdjson(res)) {
    if (chunk.error) throw new OllamaError(chunk.error);

    const text = chunk.message?.content;
    if (text) yield text;

    if (chunk.done) opts.onDone?.(usageOf(chunk));
  }
}

export const ollamaProvider: LlmProvider = {
  name: "ollama",
  modelName: () => config.ollamaModel,
  complete,
  completeJSON,
  streamText,
};

/** Lokal model tayyor turibdimi — panel va sog'liq tekshiruvi uchun. */
export async function pingOllama(): Promise<{
  ok: boolean;
  models?: string[];
  error?: string;
}> {
  try {
    const res = await fetch(`${config.ollamaBaseUrl}/api/tags`, {
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) return { ok: false, error: `HTTP ${res.status}` };

    const body = (await res.json()) as { models?: Array<{ name: string }> };
    const models = (body.models ?? []).map((m) => m.name);

    return models.includes(config.ollamaModel)
      ? { ok: true, models }
      : {
          ok: false,
          models,
          error: `«${config.ollamaModel}» yuklab olinmagan.`,
        };
  } catch {
    return { ok: false, error: "ulanmadi" };
  }
}
