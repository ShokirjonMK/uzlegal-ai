import { config } from "@/lib/config";
import { activeModel, pingOllama } from "@/lib/llm";
import { adminGuard, adminSetup } from "@/lib/auth/admin";
import { stats } from "@/lib/rag/store";
import { lifetime, summary } from "@/lib/analytics";
import { pingMongo, isMongoConfigured } from "@/lib/db/mongo";
import { aiCalls, users } from "@/lib/db/collections";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** GET /api/admin/holat?soat=24 — tizim, korpus va statistika bir javobda. */
export async function GET(request: Request): Promise<Response> {
  const denied = adminGuard(request);
  if (denied) return denied;

  const hours = clampHours(new URL(request.url).searchParams.get("soat"));

  const active = activeModel();

  const [corpus, mongo, stat, ollama] = await Promise.all([
    Promise.resolve().then(() => safe(() => stats())),
    pingMongo(),
    Promise.resolve().then(() => safe(() => ({ ...summary(hours), ...lifetime() }))),
    // Lokal model faqat oʻsha provayder tanlanganda soʻraladi.
    config.provider === "ollama" ? pingOllama() : Promise.resolve(null),
  ]);

  return Response.json({
    soat: hours,
    tizim: {
      provider: active.provider,
      model: active.model,
      ollama: ollama ? { ...ollama, url: config.ollamaBaseUrl } : null,
      effort: config.effort,
      lang: config.lang,
      script: config.script,
      anthropicKey: Boolean(config.anthropicApiKey),
      telegram: Boolean(config.telegramToken),
      apiProtected: Boolean(config.apiKey),
      embedding: {
        provider: config.embeddingProvider,
        model:
          config.embeddingProvider === "voyage"
            ? config.voyageModel
            : "hashed-ngrams",
      },
      admin: adminSetup(),
      mongo: { sozlangan: isMongoConfigured(), ...mongo },
    },
    korpus: corpus.ok ? corpus.value : { xato: corpus.error },
    statistika: stat.ok ? stat.value : { xato: stat.error },
    baza: await mongoCounts(),
  });
}

function clampHours(raw: string | null): number {
  const n = Number(raw ?? 24);
  return Number.isFinite(n) ? Math.min(Math.max(1, n), 24 * 365) : 24;
}

type Safe<T> = { ok: true; value: T } | { ok: false; error: string };

function safe<T>(fn: () => T): Safe<T> {
  try {
    return { ok: true, value: fn() };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "xatolik" };
  }
}

/** Mongo dagi hajm ko'rsatkichlari. Baza yo'q bo'lsa `null`. */
async function mongoCounts(): Promise<{
  foydalanuvchi: number;
  yozishma: number;
} | null> {
  if (!isMongoConfigured()) return null;
  try {
    const [userCol, callCol] = await Promise.all([users(), aiCalls()]);
    const [foydalanuvchi, yozishma] = await Promise.all([
      userCol.estimatedDocumentCount(),
      callCol.estimatedDocumentCount(),
    ]);
    return { foydalanuvchi, yozishma };
  } catch {
    return null;
  }
}
