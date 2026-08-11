/**
 * Markdown → .docx.
 * Foydalanuvchi tayyor hujjatni Word'da ochib tahrirlashi uchun.
 */

import type { GenerateResult } from "../types";

/** Markdown matnini .docx faylga aylantiradi. */
export async function markdownToDocx(
  markdown: string,
  title: string,
): Promise<Buffer> {
  const {
    Document,
    Packer,
    Paragraph,
    TextRun,
    HeadingLevel,
    AlignmentType,
  } = await import("docx");

  const children: InstanceType<typeof Paragraph>[] = [];

  for (const rawLine of markdown.split("\n")) {
    const line = rawLine.replace(/\s+$/, "");

    if (!line.trim()) {
      children.push(new Paragraph({ text: "" }));
      continue;
    }

    // Sarlavhalar
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) {
      const level = h[1]!.length;
      children.push(
        new Paragraph({
          heading:
            level === 1
              ? HeadingLevel.HEADING_1
              : level === 2
                ? HeadingLevel.HEADING_2
                : HeadingLevel.HEADING_3,
          alignment: level === 1 ? AlignmentType.CENTER : AlignmentType.LEFT,
          children: inlineRuns(h[2] ?? "", TextRun),
        }),
      );
      continue;
    }

    // Ajratuvchi chiziq
    if (/^\s*([-*_])\1{2,}\s*$/.test(line)) {
      children.push(new Paragraph({ text: "", border: undefined }));
      continue;
    }

    // Belgili ro'yxat
    const bullet = /^\s*[-*+]\s+(.*)$/.exec(line);
    if (bullet) {
      children.push(
        new Paragraph({
          bullet: { level: 0 },
          children: inlineRuns(bullet[1] ?? "", TextRun),
        }),
      );
      continue;
    }

    // Raqamli band: "1.", "1.1.", "2)" — hujjatlarda ko'p uchraydi,
    // shuning uchun raqamni matn ichida qoldiramiz (avtoraqamlash emas).
    children.push(
      new Paragraph({
        children: inlineRuns(line, TextRun),
        spacing: { after: 120 },
      }),
    );
  }

  const doc = new Document({
    creator: "AI Lawyer",
    title,
    description: "AI Lawyer tomonidan tayyorlangan hujjat loyihasi",
    sections: [{ properties: {}, children }],
  });

  return Buffer.from(await Packer.toBuffer(doc));
}

/**
 * Bir satr ichidagi **qalin** matnni ajratadi.
 * Qolgan markdown belgilarini olib tashlaydi.
 */
function inlineRuns(
  text: string,
  TextRunCtor: typeof import("docx").TextRun,
): InstanceType<typeof import("docx").TextRun>[] {
  const runs: InstanceType<typeof import("docx").TextRun>[] = [];
  const parts = text.split(/(\*\*[^*]+\*\*)/g);

  for (const part of parts) {
    if (!part) continue;
    const bold = /^\*\*[^*]+\*\*$/.test(part);
    const clean = bold
      ? part.slice(2, -2)
      : part.replace(/[*_`]/g, "");
    if (clean) runs.push(new TextRunCtor({ text: clean, bold }));
  }

  if (runs.length === 0) runs.push(new TextRunCtor({ text: "" }));
  return runs;
}

/** Generatsiya natijasini .docx ga aylantiradi. */
export async function resultToDocx(result: GenerateResult): Promise<Buffer> {
  return markdownToDocx(result.markdown, result.title);
}

/** Fayl nomi uchun xavfsiz satr yasaydi. */
export function safeFilename(title: string, ext: string): string {
  const base = title
    .normalize("NFKD")
    .replace(/[^\p{L}\p{N}\s-]/gu, "")
    .trim()
    .replace(/\s+/g, "-")
    .slice(0, 60);
  return `${base || "hujjat"}.${ext}`;
}
