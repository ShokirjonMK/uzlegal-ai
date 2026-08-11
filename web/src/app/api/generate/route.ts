import { checkApiKey, config } from "@/lib/config";
import { callMeta, humanError } from "@/lib/llm";
import { generate, generateStream } from "@/lib/services/generate";
import { currentUser } from "@/lib/auth/session";
import { recordAiCall } from "@/lib/db/log";
import { tapStream } from "@/lib/db/tap";
import { resultToDocx, safeFilename } from "@/lib/util/docx";
import { errorJson, sseResponse } from "@/lib/util/sse";
import { TEMPLATE_LIST } from "@/lib/prompts";
import type { GenerateRequest } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

/** GET /api/generate — mavjud shablonlar ro'yxati. */
export async function GET(): Promise<Response> {
  return Response.json({ templates: TEMPLATE_LIST });
}

/**
 * POST /api/generate — hujjat loyihasini tayyorlash.
 *
 * `?format=` parametri:
 *   - `json`   (standart) — { title, markdown, placeholders, notes }
 *   - `sse`    — oqim (web UI uchun)
 *   - `docx`   — tayyor .docx fayl
 */
export async function POST(request: Request): Promise<Response> {
  if (!checkApiKey(request)) return errorJson("Ruxsat yoʻq.", 401);

  const format = new URL(request.url).searchParams.get("format") ?? "json";

  let body: GenerateRequest;
  try {
    body = (await request.json()) as GenerateRequest;
  } catch {
    return errorJson("Soʻrov JSON formatida boʻlishi kerak.");
  }

  if (!body.template) {
    return errorJson("`template` maydoni koʻrsatilmagan.");
  }
  if (!body.details?.trim() && !Object.keys(body.fields ?? {}).length) {
    return errorJson("`details` yoki `fields` toʻldirilishi kerak.");
  }

  const user = await currentUser(request);

  if (format === "sse") {
    return sseResponse(
      tapStream(generateStream(body), {
        kind: "generate",
        surface: "web",
        userId: user?._id ?? null,
        telegramId: user?.telegramId,
        input: body.details ?? JSON.stringify(body.fields ?? {}),
        label: body.template,
      }),
    );
  }

  try {
    const started = Date.now();
    const result = await generate(body);

    recordAiCall({
      kind: "generate",
      surface: "web",
      userId: user?._id ?? null,
      telegramId: user?.telegramId,
      ...callMeta(),
      input: body.details ?? JSON.stringify(body.fields ?? {}),
      output: result.markdown,
      durationMs: Date.now() - started,
      label: body.template,
    });

    if (format === "docx") {
      const buffer = await resultToDocx(result);
      return new Response(new Uint8Array(buffer), {
        headers: {
          "content-type":
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          "content-disposition": `attachment; filename*=UTF-8''${encodeURIComponent(
            safeFilename(result.title, "docx"),
          )}`,
        },
      });
    }

    return Response.json(result);
  } catch (err) {
    return errorJson(humanError(err), 500);
  }
}
