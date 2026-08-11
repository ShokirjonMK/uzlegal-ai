/**
 * Foydalanuvchi sessiyasi.
 *
 * Admin sessiyasidan farqli (u imzolangan cookie, bazasiz), oddiy foydalanuvchi
 * sessiyasi Mongo da saqlanadi. Sabab: foydalanuvchini chiqarib yuborish
 * (bloklash, «barcha qurilmalardan chiqish») kerak bo'ladi, buni imzolangan
 * cookie bilan qilib bo'lmaydi.
 *
 * Cookie'da tokenning O'ZI turadi, bazada esa faqat uning SHA-256 xeshi:
 * baza oqib ketsa ham tokenlar bilan kirib bo'lmaydi.
 */

import { createHash, randomBytes } from "node:crypto";
import { ObjectId } from "mongodb";
import { sessions, users, type UserDoc } from "../db/collections";
import { USER_COOKIE, readCookie } from "./cookie";

/** Sessiya muddati — 30 kun. */
const SESSION_DAYS = 30;

function hashToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

export interface CreatedSession {
  token: string;
  maxAgeSeconds: number;
}

export async function createSession(
  userId: ObjectId,
  request: Request,
): Promise<CreatedSession> {
  const token = randomBytes(32).toString("base64url");
  const maxAgeSeconds = SESSION_DAYS * 24 * 3600;

  const col = await sessions();
  await col.insertOne({
    _id: hashToken(token),
    userId,
    kind: "web",
    createdAt: new Date(),
    expiresAt: new Date(Date.now() + maxAgeSeconds * 1000),
    ip: clientIp(request),
    userAgent: request.headers.get("user-agent") ?? undefined,
  });

  return { token, maxAgeSeconds };
}

/** Cookie bo'yicha foydalanuvchini topadi. Topilmasa yoki bloklangan bo'lsa `null`. */
export async function currentUser(request: Request): Promise<UserDoc | null> {
  const token = readCookie(request, USER_COOKIE);
  return token ? userByToken(token) : null;
}

export async function userByToken(token: string): Promise<UserDoc | null> {
  try {
    const sessionCol = await sessions();
    const session = await sessionCol.findOne({ _id: hashToken(token) });
    if (!session || session.expiresAt < new Date()) return null;

    const userCol = await users();
    const user = await userCol.findOne({ _id: session.userId ?? undefined });
    if (!user || user.blocked) return null;

    return user;
  } catch {
    // Baza yetib bormasa — kirmagan deb hisoblanadi, sayt ishlashda davom etadi.
    return null;
  }
}

export async function destroySession(request: Request): Promise<void> {
  const token = readCookie(request, USER_COOKIE);
  if (!token) return;
  try {
    const col = await sessions();
    await col.deleteOne({ _id: hashToken(token) });
  } catch {
    // Cookie baribir o'chiriladi.
  }
}

/** Foydalanuvchining barcha sessiyalarini bekor qiladi. */
export async function destroyAllSessions(userId: ObjectId): Promise<number> {
  try {
    const col = await sessions();
    const res = await col.deleteMany({ userId });
    return res.deletedCount;
  } catch {
    return 0;
  }
}

export function clientIp(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0]?.trim() ?? "nomaʼlum";
  return request.headers.get("x-real-ip") ?? "nomaʼlum";
}
