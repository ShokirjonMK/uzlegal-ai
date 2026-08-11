/**
 * Qonun bazasi uchun vektor do'kon.
 *
 * `node:sqlite` (Node 22.5+ tarkibida) ishlatiladi — tashqi baza o'rnatish
 * shart emas. Vektorlar BLOB sifatida saqlanadi, qidiruv xotirada bajariladi.
 * Bu 50 000 gacha bo'lakda yetarli tez ishlaydi; undan katta korpus uchun
 * PostgreSQL + pgvector ga o'tish tavsiya etiladi (interfeys o'zgarmaydi).
 */

import { DatabaseSync } from "node:sqlite";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { config } from "../config";
import { foldForSearch } from "../uz/orthography";
import type { CorpusChunk, Lang, Script } from "../types";

export interface StoredChunk extends CorpusChunk {
  embedding: Float32Array;
  /** Qidiruv uchun normallashtirilgan matn. */
  folded: string;
}

interface Row {
  id: string;
  document: string;
  article: string | null;
  heading: string | null;
  text: string;
  url: string | null;
  version: string | null;
  lang: string;
  script: string;
  folded: string;
  embedding: Uint8Array;
}

const SCHEMA = `
CREATE TABLE IF NOT EXISTS chunks (
  id        TEXT PRIMARY KEY,
  document  TEXT NOT NULL,
  article   TEXT,
  heading   TEXT,
  text      TEXT NOT NULL,
  url       TEXT,
  version   TEXT,
  lang      TEXT NOT NULL,
  script    TEXT NOT NULL,
  folded    TEXT NOT NULL,
  embedding BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document);

CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
`;

let db: DatabaseSync | null = null;
let memo: StoredChunk[] | null = null;

function open(): DatabaseSync {
  if (db) return db;
  const path = resolve(config.corpusDbPath);
  mkdirSync(dirname(path), { recursive: true });
  db = new DatabaseSync(path);
  db.exec("PRAGMA journal_mode = WAL;");
  db.exec(SCHEMA);
  return db;
}

/** Ochiq bazani yopadi (CLI va testlar uchun). */
export function closeStore(): void {
  db?.close();
  db = null;
  memo = null;
}

function toBlob(v: Float32Array): Uint8Array {
  return new Uint8Array(v.buffer.slice(v.byteOffset, v.byteOffset + v.byteLength));
}

function fromBlob(b: Uint8Array): Float32Array {
  // BLOB 4 baytga tekislanmagan bo'lishi mumkin — nusxa olamiz.
  const copy = new Uint8Array(b.length);
  copy.set(b);
  return new Float32Array(copy.buffer);
}

function rowToChunk(r: Row): StoredChunk {
  return {
    id: r.id,
    document: r.document,
    article: r.article ?? undefined,
    heading: r.heading ?? undefined,
    text: r.text,
    url: r.url ?? undefined,
    version: r.version ?? undefined,
    lang: r.lang as Lang,
    script: r.script as Script,
    folded: r.folded,
    embedding: fromBlob(r.embedding),
  };
}

// ── Yozish ─────────────────────────────────────────────────────────────────

/** Bo'laklarni bazaga yozadi (mavjud id ustiga yozib ketadi). */
export function upsertChunks(
  chunks: Array<CorpusChunk & { embedding: Float32Array }>,
): number {
  const database = open();
  const stmt = database.prepare(`
    INSERT INTO chunks (id, document, article, heading, text, url, version, lang, script, folded, embedding)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
      document=excluded.document, article=excluded.article, heading=excluded.heading,
      text=excluded.text, url=excluded.url, version=excluded.version,
      lang=excluded.lang, script=excluded.script,
      folded=excluded.folded, embedding=excluded.embedding
  `);

  database.exec("BEGIN");
  try {
    for (const c of chunks) {
      stmt.run(
        c.id,
        c.document,
        c.article ?? null,
        c.heading ?? null,
        c.text,
        c.url ?? null,
        c.version ?? null,
        c.lang,
        c.script,
        foldForSearch(`${c.document} ${c.heading ?? ""} ${c.text}`),
        toBlob(c.embedding),
      );
    }
    database.exec("COMMIT");
  } catch (err) {
    database.exec("ROLLBACK");
    throw err;
  }

  memo = null; // kesh eskirdi
  return chunks.length;
}

/** Bitta hujjatning barcha bo'laklarini o'chiradi (qayta yuklashdan oldin). */
export function deleteDocument(document: string): number {
  const database = open();
  const res = database.prepare("DELETE FROM chunks WHERE document = ?").run(document);
  memo = null;
  return Number(res.changes);
}

/** Butun bazani tozalaydi. */
export function clearStore(): void {
  const database = open();
  database.exec("DELETE FROM chunks");
  memo = null;
}

/** Meta-ma'lumot yozish (masalan, qaysi embedder ishlatilgani). */
export function setMeta(key: string, value: string): void {
  open()
    .prepare(
      "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
    )
    .run(key, value);
}

export function getMeta(key: string): string | undefined {
  const row = open().prepare("SELECT value FROM meta WHERE key = ?").get(key) as
    | { value: string }
    | undefined;
  return row?.value;
}

// ── O'qish ─────────────────────────────────────────────────────────────────

/** Barcha bo'laklarni xotiraga yuklaydi (bir marta, keyin keshdan). */
export function loadAll(): StoredChunk[] {
  if (memo) return memo;
  const rows = open().prepare("SELECT * FROM chunks").all() as unknown as Row[];
  memo = rows.map(rowToChunk);
  return memo;
}

export interface CorpusStats {
  chunks: number;
  documents: Array<{ document: string; chunks: number }>;
  embedder?: string;
  dim?: number;
}

/** Baza holati haqida ma'lumot. */
export function stats(): CorpusStats {
  const database = open();
  const total = database.prepare("SELECT COUNT(*) AS n FROM chunks").get() as {
    n: number;
  };
  const docs = database
    .prepare(
      "SELECT document, COUNT(*) AS n FROM chunks GROUP BY document ORDER BY n DESC",
    )
    .all() as unknown as Array<{ document: string; n: number }>;

  return {
    chunks: Number(total.n),
    documents: docs.map((d) => ({ document: d.document, chunks: Number(d.n) })),
    embedder: getMeta("embedder"),
    dim: getMeta("dim") ? Number(getMeta("dim")) : undefined,
  };
}

/** Baza bo'shmi? */
export function isEmpty(): boolean {
  return stats().chunks === 0;
}
