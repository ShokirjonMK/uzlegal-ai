/**
 * Kolleksiyalar, ularning tiplari va indekslari.
 *
 * SAQLASH SIYOSATI. `ai_calls` va `messages` da savol va javob matni TO'LIQ
 * saqlanadi va avtomatik o'chirilmaydi — bu foydalanuvchi tomonidan ataylab
 * tanlangan qaror (docs/TASKS.md, #65). Shu sababli bu ikki kolleksiyada TTL
 * indeksi YO'Q. TTL faqat sessiya va kirish kodlarida — ular xavfsizlik
 * uchun muddatli bo'lishi shart.
 */

import type { Collection, Db, ObjectId } from "mongodb";
import { getDb } from "./mongo";
import type { EventKind, Surface } from "../analytics";

export interface UserDoc {
  _id: ObjectId;
  /** Telegram chat ID — bot va web yuzalarini bir shaxsga bog'laydi. */
  telegramId?: number;
  username?: string;
  firstName?: string;
  email?: string;
  /** scrypt xeshi. Parol hech qachon ochiq saqlanmaydi. */
  passwordHash?: string;
  passwordSalt?: string;
  roles: string[];
  surfaces: Surface[];
  createdAt: Date;
  lastSeenAt: Date;
  requests: number;
  blocked?: boolean;
}

export interface SessionDoc {
  /** Token xeshi (SHA-256). Tokenning o'zi faqat cookie'da bo'ladi. */
  _id: string;
  userId: ObjectId | null;
  kind: "web" | "admin";
  createdAt: Date;
  expiresAt: Date;
  ip?: string;
  userAgent?: string;
}

export interface LoginCodeDoc {
  /** Urinish identifikatori — mijozga shu qaytariladi, kodning o'zi emas. */
  _id: string;
  kind: "admin" | "user";
  telegramId?: number;
  email?: string;
  codeHash: string;
  createdAt: Date;
  expiresAt: Date;
  tries: number;
}

export interface ConversationDoc {
  _id: ObjectId;
  userId: ObjectId | null;
  /** Kirmagan mehmon uchun brauzer identifikatori. */
  anonId?: string;
  surface: Surface;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  messageCount: number;
}

export interface MessageDoc {
  _id: ObjectId;
  conversationId: ObjectId;
  userId: ObjectId | null;
  role: "user" | "assistant";
  /** To'liq matn. Qisqartirilmaydi. */
  content: string;
  citations?: unknown[];
  createdAt: Date;
}

/** Modelga qilingan har bir murojaatning to'liq yozuvi. */
export interface AiCallDoc {
  _id: ObjectId;
  kind: EventKind;
  surface: Surface;
  userId: ObjectId | null;
  telegramId?: number;
  anonId?: string;
  /** Qaysi xizmat javob berdi: `anthropic` yoki `ollama`. */
  provider?: string;
  model: string;
  effort?: string;
  /** Tizim prompti — qaysi ko'rsatma bilan javob olingani. */
  systemPrompt?: string;
  /** Foydalanuvchi kiritgan matn, to'liq. */
  input: string;
  /** Model qaytargan matn, to'liq. */
  output: string;
  citations?: unknown[];
  inputTokens?: number;
  outputTokens?: number;
  durationMs?: number;
  error?: string;
  label?: string;
  createdAt: Date;
}

export interface EventDoc {
  _id: ObjectId;
  kind: EventKind;
  surface: Surface;
  userId: ObjectId | null;
  /**
   * Yuza identifikatori — Telegram chat ID yoki web sessiya kaliti.
   *
   * `userId` (Mongo hisobi) dan ALOHIDA saqlanadi: bot foydalanuvchisi
   * roʻyxatdan oʻtmagan boʻlishi mumkin, lekin uning faoliyati baribir
   * hisobga olinishi kerak.
   */
  actorId?: string;
  username?: string;
  telegramId?: number;
  /** Kiruvchi matn UZUNLIGI. Matnning oʻzi hech qachon saqlanmaydi. */
  inputChars?: number;
  inputTokens?: number;
  outputTokens?: number;
  durationMs?: number;
  error?: string;
  label?: string;
  createdAt: Date;
}

/**
 * Yuza ishtirokchisi — Telegram chat yoki web sessiyasi.
 *
 * NEGA `users` DAN ALOHIDA. `users` — roʻyxatdan oʻtgan hisob (parol,
 * email, rollar). Bot foydalanuvchisi esa hech qachon roʻyxatdan
 * oʻtmasligi mumkin, lekin uning birinchi murojaati va faolligi
 * hisobga olinishi kerak. Ikkalasini bitta kolleksiyaga qoʻshish
 * «foydalanuvchi» tushunchasini ikki xil maʼnoda ishlatardi.
 */
export interface ActorDoc {
  /** `${surface}:${actorId}` — yuzalar boʻyicha takrorlanmas kalit. */
  _id: string;
  actorId: string;
  surface: Surface;
  username?: string;
  firstSeenAt: Date;
  lastSeenAt: Date;
  requests: number;
}

export const NAMES = {
  users: "users",
  actors: "actors",
  sessions: "sessions",
  loginCodes: "login_codes",
  conversations: "conversations",
  messages: "messages",
  aiCalls: "ai_calls",
  events: "events",
} as const;

export async function users(): Promise<Collection<UserDoc>> {
  return (await db()).collection<UserDoc>(NAMES.users);
}
export async function actors(): Promise<Collection<ActorDoc>> {
  return (await db()).collection<ActorDoc>(NAMES.actors);
}
export async function sessions(): Promise<Collection<SessionDoc>> {
  return (await db()).collection<SessionDoc>(NAMES.sessions);
}
export async function loginCodes(): Promise<Collection<LoginCodeDoc>> {
  return (await db()).collection<LoginCodeDoc>(NAMES.loginCodes);
}
export async function conversations(): Promise<Collection<ConversationDoc>> {
  return (await db()).collection<ConversationDoc>(NAMES.conversations);
}
export async function messages(): Promise<Collection<MessageDoc>> {
  return (await db()).collection<MessageDoc>(NAMES.messages);
}
export async function aiCalls(): Promise<Collection<AiCallDoc>> {
  return (await db()).collection<AiCallDoc>(NAMES.aiCalls);
}
export async function events(): Promise<Collection<EventDoc>> {
  return (await db()).collection<EventDoc>(NAMES.events);
}

let indexesReady: Promise<void> | null = null;

async function db(): Promise<Db> {
  const database = await getDb();
  // Indekslar bir marta, birinchi murojaatda quriladi.
  indexesReady ??= ensureIndexes(database).catch((err: unknown) => {
    indexesReady = null;
    console.error("[mongo] indekslarni qurib boʻlmadi:", err);
  });
  await indexesReady;
  return database;
}

async function ensureIndexes(database: Db): Promise<void> {
  await Promise.all([
    database
      .collection<UserDoc>(NAMES.users)
      .createIndexes([
        { key: { telegramId: 1 }, unique: true, sparse: true },
        { key: { email: 1 }, unique: true, sparse: true },
        { key: { lastSeenAt: -1 } },
      ]),

    // TTL: muddati o'tgan sessiya o'zi o'chadi.
    database
      .collection<SessionDoc>(NAMES.sessions)
      .createIndexes([
        { key: { expiresAt: 1 }, expireAfterSeconds: 0 },
        { key: { userId: 1 } },
      ]),

    database
      .collection<LoginCodeDoc>(NAMES.loginCodes)
      .createIndexes([{ key: { expiresAt: 1 }, expireAfterSeconds: 0 }]),

    database
      .collection<ConversationDoc>(NAMES.conversations)
      .createIndexes([
        { key: { userId: 1, updatedAt: -1 } },
        { key: { anonId: 1, updatedAt: -1 } },
      ]),

    database
      .collection<MessageDoc>(NAMES.messages)
      .createIndexes([{ key: { conversationId: 1, createdAt: 1 } }]),

    // TTL YO'Q — yozishmalar muddatsiz saqlanadi.
    database
      .collection<AiCallDoc>(NAMES.aiCalls)
      .createIndexes([
        { key: { createdAt: -1 } },
        { key: { userId: 1, createdAt: -1 } },
        { key: { kind: 1, createdAt: -1 } },
      ]),

    database
      .collection<EventDoc>(NAMES.events)
      .createIndexes([
        { key: { createdAt: -1 } },
        { key: { kind: 1, createdAt: -1 } },
        { key: { surface: 1, createdAt: -1 } },
        { key: { actorId: 1, createdAt: -1 } },
      ]),

    database
      .collection<ActorDoc>(NAMES.actors)
      .createIndexes([
        { key: { surface: 1 } },
        { key: { firstSeenAt: -1 } },
        { key: { lastSeenAt: -1 } },
      ]),
  ]);
}
