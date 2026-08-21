import { checkApiKey, config } from "@/lib/config";
import { errorJson } from "@/lib/util/sse";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * GET /api/norma?q=...&k=8 — norma topuvchi.
 *
 * NEGA `/api/search` DAN ALOHIDA. `/api/search` veb ilovaning O'Z
 * SQLite bazasidan qidiradi. Bu marshrut esa **yadro indeksidan**
 * oladi: 808 hujjat, versiya filtri, qamrov darvozasi va iqtibos
 * yorliqlari o'sha yerda.
 *
 * NEGA MODEL CHAQIRILMAYDI. Norma topuvchining butun mohiyati shu:
 * u qonun matnini KO'RSATADI, o'zidan hech narsa yozmaydi. Model
 * bo'lmagani uchun u gallyutsinatsiya ham qila olmaydi.
 */
export async function GET(request: Request): Promise<Response> {
  if (!checkApiKey(request)) return errorJson("Ruxsat yoʻq.", 401);

  const url = new URL(request.url);
  const q = url.searchParams.get("q")?.trim();
  if (!q) return errorJson("`q` parametri koʻrsatilmagan.");

  const k = Number(url.searchParams.get("k") ?? 8);
  const topK = Number.isFinite(k) ? Math.min(Math.max(1, k), 30) : 8;

  const headers: Record<string, string> = { "content-type": "application/json" };
  if (config.uzlegalApiKey) headers.authorization = `Bearer ${config.uzlegalApiKey}`;

  try {
    const res = await fetch(`${config.uzlegalApiUrl}/v1/search`, {
      method: "POST",
      headers,
      body: JSON.stringify({ query: q, top_k: topK }),
      signal: AbortSignal.timeout(30_000),
      cache: "no-store",
    });

    if (!res.ok) {
      return errorJson(`Yadro ${res.status} qaytardi.`, 502);
    }
    return Response.json(await res.json());
  } catch (err) {
    /*
     * Yadro oʻchiq boʻlsa buni AYTAMIZ. Boʻsh roʻyxat qaytarish
     * «hech narsa topilmadi» degan notoʻgʻri taassurot qoldiradi —
     * holbuki qidiruv umuman ishlamagan.
     */
    const detail = err instanceof Error ? err.message : "nomaʼlum xatolik";
    return errorJson(`Yadroga ulanib boʻlmadi: ${detail}. Ishga tushiring: uzlegal serve`, 503);
  }
}
