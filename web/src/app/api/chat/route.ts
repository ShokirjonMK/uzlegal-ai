import { checkApiKey } from "@/lib/config";
import { askStream } from "@/lib/services/ask";
import { errorJson, sseResponse } from "@/lib/util/sse";
import { currentUser } from "@/lib/auth/session";
import { tapStream } from "@/lib/db/tap";
import type { AskRequest } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

/**
 * POST /api/chat — savol-javob, SSE oqimi.
 *
 * Hodisalar: status | citations | delta | done | error
 */
export async function POST(request: Request): Promise<Response> {
  if (!checkApiKey(request)) return errorJson("Ruxsat yoʻq.", 401);

  let body: AskRequest;
  try {
    body = (await request.json()) as AskRequest;
  } catch {
    return errorJson("Soʻrov JSON formatida boʻlishi kerak.");
  }

  if (!body.question?.trim()) {
    return errorJson("`question` maydoni boʻsh boʻlmasligi kerak.");
  }

  // Kim so'ragani ma'lum bo'lsa yozuvga biriktiriladi; mehmon bo'lsa `null`.
  const user = await currentUser(request);

  return sseResponse(
    tapStream(askStream(body), {
      kind: "ask",
      surface: "web",
      userId: user?._id ?? null,
      telegramId: user?.telegramId,
      input: body.question,
    }),
  );
}
