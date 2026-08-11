import { checkApiKey, config } from "@/lib/config";
import { callMeta, humanError } from "@/lib/llm";
import { analyze } from "@/lib/services/analyze";
import { currentUser } from "@/lib/auth/session";
import { recordAiCall } from "@/lib/db/log";
import { extractText } from "@/lib/util/extract";
import { errorJson } from "@/lib/util/sse";
import type { Lang, Script } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

/** Yuklanadigan fayl uchun chegara (25 MB). */
const MAX_FILE_BYTES = 25 * 1024 * 1024;

/**
 * POST /api/analyze — hujjat tahlili.
 *
 * Ikki xil kirish qo'llab-quvvatlanadi:
 *  1. multipart/form-data: `file` (pdf/docx/txt/md/html), `perspective?`, `lang?`
 *  2. application/json:    { text, filename?, perspective?, lang?, script? }
 */
export async function POST(request: Request): Promise<Response> {
  if (!checkApiKey(request)) return errorJson("Ruxsat yoʻq.", 401);

  try {
    const contentType = request.headers.get("content-type") ?? "";
    let text: string;
    let filename: string | undefined;
    let perspective: string | undefined;
    let lang: Lang | "auto" | undefined;
    let script: Script | "auto" | undefined;

    if (contentType.includes("multipart/form-data")) {
      const form = await request.formData();
      const file = form.get("file");

      if (!(file instanceof File)) {
        return errorJson("`file` maydonida fayl yuborilmadi.");
      }
      if (file.size > MAX_FILE_BYTES) {
        return errorJson("Fayl juda katta (chegara: 25 MB).", 413);
      }

      filename = file.name;
      const buffer = Buffer.from(await file.arrayBuffer());
      text = await extractText(buffer, file.name);

      perspective = asString(form.get("perspective"));
      lang = asString(form.get("lang")) as Lang | "auto" | undefined;
      script = asString(form.get("script")) as Script | "auto" | undefined;
    } else {
      const body = (await request.json()) as {
        text?: string;
        filename?: string;
        perspective?: string;
        lang?: Lang | "auto";
        script?: Script | "auto";
      };
      if (!body.text?.trim()) {
        return errorJson("`text` yoki `file` yuborilishi kerak.");
      }
      text = body.text;
      filename = body.filename;
      perspective = body.perspective;
      lang = body.lang;
      script = body.script;
    }

    const started = Date.now();
    const user = await currentUser(request);
    const result = await analyze({ text, filename, perspective, lang, script });

    recordAiCall({
      kind: "analyze",
      surface: "web",
      userId: user?._id ?? null,
      telegramId: user?.telegramId,
      ...callMeta(),
      input: text,
      output: JSON.stringify(result),
      durationMs: Date.now() - started,
      label: filename,
    });

    return Response.json(result);
  } catch (err) {
    return errorJson(humanError(err), 500);
  }
}

function asString(v: FormDataEntryValue | null): string | undefined {
  return typeof v === "string" && v.trim() ? v.trim() : undefined;
}
