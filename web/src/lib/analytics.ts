/**
 * Foydalanish statistikasi — MongoDB da.
 *
 * ## Nima uchun SQLite dan koʻchirildi
 *
 * Ilgari statistika **ikki joyda** yashardi: bot va CLI SQLite ga
 * yozardi, web va kabinet esa Mongo ga. Natijada admin paneli
 * `/api/admin/xabar` da ikkala manbani qoʻlda birlashtirishga majbur
 * edi va sonlar hech qachon toʻliq mos kelmasdi.
 *
 * Ikkita haqiqat manbai — bitta ham yoʻqdan yomonroq: qaysi biri
 * toʻgʻri ekanini aytib boʻlmaydi.
 *
 * ## Maxfiylik — oʻzgarmadi
 *
 * Savol MATNI hech qachon saqlanmaydi — faqat uzunligi, turi va
 * davomiyligi. Bu ataylab qilingan qaror va koʻchirishda ham
 * saqlandi.
 *
 * ## Mongo sozlanmagan boʻlsa
 *
 * Barcha funksiyalar **jimgina boʻsh natija** qaytaradi va asosiy ish
 * toʻxtamaydi. Statistika yordamchi vazifa: uning yoʻqligi savol-javobni
 * buzmasligi kerak. Ogohlantirish bir marta yoziladi.
 */

import { isMongoConfigured } from "./db/mongo";
import type { ActorDoc, EventDoc } from "./db/collections";

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
  /** Kiruvchi matn uzunligi (matnning oʻzi emas). */
  inputChars?: number;
  inputTokens?: number;
  outputTokens?: number;
  /** Amal davomiyligi, millisekundda. */
  durationMs?: number;
  /** Xatolik boʻlsa — qisqa tavsif. */
  error?: string;
  /** Qoʻshimcha belgi: hujjat turi, fayl kengaytmasi va h.k. */
  label?: string;
}

let warned = false;

function unavailable(): boolean {
  if (isMongoConfigured()) return false;
  if (!warned) {
    warned = true;
    console.warn(
      "[analytics] MONGODB_URI sozlanmagan — statistika yozilmaydi. " +
        "Asosiy ish davom etadi.",
    );
  }
  return true;
}

// ── Yozish ─────────────────────────────────────────────────────────────────

/** Amalni qayd etadi. Yangi ishtirokchi boʻlsa `isNewUser: true`. */
export async function record(e: EventInput): Promise<{ isNewUser: boolean }> {
  if (unavailable()) return { isNewUser: false };

  try {
    const { events, actors } = await import("./db/collections");
    const now = new Date();

    const [eventsColl, actorsColl] = await Promise.all([events(), actors()]);

    // Hodisa har doim yoziladi — ishtirokchi nomaʼlum boʻlsa ham.
    await eventsColl.insertOne({
      kind: e.kind,
      surface: e.surface,
      userId: null,
      actorId: e.userId,
      username: e.username,
      telegramId: e.surface === "telegram" ? Number(e.userId) || undefined : undefined,
      inputChars: e.inputChars,
      inputTokens: e.inputTokens,
      outputTokens: e.outputTokens,
      durationMs: e.durationMs,
      error: e.error,
      label: e.label,
      createdAt: now,
    } as EventDoc);

    if (!e.userId) return { isNewUser: false };

    // `upsert` bitta amalda: yangi boʻlsa yaratadi, boʻlmasa yangilaydi.
    // `upsertedCount` — yangi ishtirokchi belgisi. Alohida `findOne`
    // qilinsa ikki soʻrov orasida poyga paydo boʻlardi.
    const result = await actorsColl.updateOne(
      { _id: `${e.surface}:${e.userId}` },
      {
        $set: { lastSeenAt: now, ...(e.username ? { username: e.username } : {}) },
        $inc: { requests: 1 },
        $setOnInsert: {
          actorId: e.userId,
          surface: e.surface,
          firstSeenAt: now,
        },
      },
      { upsert: true },
    );

    return { isNewUser: result.upsertedCount > 0 };
  } catch (err) {
    // Statistika hech qachon asosiy ishni toʻxtatmasligi kerak.
    console.error("[analytics] yozib boʻlmadi:", err);
    return { isNewUser: false };
  }
}

// ── Oʻqish ─────────────────────────────────────────────────────────────────

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

function emptySummary(since: number): Summary {
  return {
    since,
    totalEvents: 0,
    byKind: [],
    bySurface: [],
    uniqueUsers: 0,
    newUsers: 0,
    errors: 0,
    inputTokens: 0,
    outputTokens: 0,
    avgDurationMs: 0,
    topUsers: [],
    recentErrors: [],
  };
}

/** Oxirgi `hours` soat uchun statistika. */
export async function summary(hours = 24): Promise<Summary> {
  const since = Date.now() - hours * 3600_000;
  if (unavailable()) return emptySummary(since);

  try {
    const { events, actors } = await import("./db/collections");
    const [eventsColl, actorsColl] = await Promise.all([events(), actors()]);
    const from = new Date(since);
    const window = { createdAt: { $gte: from } };

    // Barcha agregatsiyalar parallel — ular bir-biriga bogʻliq emas va
    // ketma-ket bajarilsa admin paneli sezilarli sekinlashardi.
    const [totals, byKind, bySurface, uniq, fresh, top, recent] = await Promise.all([
      eventsColl
        .aggregate<{ n: number; i: number; o: number; d: number; errors: number }>([
          { $match: window },
          {
            $group: {
              _id: null,
              n: { $sum: 1 },
              i: { $sum: { $ifNull: ["$inputTokens", 0] } },
              o: { $sum: { $ifNull: ["$outputTokens", 0] } },
              d: { $avg: "$durationMs" },
              errors: { $sum: { $cond: [{ $ifNull: ["$error", false] }, 1, 0] } },
            },
          },
        ])
        .toArray(),

      eventsColl
        .aggregate<{ _id: string; n: number }>([
          { $match: window },
          { $group: { _id: "$kind", n: { $sum: 1 } } },
          { $sort: { n: -1 } },
        ])
        .toArray(),

      eventsColl
        .aggregate<{ _id: string; n: number }>([
          { $match: window },
          { $group: { _id: "$surface", n: { $sum: 1 } } },
          { $sort: { n: -1 } },
        ])
        .toArray(),

      eventsColl.distinct("actorId", { ...window, actorId: { $exists: true } }),

      actorsColl.countDocuments({ firstSeenAt: { $gte: from } }),

      eventsColl
        .aggregate<{ _id: string; username: string | null; n: number }>([
          { $match: { ...window, actorId: { $exists: true } } },
          {
            $group: {
              _id: "$actorId",
              username: { $last: "$username" },
              n: { $sum: 1 },
            },
          },
          { $sort: { n: -1 } },
          { $limit: 10 },
        ])
        .toArray(),

      eventsColl
        .find({ ...window, error: { $exists: true } })
        .sort({ createdAt: -1 })
        .limit(5)
        .toArray(),
    ]);

    const t = totals[0];
    return {
      since,
      totalEvents: t?.n ?? 0,
      byKind: byKind.map((r) => ({ kind: r._id, n: r.n })),
      bySurface: bySurface.map((r) => ({ surface: r._id, n: r.n })),
      uniqueUsers: uniq.filter(Boolean).length,
      newUsers: fresh,
      errors: t?.errors ?? 0,
      inputTokens: t?.i ?? 0,
      outputTokens: t?.o ?? 0,
      avgDurationMs: Math.round(t?.d ?? 0),
      topUsers: top.map((r) => ({ userId: r._id, username: r.username ?? null, n: r.n })),
      recentErrors: recent.map((r) => ({
        ts: r.createdAt.getTime(),
        kind: r.kind,
        error: r.error ?? "",
      })),
    };
  } catch (err) {
    console.error("[analytics] statistika oʻqilmadi:", err);
    return emptySummary(since);
  }
}

/** Umumiy (butun davr) koʻrsatkichlar. */
export async function lifetime(): Promise<{
  users: number;
  events: number;
  firstTs: number | null;
}> {
  if (unavailable()) return { users: 0, events: 0, firstTs: null };

  try {
    const { events, actors } = await import("./db/collections");
    const [eventsColl, actorsColl] = await Promise.all([events(), actors()]);

    const [userCount, eventCount, first] = await Promise.all([
      actorsColl.countDocuments({}),
      eventsColl.countDocuments({}),
      eventsColl.find({}).sort({ createdAt: 1 }).limit(1).toArray(),
    ]);

    return {
      users: userCount,
      events: eventCount,
      firstTs: first[0]?.createdAt.getTime() ?? null,
    };
  } catch (err) {
    console.error("[analytics] umumiy koʻrsatkich oʻqilmadi:", err);
    return { users: 0, events: 0, firstTs: null };
  }
}

/** Roʻyxatdagi barcha ishtirokchi ID lari (ommaviy xabar yuborish uchun). */
export async function allUserIds(surface?: Surface): Promise<string[]> {
  if (unavailable()) return [];

  try {
    const { actors } = await import("./db/collections");
    const coll = await actors();
    const docs = await coll.find(surface ? { surface } : {}).toArray();
    return docs.map((d) => d.actorId);
  } catch (err) {
    console.error("[analytics] ishtirokchilar oʻqilmadi:", err);
    return [];
  }
}

// ── Koʻrsatish ─────────────────────────────────────────────────────────────

const KIND_LABELS: Record<string, string> = {
  ask: "Savol-javob",
  analyze: "Hujjat tahlili",
  review: "Tekshiruv",
  generate: "Hujjat tayyorlash",
  search: "Qidiruv",
  start: "Boshlash",
  error: "Xatolik",
};

function label(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}

function fmt(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

/** Statistikani oʻzbekcha matn koʻrinishida formatlaydi. */
export async function formatSummary(s: Summary, hours: number): Promise<string> {
  const life = await lifetime();
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
    `Umumiy: ${life.users} foydalanuvchi · ${life.events} amal` +
      (life.firstTs ? ` · ${new Date(life.firstTs).toLocaleDateString("uz-UZ")} dan beri` : ""),
  );

  return lines.join("\n");
}

/** Test va toʻxtatish uchun — Mongo ulanishi `db/mongo` da yopiladi. */
export function closeAnalytics(): void {
  warned = false;
}

export type { ActorDoc };
