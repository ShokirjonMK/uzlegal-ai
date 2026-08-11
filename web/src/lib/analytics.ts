/**
 * Foydalanish statistikasi.
 *
 * Har bir amal SQLite ga yoziladi (korpus bazasidan alohida fayl), keyin
 * admin `/stat` buyrug'i yoki kunlik hisobot orqali ko'ra oladi.
 *
 * Maxfiylik: savol MATNI saqlanmaydi — faqat uzunligi va turi. Foydalanuvchi
 * identifikatori Telegram chat ID va username bilan cheklangan.
 */

import { DatabaseSync } from "node:sqlite";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { config } from "./config";

export type EventKind =
  | "ask"
  | "analyze"
  | "review"
  | "generate"
  | "search"
  | "start"
  | "error";

export type Surface = "telegram" | "web" | "api" | "cli";

export interface EventInput {
  kind: EventKind;
  surface: Surface;
  /** Telegram chat ID yoki web sessiya identifikatori. */
  userId?: string;
  username?: string;
  /** Kiruvchi matn uzunligi (matnning o'zi emas). */
  inputChars?: number;
  inputTokens?: number;
  outputTokens?: number;
  /** Amal davomiyligi, millisekundda. */
  durationMs?: number;
  /** Xatolik bo'lsa — qisqa tavsif. */
  error?: string;
  /** Qo'shimcha belgi: hujjat turi, fayl kengaytmasi va h.k. */
  label?: string;
}

const SCHEMA = `
CREATE TABLE IF NOT EXISTS events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  ts            INTEGER NOT NULL,
  kind          TEXT NOT NULL,
  surface       TEXT NOT NULL,
  user_id       TEXT,
  username      TEXT,
  input_chars   INTEGER,
  input_tokens  INTEGER,
  output_tokens INTEGER,
  duration_ms   INTEGER,
  error         TEXT,
  label         TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id);

CREATE TABLE IF NOT EXISTS users (
  user_id   TEXT PRIMARY KEY,
  username  TEXT,
  surface   TEXT NOT NULL,
  first_ts  INTEGER NOT NULL,
  last_ts   INTEGER NOT NULL,
  requests  INTEGER NOT NULL DEFAULT 0
);
`;

let db: DatabaseSync | null = null;

function open(): DatabaseSync {
  if (db) return db;
  const path = resolve(config.corpusDbPath).replace(/\.db$/, "") + ".analytics.db";
  mkdirSync(dirname(path), { recursive: true });
  db = new DatabaseSync(path);
  db.exec("PRAGMA journal_mode = WAL;");
  db.exec(SCHEMA);
  return db;
}

export function closeAnalytics(): void {
  db?.close();
  db = null;
}

/** Yangi foydalanuvchi bo'lsa `true` qaytaradi. */
export function record(e: EventInput): { isNewUser: boolean } {
  let isNewUser = false;
  try {
    const database = open();
    const now = Date.now();

    database
      .prepare(
        `INSERT INTO events
         (ts, kind, surface, user_id, username, input_chars, input_tokens, output_tokens, duration_ms, error, label)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
      .run(
        now,
        e.kind,
        e.surface,
        e.userId ?? null,
        e.username ?? null,
        e.inputChars ?? null,
        e.inputTokens ?? null,
        e.outputTokens ?? null,
        e.durationMs ?? null,
        e.error ?? null,
        e.label ?? null,
      );

    if (e.userId) {
      const existing = database
        .prepare("SELECT user_id FROM users WHERE user_id = ?")
        .get(e.userId);
      isNewUser = !existing;

      database
        .prepare(
          `INSERT INTO users (user_id, username, surface, first_ts, last_ts, requests)
           VALUES (?, ?, ?, ?, ?, 1)
           ON CONFLICT(user_id) DO UPDATE SET
             username = COALESCE(excluded.username, users.username),
             last_ts  = excluded.last_ts,
             requests = users.requests + 1`,
        )
        .run(e.userId, e.username ?? null, e.surface, now, now);
    }
  } catch (err) {
    // Statistika hech qachon asosiy ishni to'xtatmasligi kerak.
    console.error("[analytics] yozib boʻlmadi:", err);
  }
  return { isNewUser };
}

export interface Summary {
  since: number;
  totalEvents: number;
  byKind: Array<{ kind: string; n: number }>;
  bySurface: Array<{ surface: string; n: number }>;
  uniqueUsers: number;
  newUsers: number;
  errors: number;
  inputTokens: number;
  outputTokens: number;
  avgDurationMs: number;
  topUsers: Array<{ userId: string; username: string | null; n: number }>;
  recentErrors: Array<{ ts: number; kind: string; error: string }>;
}

/** Oxirgi `hours` soat uchun statistika. */
export function summary(hours = 24): Summary {
  const database = open();
  const since = Date.now() - hours * 3600_000;

  const one = <T>(sql: string, ...params: unknown[]): T =>
    database.prepare(sql).get(...(params as never[])) as T;
  const many = <T>(sql: string, ...params: unknown[]): T[] =>
    database.prepare(sql).all(...(params as never[])) as unknown as T[];

  const total = one<{ n: number }>(
    "SELECT COUNT(*) AS n FROM events WHERE ts >= ?",
    since,
  );
  const tokens = one<{ i: number | null; o: number | null; d: number | null }>(
    `SELECT SUM(input_tokens) AS i, SUM(output_tokens) AS o, AVG(duration_ms) AS d
     FROM events WHERE ts >= ?`,
    since,
  );
  const users = one<{ n: number }>(
    "SELECT COUNT(DISTINCT user_id) AS n FROM events WHERE ts >= ? AND user_id IS NOT NULL",
    since,
  );
  const fresh = one<{ n: number }>(
    "SELECT COUNT(*) AS n FROM users WHERE first_ts >= ?",
    since,
  );
  const errors = one<{ n: number }>(
    "SELECT COUNT(*) AS n FROM events WHERE ts >= ? AND error IS NOT NULL",
    since,
  );

  return {
    since,
    totalEvents: Number(total.n),
    byKind: many<{ kind: string; n: number }>(
      "SELECT kind, COUNT(*) AS n FROM events WHERE ts >= ? GROUP BY kind ORDER BY n DESC",
      since,
    ).map((r) => ({ kind: r.kind, n: Number(r.n) })),
    bySurface: many<{ surface: string; n: number }>(
      "SELECT surface, COUNT(*) AS n FROM events WHERE ts >= ? GROUP BY surface ORDER BY n DESC",
      since,
    ).map((r) => ({ surface: r.surface, n: Number(r.n) })),
    uniqueUsers: Number(users.n),
    newUsers: Number(fresh.n),
    errors: Number(errors.n),
    inputTokens: Number(tokens.i ?? 0),
    outputTokens: Number(tokens.o ?? 0),
    avgDurationMs: Math.round(Number(tokens.d ?? 0)),
    topUsers: many<{ user_id: string; username: string | null; n: number }>(
      `SELECT user_id, username, COUNT(*) AS n FROM events
       WHERE ts >= ? AND user_id IS NOT NULL
       GROUP BY user_id ORDER BY n DESC LIMIT 10`,
      since,
    ).map((r) => ({ userId: r.user_id, username: r.username, n: Number(r.n) })),
    recentErrors: many<{ ts: number; kind: string; error: string }>(
      `SELECT ts, kind, error FROM events
       WHERE ts >= ? AND error IS NOT NULL ORDER BY ts DESC LIMIT 5`,
      since,
    ).map((r) => ({ ts: Number(r.ts), kind: r.kind, error: r.error })),
  };
}

/** Umumiy (butun davr) ko'rsatkichlar. */
export function lifetime(): { users: number; events: number; firstTs: number | null } {
  const database = open();
  const u = database.prepare("SELECT COUNT(*) AS n FROM users").get() as { n: number };
  const e = database.prepare("SELECT COUNT(*) AS n FROM events").get() as { n: number };
  const f = database.prepare("SELECT MIN(ts) AS t FROM events").get() as {
    t: number | null;
  };
  return {
    users: Number(u.n),
    events: Number(e.n),
    firstTs: f.t !== null ? Number(f.t) : null,
  };
}

/** Ro'yxatdagi barcha foydalanuvchi ID'lari (ommaviy xabar yuborish uchun). */
export function allUserIds(surface?: string): string[] {
  const database = open();
  const rows = (
    surface
      ? database.prepare("SELECT user_id FROM users WHERE surface = ?").all(surface)
      : database.prepare("SELECT user_id FROM users").all()
  ) as unknown as Array<{ user_id: string }>;
  return rows.map((r) => r.user_id);
}

/** Statistikani o'zbekcha matn ko'rinishida formatlaydi. */
export function formatSummary(s: Summary, hours: number): string {
  const life = lifetime();
  const dur = s.avgDurationMs > 0 ? `${(s.avgDurationMs / 1000).toFixed(1)} s` : "—";

  const lines = [
    `📊 Statistika — oxirgi ${hours} soat`,
    "",
    `Soʻrovlar      : ${s.totalEvents}`,
    `Foydalanuvchi  : ${s.uniqueUsers} (yangi: ${s.newUsers})`,
    `Xatoliklar     : ${s.errors}`,
    `Oʻrtacha vaqt  : ${dur}`,
    `Tokenlar       : ${fmt(s.inputTokens)} kirish / ${fmt(s.outputTokens)} chiqish`,
    "",
  ];

  if (s.byKind.length) {
    lines.push("Amal turlari:");
    for (const k of s.byKind) lines.push(`  ${label(k.kind)} — ${k.n}`);
    lines.push("");
  }

  if (s.bySurface.length) {
    lines.push("Kanallar:");
    for (const k of s.bySurface) lines.push(`  ${k.surface} — ${k.n}`);
    lines.push("");
  }

  if (s.topUsers.length) {
    lines.push("Faol foydalanuvchilar:");
    for (const u of s.topUsers.slice(0, 5)) {
      lines.push(`  ${u.username ? `@${u.username}` : u.userId} — ${u.n}`);
    }
    lines.push("");
  }

  if (s.recentErrors.length) {
    lines.push("Oxirgi xatoliklar:");
    for (const e of s.recentErrors) {
      lines.push(`  ${new Date(e.ts).toLocaleString("uz-UZ")} · ${e.kind}`);
      lines.push(`    ${e.error.slice(0, 120)}`);
    }
    lines.push("");
  }

  lines.push(
    `Umumiy: ${life.users} foydalanuvchi, ${life.events} soʻrov` +
      (life.firstTs
        ? ` (${new Date(life.firstTs).toLocaleDateString("uz-UZ")} dan beri)`
        : ""),
  );

  return lines.join("\n");
}

function fmt(n: number): string {
  return n.toLocaleString("uz-UZ").replace(/,/g, " ");
}

function label(kind: string): string {
  const names: Record<string, string> = {
    ask: "savol-javob",
    analyze: "hujjat tahlili",
    review: "tekshiruv",
    generate: "hujjat yaratish",
    search: "qidiruv",
    start: "botga kirish",
    error: "xatolik",
  };
  return names[kind] ?? kind;
}
