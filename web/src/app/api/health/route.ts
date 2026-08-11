import { config } from "@/lib/config";
import { activeModel } from "@/lib/llm";
import { stats } from "@/lib/rag/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** GET /api/health — tizim holati. Maxfiy qiymatlar chiqarilmaydi. */
export async function GET(): Promise<Response> {
  let corpus;
  let corpusError: string | undefined;
  try {
    corpus = stats();
  } catch (err) {
    corpusError = err instanceof Error ? err.message : "baza ochilmadi";
  }

  const active = activeModel();

  return Response.json({
    ok: true,
    provider: active.provider,
    model: active.model,
    effort: config.effort,
    lang: config.lang,
    script: config.script,
    anthropicKey: Boolean(config.anthropicApiKey),
    embedding: {
      provider: config.embeddingProvider,
      model: config.embeddingProvider === "voyage" ? config.voyageModel : "hashed-ngrams",
    },
    telegram: Boolean(config.telegramToken),
    apiProtected: Boolean(config.apiKey),
    corpus: corpus ?? { error: corpusError },
  });
}
