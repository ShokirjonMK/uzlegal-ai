/**
 * Claude API bilan ishlash qatlami.
 *
 * Bu yerda modelga bog'liq barcha nozikliklar bir joyga jamlangan:
 * adaptiv fikrlash, effort, prompt keshlash, rad javobini (refusal) qayta ishlash
 * va strukturali chiqish (structured outputs).
 */

import Anthropic from "@anthropic-ai/sdk";
import type {
  MessageParam,
  TextBlockParam,
  Message,
} from "@anthropic-ai/sdk/resources/messages";
import { config } from "../config";
import type { Usage } from "../types";
import type {
  CallOptions,
  CompleteResult,
  JsonResult,
  LlmProvider,
  StreamOptions,
} from "./types";

let client: Anthropic | null = null;

/** Anthropic klienti (bir marta yaratiladi). */
export function getClient(): Anthropic {
  if (!client) {
    client = new Anthropic({
      apiKey: config.anthropicApiKey,
      // Uzoq fikrlash uchun kengaytirilgan taymaut (10 daqiqa).
      timeout: 10 * 60 * 1000,
      maxRetries: 2,
    });
  }
  return client;
}

/** Model rad javobini qaytarganda tashlanadi. */
export class RefusalError extends Error {
  constructor(
    readonly category: string | null,
    readonly explanation: string | null,
  ) {
    super(
      "Model bu soʻrovga javob berishdan bosh tortdi" +
        (category ? ` (sabab turkumi: ${category})` : "") +
        ".",
    );
    this.name = "RefusalError";
  }
}

/** API kaliti sozlanmaganda tashlanadi. */
export class MissingApiKeyError extends Error {
  constructor() {
    super(
      "ANTHROPIC_API_KEY sozlanmagan. `.env.local` faylida kalitni koʻrsating " +
        "(namuna uchun `.env.example` ga qarang).",
    );
    this.name = "MissingApiKeyError";
  }
}

function assertApiKey(): void {
  if (!config.anthropicApiKey && !process.env.ANTHROPIC_AUTH_TOKEN) {
    throw new MissingApiKeyError();
  }
}

/*
 * Chaqiruv tiplari `./types` da — ular Ollama provayderi bilan umumiy.
 * Bu yerda faqat Anthropic ga xos xatti-harakat: keshlash, `effort`,
 * fikrlash rejimi va rad javobi.
 */

/**
 * Tizim promptini bloklarga ajratadi va barqaror qismga kesh nuqtasini qo'yadi.
 *
 * Keshlash prefiks bo'yicha ishlaydi: barqaror matn birinchi, o'zgaruvchan matn
 * keyin turishi shart, aks holda kesh har so'rovda buziladi.
 */
function buildSystem(opts: CallOptions): TextBlockParam[] {
  const blocks: TextBlockParam[] = [
    {
      type: "text",
      text: opts.systemStable,
      cache_control: { type: "ephemeral" },
    },
  ];
  if (opts.systemDynamic?.trim()) {
    blocks.push({ type: "text", text: opts.systemDynamic });
  }
  return blocks;
}

function thinkingFor(opts: CallOptions) {
  const effort = opts.effort ?? config.effort;
  // Claude Opus 5 da fikrlashni o'chirish faqat effort `high` va undan past bo'lsa mumkin.
  const canDisable = effort !== "xhigh" && effort !== "max";
  if (opts.disableThinking && canDisable) {
    return { type: "disabled" as const };
  }
  return { type: "adaptive" as const };
}

function toUsage(msg: Message): Usage {
  return {
    inputTokens: msg.usage.input_tokens,
    outputTokens: msg.usage.output_tokens,
    cacheReadTokens: msg.usage.cache_read_input_tokens ?? undefined,
    cacheWriteTokens: msg.usage.cache_creation_input_tokens ?? undefined,
  };
}

/** Javobdagi barcha matn bloklarini birlashtiradi. */
function textOf(msg: Message): string {
  return msg.content
    .filter((b): b is Extract<typeof b, { type: "text" }> => b.type === "text")
    .map((b) => b.text)
    .join("");
}

/** Rad javobi bo'lsa xato tashlaydi. `content` ni o'qishdan OLDIN chaqiriladi. */
function assertNotRefused(msg: Message): void {
  if (msg.stop_reason === "refusal") {
    throw new RefusalError(
      msg.stop_details?.category ?? null,
      msg.stop_details?.explanation ?? null,
    );
  }
}

// ── Oddiy (streamingsiz) so'rov ────────────────────────────────────────────

/** Bir martalik so'rov. Uzun chiqish kutilsa `streamText` dan foydalaning. */
export async function complete(opts: CallOptions): Promise<CompleteResult> {
  assertApiKey();
  const msg = await getClient().messages.create({
    model: config.model,
    max_tokens: opts.maxTokens ?? 16000,
    system: buildSystem(opts),
    messages: opts.messages,
    thinking: thinkingFor(opts),
    output_config: { effort: opts.effort ?? config.effort },
  });

  assertNotRefused(msg);
  return {
    text: textOf(msg),
    usage: toUsage(msg),
    truncated: msg.stop_reason === "max_tokens",
  };
}

// ── Strukturali chiqish (JSON schema) ──────────────────────────────────────

/**
 * Modeldan aniq JSON schema bo'yicha javob oladi.
 * Hujjat tahlili va tekshiruvlar uchun ishlatiladi — natija har doim
 * bir xil shaklda bo'lishini kafolatlaydi.
 */
export async function completeJSON<T>(
  opts: CallOptions & { schema: Record<string, unknown> },
): Promise<JsonResult<T>> {
  assertApiKey();
  const msg = await getClient().messages.create({
    model: config.model,
    // Uzun tahlil natijasi kesilib qolmasligi uchun keng chegara + streaming.
    max_tokens: opts.maxTokens ?? 16000,
    system: buildSystem(opts),
    messages: opts.messages,
    thinking: thinkingFor(opts),
    output_config: {
      effort: opts.effort ?? config.effort,
      format: { type: "json_schema", schema: opts.schema },
    },
  });

  assertNotRefused(msg);

  if (msg.stop_reason === "max_tokens") {
    throw new Error(
      "Javob juda uzun boʻlib kesildi. Hujjatni qisqartiring yoki qismlarga boʻling.",
    );
  }

  const raw = textOf(msg);
  try {
    return { data: JSON.parse(raw) as T, usage: toUsage(msg) };
  } catch {
    throw new Error("Model qaytargan JSON oʻqib boʻlmadi.");
  }
}

// ── Streaming ──────────────────────────────────────────────────────────────

/**
 * Javobni bo'lak-bo'lak qaytaradi. Oxirida `onDone` orqali usage beriladi.
 * Chat va uzun hujjat generatsiyasi uchun.
 */
export async function* streamText(
  opts: StreamOptions,
): AsyncGenerator<string, void, unknown> {
  assertApiKey();

  const stream = getClient().messages.stream({
    model: config.model,
    max_tokens: opts.maxTokens ?? 32000,
    system: buildSystem(opts),
    messages: opts.messages,
    thinking: thinkingFor(opts),
    output_config: { effort: opts.effort ?? config.effort },
  });

  for await (const event of stream) {
    if (
      event.type === "content_block_delta" &&
      event.delta.type === "text_delta"
    ) {
      yield event.delta.text;
    }
  }

  const final = await stream.finalMessage();
  assertNotRefused(final);
  opts.onDone?.(toUsage(final));
}

/** Provayder shartnomasi bo'yicha ko'rinish. */
export const anthropicProvider: LlmProvider = {
  name: "anthropic",
  modelName: () => config.model,
  complete,
  completeJSON,
  streamText,
};

/** Foydalanuvchiga ko'rsatiladigan xato matni (o'zbekcha). */
export function humanError(err: unknown): string {
  if (err instanceof MissingApiKeyError) return err.message;

  if (err instanceof RefusalError) {
    return (
      "Bu soʻrovga javob bera olmadim. Savolni boshqacha, aniqroq va " +
      "qonuniy maqsadni koʻrsatgan holda qayta bering."
    );
  }

  if (err instanceof Anthropic.APIError) {
    switch (err.status) {
      case 401:
        return "API kaliti notoʻgʻri yoki eskirgan.";
      case 403:
        return "API kalitida bu amal uchun ruxsat yoʻq.";
      case 429:
        return "Soʻrovlar chegarasiga yetildi. Bir necha soniyadan soʻng qayta urinib koʻring.";
      case 413:
        return "Yuborilgan matn juda katta. Hujjatni qisqartiring.";
      default:
        if ((err.status ?? 0) >= 500) {
          return "Xizmatda vaqtinchalik nosozlik. Birozdan soʻng qayta urinib koʻring.";
        }
        return `Soʻrovda xatolik: ${err.message}`;
    }
  }

  if (err instanceof Error) return err.message;
  return "Nomaʼlum xatolik yuz berdi.";
}
