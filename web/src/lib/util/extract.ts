/**
 * Turli formatdagi fayllardan matn ajratib olish.
 * Faqat server tomonda ishlaydi (Node runtime).
 */

import { extname } from "node:path";
import { fixApostrophes } from "../uz/orthography";

export type SupportedExt = ".txt" | ".md" | ".pdf" | ".docx" | ".html" | ".htm";

export const SUPPORTED_EXTENSIONS: readonly SupportedExt[] = [
  ".txt",
  ".md",
  ".pdf",
  ".docx",
  ".html",
  ".htm",
];

export function isSupported(filename: string): boolean {
  return (SUPPORTED_EXTENSIONS as readonly string[]).includes(
    extname(filename).toLowerCase(),
  );
}

/** Fayl kengaytmasi bo'yicha matnni ajratadi. */
export async function extractText(
  buffer: Buffer | Uint8Array,
  filename: string,
): Promise<string> {
  const ext = extname(filename).toLowerCase();
  const bytes = buffer instanceof Buffer ? buffer : Buffer.from(buffer);

  switch (ext) {
    case ".pdf":
      return clean(await fromPdf(bytes));
    case ".docx":
      return clean(await fromDocx(bytes));
    case ".html":
    case ".htm":
      return clean(stripHtml(bytes.toString("utf8")));
    case ".txt":
    case ".md":
      return clean(bytes.toString("utf8"));
    default:
      throw new Error(
        `Qoʻllab-quvvatlanmaydigan format: ${ext || "(kengaytmasiz)"}. ` +
          `Ruxsat etilgan: ${SUPPORTED_EXTENSIONS.join(", ")}`,
      );
  }
}

async function fromPdf(bytes: Buffer): Promise<string> {
  const { extractText: pdfExtract, getDocumentProxy } = await import("unpdf");
  const doc = await getDocumentProxy(new Uint8Array(bytes));
  const { text } = await pdfExtract(doc, { mergePages: true });
  return Array.isArray(text) ? text.join("\n\n") : text;
}

async function fromDocx(bytes: Buffer): Promise<string> {
  const mammoth = await import("mammoth");
  const { value } = await mammoth.extractRawText({ buffer: bytes });
  return value;
}

function stripHtml(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<\/(p|div|tr|li|h[1-6])>/gi, "\n")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#(\d+);/g, (_m, d: string) => String.fromCharCode(Number(d)));
}

/** Ajratilgan matnni tozalash: apostroflar, ortiqcha bo'sh joy, satr uzilishlari. */
function clean(text: string): string {
  return fixApostrophes(text)
    .replace(/\r\n?/g, "\n")
    .replace(/ /g, " ")
    // PDF dan kelgan so'z bo'linishi: "shartno-\nma" → "shartnoma"
    .replace(/(\p{Ll})-\n(\p{Ll})/gu, "$1$2")
    .replace(/[ \t]+/g, " ")
    .replace(/ *\n */g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
