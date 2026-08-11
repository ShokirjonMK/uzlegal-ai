import { checkApiKey, config } from "@/lib/config";
import { callMeta, humanError } from "@/lib/llm";
import { review } from "@/lib/services/review";
import { currentUser } from "@/lib/auth/session";
import { recordAiCall } from "@/lib/db/log";
import { extractText } from "@/lib/util/extract";
import { errorJson } from "@/lib/util/sse";
import type { Lang, Script } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

const MAX_FILE_BYTES = 25 * 1024 * 1024;

/**
 * POST /api/review — hujjatni majburiy talablar bo'yicha tekshirish.
 * Kirish `/api/analyze` bilan bir xil (multipart yoki JSON).
 */
export async function POST(request: Request): Promise<Response> {
  if (!checkApiKey(request)) return errorJson("Ruxsat yoʻq.", 401);

  try {
    const contentType = request.headers.get("content-type") ?? "";
    let text: string;
    let filename: string | undefined;
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
      text = await extractText(Buffer.from(await file.arrayBuffer()), file.name);
      const l = form.get("lang");
      if (typeof l === "string" && l) lang = l as Lang | "auto";
    } else {
      const body = (await request.json()) as {
        text?: string;
        filename?: string;
        lang?: Lang | "auto";
        script?: Script | "auto";
      };
      if (!body.text?.trim()) {
        return errorJson("`text` yoki `file` yuborilishi kerak.");
      }
      text = body.text;
      filename = body.filename;
      lang = body.lang;
      script = body.script;
    }

    const started = Date.now();
    const user = await currentUser(request);
    const result = await review({ text, filename, lang, script });

    recordAiCall({
      kind: "review",
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
