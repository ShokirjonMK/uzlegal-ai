/**
 * Qonun matnlarini bazaga yuklash quvuri:
 * fayl → matn → bo'laklar → vektorlar → SQLite.
 */

import { readdir, readFile, stat } from "node:fs/promises";
import { basename, extname, join, resolve } from "node:path";
import { config } from "../config";
import { chunkLegalText } from "./chunk";
import { getEmbedder } from "./embeddings";
import { deleteDocument, setMeta, upsertChunks } from "./store";
import { extractText, isSupported } from "../util/extract";
import type { CorpusChunk } from "../types";

export interface IngestProgress {
  file: string;
  document: string;
  chunks: number;
}

export interface IngestOptions {
  /** Har bir fayl uchun chaqiriladi. */
  onProgress?: (p: IngestProgress) => void;
  /** Faylni yuklashdan oldin shu hujjatning eski bo'laklarini o'chirish. */
  replace?: boolean;
}

/**
 * Fayl nomidan hujjat nomini va manba havolasini ajratadi.
 *
 * Qo'llab-quvvatlanadigan nom shakli:
 *   `Mehnat kodeksi.txt`
 *   `Mehnat kodeksi__https---lex.uz-docs-142859.txt`  (havola bilan)
 *   `Mehnat kodeksi__2024-01-15.txt`                   (tahrir sanasi bilan)
 */
function parseFilename(filename: string): {
  document: string;
  url?: string;
  version?: string;
} {
  const stem = basename(filename, extname(filename));
  const [namePart, ...rest] = stem.split("__");
  const document = (namePart ?? stem).trim();

  let url: string | undefined;
  let version: string | undefined;

  for (const part of rest) {
    const p = part.trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(p)) {
      version = p;
    } else if (p) {
      // Fayl nomida `/` bo'lolmaydi — `-` bilan yozilgan bo'lishi mumkin.
      url = p.startsWith("http") ? p : p.replace(/^https---/, "https://").replace(/^http---/, "http://");
    }
  }

  return { document, url, version };
}

/** Bitta faylni bazaga yuklaydi. */
export async function ingestFile(
  path: string,
  opts: IngestOptions = {},
): Promise<IngestProgress> {
  const filename = basename(path);
  const buffer = await readFile(path);
  const text = await extractText(buffer, filename);

  const { document, url, version } = parseFilename(filename);

  if (opts.replace) deleteDocument(document);

  const chunks = chunkLegalText(text, { document, url, version });
  if (chunks.length === 0) {
    return { file: filename, document, chunks: 0 };
  }

  const embedder = getEmbedder();
  const vectors = await embedder.embedDocuments(chunks.map((c) => embedInput(c)));

  const withVectors = chunks.map((c, i) => ({
    ...c,
    embedding: vectors[i]!,
  }));

  upsertChunks(withVectors);
  setMeta("embedder", embedder.name);
  if (vectors[0]) setMeta("dim", String(vectors[0].length));

  const result = { file: filename, document, chunks: chunks.length };
  opts.onProgress?.(result);
  return result;
}

/**
 * Vektorlashtirish uchun matn: sarlavha ham qo'shiladi, chunki
 * "Mehnat kodeksi · 173-modda · Ishdan boʻshatish asoslari" kontekstsiz
 * modda matnidan ko'ra ko'proq ma'no beradi.
 */
function embedInput(c: CorpusChunk): string {
  return [c.document, c.article ? `${c.article}-modda` : "", c.heading, c.text]
    .filter(Boolean)
    .join(" · ");
}

export interface IngestSummary {
  files: number;
  chunks: number;
  skipped: string[];
  documents: string[];
}

/** Papkadagi barcha mos fayllarni yuklaydi (ichma-ich papkalar ham). */
export async function ingestDirectory(
  dir: string = config.corpusDir,
  opts: IngestOptions = {},
): Promise<IngestSummary> {
  const root = resolve(dir);
  const files = await walk(root);

  const summary: IngestSummary = {
    files: 0,
    chunks: 0,
    skipped: [],
    documents: [],
  };

  for (const path of files) {
    if (!isSupported(path)) {
      summary.skipped.push(basename(path));
      continue;
    }
    const res = await ingestFile(path, opts);
    summary.files += 1;
    summary.chunks += res.chunks;
    if (!summary.documents.includes(res.document)) {
      summary.documents.push(res.document);
    }
  }

  return summary;
}

async function walk(dir: string): Promise<string[]> {
  let entries: string[];
  try {
    entries = await readdir(dir);
  } catch {
    throw new Error(
      `Korpus papkasi topilmadi: ${dir}\n` +
        `Qonun matnlarini shu papkaga joylang yoki CORPUS_DIR ni oʻzgartiring.`,
    );
  }

  const out: string[] = [];
  for (const entry of entries.sort()) {
    if (entry.startsWith(".")) continue;
    const full = join(dir, entry);
    const info = await stat(full);
    if (info.isDirectory()) {
      out.push(...(await walk(full)));
    } else if (info.isFile()) {
      out.push(full);
    }
  }
  return out;
}
