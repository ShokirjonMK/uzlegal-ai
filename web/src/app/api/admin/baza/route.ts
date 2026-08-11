import { mkdir, writeFile } from "node:fs/promises";
import { basename, join, resolve, sep } from "node:path";
import { config } from "@/lib/config";
import { adminGuard } from "@/lib/auth/admin";
import { errorJson } from "@/lib/util/sse";
import { deleteDocument, stats } from "@/lib/rag/store";
import { ingestDirectory, ingestFile } from "@/lib/rag/ingest";
import { isSupported } from "@/lib/util/extract";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
/** Vektorlashtirish sekin — Next ning standart chegarasi yetmaydi. */
export const maxDuration = 300;

const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

/** GET /api/admin/baza — bazadagi hujjatlar ro'yxati. */
export async function GET(request: Request): Promise<Response> {
  const denied = adminGuard(request);
  if (denied) return denied;

  try {
    return Response.json({ korpus: stats(), papka: resolve(config.corpusDir) });
  } catch (err) {
    return errorJson(err instanceof Error ? err.message : "Bazani oʻqib boʻlmadi.", 500);
  }
}

/**
 * POST /api/admin/baza — hujjat yuklash.
 *
 * Ikki shakl:
 *  - `multipart/form-data` + `file` — bitta fayl yuklanadi va bazaga qo'shiladi;
 *  - `application/json` + `{ amal: "papka" }` — `data/corpus/` dagi hammasi.
 */
export async function POST(request: Request): Promise<Response> {
  const denied = adminGuard(request);
  if (denied) return denied;

  const contentType = request.headers.get("content-type") ?? "";

  try {
    if (contentType.includes("multipart/form-data")) {
      return await ingestUpload(request);
    }

    const body = (await request.json().catch(() => ({}))) as { amal?: unknown };
    if (body.amal !== "papka") {
      return errorJson("Nomaʼlum amal. Fayl yuboring yoki `{ \"amal\": \"papka\" }`.");
    }

    const summary = await ingestDirectory();
    return Response.json({
      ok: true,
      xabar:
        summary.files === 0
          ? "Papkada mos fayl topilmadi."
          : `${summary.files} ta fayl, ${summary.chunks} ta boʻlak yuklandi.`,
      natija: summary,
      korpus: stats(),
    });
  } catch (err) {
    return errorJson(err instanceof Error ? err.message : "Yuklashda xatolik.", 500);
  }
}

async function ingestUpload(request: Request): Promise<Response> {
  const form = await request.formData();
  const file = form.get("file");

  if (!(file instanceof File)) return errorJson("Fayl yuborilmadi.");
  if (file.size === 0) return errorJson("Fayl boʻsh.");
  if (file.size > MAX_UPLOAD_BYTES) {
    return errorJson("Fayl juda katta — 25 MB gacha ruxsat etiladi.", 413);
  }

  // Fayl nomi faqat nomdan iborat bo'lsin: `../` bilan papkadan chiqib
  // ketishga urinish shu yerda to'xtaydi.
  const name = basename(file.name).replace(/[/\\]/g, "").trim();
  if (!name) return errorJson("Fayl nomi notoʻgʻri.");
  if (!isSupported(name)) {
    return errorJson("Bu fayl turi qoʻllab-quvvatlanmaydi (PDF, DOCX, TXT, MD, HTML).");
  }

  const dir = resolve(config.corpusDir);
  const target = resolve(join(dir, name));
  if (target !== join(dir, name) || !target.startsWith(dir + sep)) {
    return errorJson("Fayl nomi notoʻgʻri.");
  }

  await mkdir(dir, { recursive: true });
  await writeFile(target, Buffer.from(await file.arrayBuffer()));

  // `replace` — o'sha nomdagi hujjatning eski bo'laklari avval o'chiriladi,
  // aks holda tahrir qilingan qonun matni ikki nusxada qolib ketardi.
  const result = await ingestFile(target, { replace: true });

  return Response.json({
    ok: true,
    xabar:
      result.chunks === 0
        ? `«${result.document}» dan boʻlak ajratilmadi — matn boʻsh yoki tanilmadi.`
        : `«${result.document}» yuklandi: ${result.chunks} ta boʻlak.`,
    natija: result,
    korpus: stats(),
  });
}

/** DELETE /api/admin/baza?hujjat=… — hujjatni bazadan o'chiradi. */
export async function DELETE(request: Request): Promise<Response> {
  const denied = adminGuard(request);
  if (denied) return denied;

  const document = new URL(request.url).searchParams.get("hujjat")?.trim();
  if (!document) return errorJson("`hujjat` parametri koʻrsatilmagan.");

  try {
    const removed = deleteDocument(document);
    if (removed === 0) {
      return errorJson(`«${document}» bazada topilmadi.`, 404);
    }
    return Response.json({
      ok: true,
      xabar: `«${document}» oʻchirildi: ${removed} ta boʻlak.`,
      korpus: stats(),
    });
  } catch (err) {
    return errorJson(err instanceof Error ? err.message : "Oʻchirishda xatolik.", 500);
  }
}
