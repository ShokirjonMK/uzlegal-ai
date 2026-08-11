import { checkApiKey, config } from "@/lib/config";
import { callMeta, humanError } from "@/lib/llm";
import { ask } from "@/lib/services/ask";
import { currentUser } from "@/lib/auth/session";
import { recordAiCall } from "@/lib/db/log";
import { errorJson } from "@/lib/util/sse";
import type { AskRequest } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

/**
 * POST /api/ask — savol-javob, oddiy JSON javob (streamingsiz).
 * Bot va integratsiyalar uchun qulay.
 *
 * Kirish:  { question, history?, lang?, script?, topK?, noRag? }
 * Chiqish: { answer, citations, lang, script, usage }
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

  try {
    const started = Date.now();
    const user = await currentUser(request);
    const result = await ask(body);

    recordAiCall({
      kind: "ask",
      surface: "api",
      userId: user?._id ?? null,
      telegramId: user?.telegramId,
      ...callMeta(),
      input: body.question,
      output: result.answer,
      citations: result.citations,
      inputTokens: result.usage?.inputTokens,
      outputTokens: result.usage?.outputTokens,
      durationMs: Date.now() - started,
    });

    return Response.json(result);
  } catch (err) {
    return errorJson(humanError(err), 500);
  }
}
