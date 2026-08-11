import type { Filter } from "mongodb";
import { adminGuard } from "@/lib/auth/admin";
import { errorJson } from "@/lib/util/sse";
import { aiCalls, type AiCallDoc } from "@/lib/db/collections";
import { isMongoConfigured } from "@/lib/db/mongo";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const PAGE_SIZE = 20;

/**
 * GET /api/admin/yozishmalar?sahifa=1&tur=ask&q=…
 *
 * Modelga qilingan murojaatlar — savol va javob to'liq matni bilan.
 * Faqat admin ko'radi.
 */
export async function GET(request: Request): Promise<Response> {
  const denied = adminGuard(request);
  if (denied) return denied;

  if (!isMongoConfigured()) {
    return errorJson(
      "Yozishmalar bazasi sozlanmagan. `.env.local` ga MONGODB_URI qoʻshing.",
      503,
    );
  }

  const params = new URL(request.url).searchParams;
  const page = Math.max(1, Number(params.get("sahifa") ?? 1) || 1);
  const kind = params.get("tur")?.trim();
  const query = params.get("q")?.trim();

  const filter: Filter<AiCallDoc> = {};
  if (kind) filter.kind = kind as AiCallDoc["kind"];
  if (query) {
    // Oddiy matn qidiruvi: kirish yoki chiqish matnida.
    const rx = new RegExp(escapeRegExp(query), "i");
    filter.$or = [{ input: rx }, { output: rx }];
  }

  try {
    const col = await aiCalls();
    const [rows, jami] = await Promise.all([
      col
        .find(filter)
        .sort({ createdAt: -1 })
        .skip((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .toArray(),
      col.countDocuments(filter),
    ]);

    return Response.json({
      sahifa: page,
      sahifaHajmi: PAGE_SIZE,
      jami,
      yozuvlar: rows.map((r) => ({
        id: r._id.toHexString(),
        tur: r.kind,
        yuza: r.surface,
        model: r.model,
        effort: r.effort,
        kirish: r.input,
        chiqish: r.output,
        inputTokens: r.inputTokens,
        outputTokens: r.outputTokens,
        davomiylik: r.durationMs,
        xato: r.error,
        belgi: r.label,
        telegramId: r.telegramId,
        userId: r.userId?.toHexString(),
        sana: r.createdAt.toISOString(),
      })),
    });
  } catch (err) {
    return errorJson(
      err instanceof Error ? err.message : "Yozishmalarni oʻqib boʻlmadi.",
      500,
    );
  }
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
