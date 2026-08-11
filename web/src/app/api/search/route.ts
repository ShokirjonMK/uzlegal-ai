import { checkApiKey } from "@/lib/config";
import { unifiedRetrieve } from "@/lib/rag/unified";
import { stats } from "@/lib/rag/store";
import { errorJson } from "@/lib/util/sse";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * GET /api/search?q=...&k=8 — qonun bazasidan to'g'ridan-to'g'ri qidirish.
 * Modelga murojaat qilinmaydi, faqat baza.
 */
export async function GET(request: Request): Promise<Response> {
  if (!checkApiKey(request)) return errorJson("Ruxsat yoʻq.", 401);

  const url = new URL(request.url);
  const q = url.searchParams.get("q")?.trim();
  if (!q) return errorJson("`q` parametri koʻrsatilmagan.");

  const k = Number(url.searchParams.get("k") ?? 8);
  const topK = Number.isFinite(k) ? Math.min(Math.max(1, k), 50) : 8;

  try {
    const results = await unifiedRetrieve(q, { topK });
    return Response.json({
      query: q,
      count: results.length,
      corpus: stats(),
      results: results.map((r) => ({
        score: Number(r.score.toFixed(4)),
        document: r.document,
        article: r.article,
        heading: r.heading,
        url: r.url,
        text: r.text,
      })),
    });
  } catch (err) {
    return errorJson(
      err instanceof Error ? err.message : "Qidiruvda xatolik.",
      500,
    );
  }
}
