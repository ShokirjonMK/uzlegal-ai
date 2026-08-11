/**
 * Qonun matnlarini bo'laklarga ajratish.
 *
 * Oddiy "har 500 belgida kes" usuli yuridik matn uchun yaramaydi: javobda
 * "Mehnat kodeksining 173-moddasi" deb aniq havola berish uchun bo'laklar
 * MODDA chegarasida ajratilishi kerak. Bu modul matndan modda sarlavhalarini
 * topib, har bir moddani alohida bo'lak qiladi; juda uzun moddalar esa
 * qism/band chegarasida bo'linadi.
 */

import { detectScript, foldForSearch } from "../uz/orthography";
import { detectLang } from "../uz/detect";
import type { CorpusChunk } from "../types";

/** Bitta bo'lakning maksimal uzunligi (belgilarda). */
const MAX_CHARS = 4000;
/** Bo'lish kerak bo'lganda minimal bo'lak uzunligi. */
const MIN_CHARS = 400;

/**
 * Modda sarlavhasini topadigan naqshlar.
 * Qo'llab-quvvatlanadi: "173-modda.", "173-modda", "Статья 173.", "Article 173."
 * Sarlavha satr boshida turishi shart.
 */
const ARTICLE_PATTERNS: RegExp[] = [
  // 173-modda. Sarlavha
  /^\s*(\d+(?:[¹²³⁴-]\d*)?)\s*-\s*modda\s*[.．:]?\s*(.*)$/i,
  // Модда 173 / 173-модда
  /^\s*(\d+(?:[¹²³⁴-]\d*)?)\s*-\s*модда\s*[.．:]?\s*(.*)$/i,
  // Статья 173. Заголовок
  /^\s*статья\s+(\d+(?:[¹²³⁴.-]\d*)?)\s*[.．:]?\s*(.*)$/i,
  // Article 173. Heading
  /^\s*article\s+(\d+(?:[¹²³⁴.-]\d*)?)\s*[.．:]?\s*(.*)$/i,
];

interface ArticleMatch {
  article: string;
  heading: string;
}

function matchArticle(line: string): ArticleMatch | null {
  for (const re of ARTICLE_PATTERNS) {
    const m = re.exec(line);
    if (m && m[1]) {
      return { article: m[1], heading: (m[2] ?? "").trim() };
    }
  }
  return null;
}

export interface ChunkOptions {
  /** Hujjat nomi: "Mehnat kodeksi". */
  document: string;
  /** Manba havolasi. */
  url?: string;
  /** Tahrir sanasi. */
  version?: string;
}

/**
 * Qonun matnini modda chegarasida bo'laklarga ajratadi.
 * Modda topilmasa — paragraflar bo'yicha bo'ladi.
 */
export function chunkLegalText(text: string, opts: ChunkOptions): CorpusChunk[] {
  const normalized = text.replace(/\r\n?/g, "\n").replace(/ /g, " ");
  const lines = normalized.split("\n");

  interface Section {
    article?: string;
    heading?: string;
    lines: string[];
  }

  const sections: Section[] = [];
  let current: Section = { lines: [] };

  for (const line of lines) {
    const hit = matchArticle(line);
    if (hit) {
      // Oldingi bo'limni yopamiz (bo'sh bo'lmasa).
      if (current.lines.join("").trim() || current.article) {
        sections.push(current);
      }
      current = {
        article: hit.article,
        heading: hit.heading || undefined,
        lines: hit.heading ? [] : [],
      };
    } else {
      current.lines.push(line);
    }
  }
  if (current.lines.join("").trim() || current.article) sections.push(current);

  // Modda umuman topilmasa — paragraflar bo'yicha.
  const hasArticles = sections.some((s) => s.article);
  if (!hasArticles) {
    return chunkByParagraph(normalized, opts);
  }

  const chunks: CorpusChunk[] = [];
  for (const section of sections) {
    const body = section.lines.join("\n").trim();
    if (!body && !section.heading) continue;

    const full = [
      section.article ? `${section.article}-modda.` : "",
      section.heading ?? "",
      body,
    ]
      .filter(Boolean)
      .join(" ")
      .trim();

    if (full.length <= MAX_CHARS) {
      chunks.push(makeChunk(full, opts, section.article, section.heading, chunks.length));
      continue;
    }

    // Uzun modda — qism/band chegarasida bo'lamiz.
    for (const [i, part] of splitLongArticle(body).entries()) {
      const header = [
        section.article ? `${section.article}-modda.` : "",
        section.heading ?? "",
      ]
        .filter(Boolean)
        .join(" ");
      const piece = `${header} (${i + 1}-qism)\n${part}`.trim();
      chunks.push(
        makeChunk(piece, opts, section.article, section.heading, chunks.length),
      );
    }
  }

  return chunks.filter((c) => c.text.trim().length >= 20);
}

/** Uzun moddani band/qism chegarasida bo'lish. */
function splitLongArticle(body: string): string[] {
  // Band belgilari: "1)", "1.", "а)" (kirill) yoki "a)" (lotin) ...
  // lint-uz-ignore: regex belgilar sinfida kirill va lotin diapazonlari ataylab yonma-yon
  const paragraphs = body.split(/\n(?=\s*(?:\d+[).]|[а-яa-z][)]|—|-)\s)/u);
  const out: string[] = [];
  let buf = "";

  for (const p of paragraphs) {
    if (buf.length + p.length > MAX_CHARS && buf.length >= MIN_CHARS) {
      out.push(buf.trim());
      buf = p;
    } else {
      buf += (buf ? "\n" : "") + p;
    }
  }
  if (buf.trim()) out.push(buf.trim());

  // Hali ham juda uzun bo'lsa — qattiq kesamiz.
  return out.flatMap((s) =>
    s.length <= MAX_CHARS ? [s] : hardSplit(s, MAX_CHARS),
  );
}

function hardSplit(s: string, size: number): string[] {
  const out: string[] = [];
  for (let i = 0; i < s.length; i += size) out.push(s.slice(i, i + size));
  return out;
}

/** Modda topilmaganda — paragraflar bo'yicha bo'lish. */
function chunkByParagraph(text: string, opts: ChunkOptions): CorpusChunk[] {
  const paragraphs = text.split(/\n{2,}/);
  const chunks: CorpusChunk[] = [];
  let buf = "";

  const flush = () => {
    if (buf.trim().length >= 20) {
      chunks.push(makeChunk(buf.trim(), opts, undefined, undefined, chunks.length));
    }
    buf = "";
  };

  for (const p of paragraphs) {
    if (buf.length + p.length > MAX_CHARS && buf.length >= MIN_CHARS) flush();
    buf += (buf ? "\n\n" : "") + p;
  }
  flush();
  return chunks;
}

function makeChunk(
  text: string,
  opts: ChunkOptions,
  article: string | undefined,
  heading: string | undefined,
  index: number,
): CorpusChunk {
  const script = detectScript(text);
  const { lang } = detectLang(text, { lang: "uz", script });
  return {
    id: chunkId(opts.document, article, index),
    document: opts.document,
    article,
    heading,
    text: text.trim(),
    url: opts.url,
    version: opts.version,
    lang,
    script,
  };
}

function chunkId(document: string, article: string | undefined, index: number): string {
  const slug = foldForSearch(document)
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return article ? `${slug}#${article}-${index}` : `${slug}#p${index}`;
}
