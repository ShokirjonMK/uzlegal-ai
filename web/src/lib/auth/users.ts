/**
 * Foydalanuvchi hisoblari va uchta kirish usuli.
 *
 *  1. Telegram Login Widget — saytdagi tugma, imzo `telegram-login.ts` da tekshiriladi.
 *  2. Telegram bot — sayt kod ko'rsatadi, foydalanuvchi botga `/kirish KOD` yozadi.
 *  3. Elektron pochta + parol.
 *
 * Uchalasi ham BITTA `users` yozuviga olib keladi. Telegram ID bo'yicha
 * bog'lanish muhim: botdagi savol tarixi va saytdagi tarix bir joyda ko'rinadi.
 *
 * 2-usul nega Mongo da saqlanadi: bot alohida jarayonda ishlashi mumkin
 * (`npm run bot:poll`), shuning uchun kodni jarayon xotirasida saqlab bo'lmaydi.
 */

import { createHash, randomBytes, randomInt } from "node:crypto";
import { ObjectId } from "mongodb";
import { loginCodes, users, type UserDoc } from "../db/collections";
import { checkPasswordStrength, hashPassword, verifyPassword } from "./password";

/** Bot orqali kirish kodi shuncha vaqt amal qiladi. */
const BOT_CODE_TTL_MS = 10 * 60_000;

function hashCode(code: string): string {
  return createHash("sha256").update(code.trim().toUpperCase()).digest("hex");
}

function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

// ── Telegram bo'yicha hisob ────────────────────────────────────────────────

/** Telegram ID bo'yicha topadi, bo'lmasa yaratadi. */
export async function upsertTelegramUser(
  telegramId: number,
  info: { username?: string; firstName?: string } = {},
): Promise<UserDoc> {
  const col = await users();
  const now = new Date();

  await col.updateOne(
    { telegramId },
    {
      $set: {
        lastSeenAt: now,
        ...(info.username ? { username: info.username } : {}),
        ...(info.firstName ? { firstName: info.firstName } : {}),
      },
      $setOnInsert: {
        telegramId,
        roles: [],
        createdAt: now,
        requests: 0,
      },
      $addToSet: { surfaces: "telegram" as const },
    },
    { upsert: true },
  );

  const user = await col.findOne({ telegramId });
  if (!user) throw new Error("Foydalanuvchini yaratib boʻlmadi.");
  return user;
}

// ── Bot orqali kirish (kod) ────────────────────────────────────────────────

export interface BotLoginStart {
  /** Foydalanuvchi botga yozadigan kod. */
  code: string;
  /** Sayt shu identifikator bilan holatni tekshiradi. */
  attemptId: string;
}

export async function startBotLogin(): Promise<BotLoginStart> {
  // Chalkashmaydigan alifbo: 0/O va 1/I olib tashlangan.
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let code = "";
  for (let i = 0; i < 6; i++) code += alphabet[randomInt(0, alphabet.length)];

  const attemptId = randomBytes(18).toString("base64url");
  const col = await loginCodes();

  await col.insertOne({
    _id: attemptId,
    kind: "user",
    codeHash: hashCode(code),
    createdAt: new Date(),
    expiresAt: new Date(Date.now() + BOT_CODE_TTL_MS),
    tries: 0,
  });

  return { code, attemptId };
}

/**
 * Bot chaqiradi: foydalanuvchi `/kirish KOD` yozganda.
 * Kod topilsa unga Telegram ID biriktiriladi.
 */
export async function confirmBotLogin(
  code: string,
  telegramId: number,
  info: { username?: string; firstName?: string } = {},
): Promise<{ ok: boolean; error?: string }> {
  const col = await loginCodes();
  const rec = await col.findOne({
    codeHash: hashCode(code),
    kind: "user",
    expiresAt: { $gt: new Date() },
  });

  if (!rec) return { ok: false, error: "Kod topilmadi yoki muddati oʻtgan." };

  await upsertTelegramUser(telegramId, info);
  await col.updateOne({ _id: rec._id }, { $set: { telegramId } });

  return { ok: true };
}

/** Sayt so'raydi: kod tasdiqlandimi. Tasdiqlangan bo'lsa foydalanuvchi qaytadi. */
export async function pollBotLogin(attemptId: string): Promise<UserDoc | null> {
  const col = await loginCodes();
  const rec = await col.findOne({ _id: attemptId });
  if (!rec?.telegramId) return null;

  // Kod bir marta ishlaydi.
  await col.deleteOne({ _id: attemptId });

  const userCol = await users();
  return userCol.findOne({ telegramId: rec.telegramId });
}

// ── Elektron pochta va parol ───────────────────────────────────────────────

export type EmailResult = { ok: true; user: UserDoc } | { ok: false; error: string };

export async function registerWithEmail(
  email: string,
  password: string,
  firstName?: string,
): Promise<EmailResult> {
  const normalized = normalizeEmail(email);
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(normalized)) {
    return { ok: false, error: "Elektron pochta manzili notoʻgʻri." };
  }

  const weak = checkPasswordStrength(password);
  if (weak) return { ok: false, error: weak };

  const col = await users();
  if (await col.findOne({ email: normalized })) {
    return { ok: false, error: "Bu pochta manzili allaqachon roʻyxatdan oʻtgan." };
  }

  const { hash, salt } = await hashPassword(password);
  const now = new Date();
  const _id = new ObjectId();

  await col.insertOne({
    _id,
    email: normalized,
    passwordHash: hash,
    passwordSalt: salt,
    firstName,
    roles: [],
    surfaces: ["web"],
    createdAt: now,
    lastSeenAt: now,
    requests: 0,
  });

  const user = await col.findOne({ _id });
  if (!user) return { ok: false, error: "Hisob yaratilmadi." };
  return { ok: true, user };
}

export async function loginWithEmail(
  email: string,
  password: string,
): Promise<EmailResult> {
  const col = await users();
  const user = await col.findOne({ email: normalizeEmail(email) });

  // Xato xabari ataylab umumiy: qaysi pochta ro'yxatda borligini oshkor qilmaydi.
  const generic = "Pochta yoki parol notoʻgʻri.";

  if (!user?.passwordHash || !user.passwordSalt) {
    return { ok: false, error: generic };
  }
  if (user.blocked) {
    return { ok: false, error: "Hisob bloklangan." };
  }
  if (!(await verifyPassword(password, user.passwordHash, user.passwordSalt))) {
    return { ok: false, error: generic };
  }

  await col.updateOne({ _id: user._id }, { $set: { lastSeenAt: new Date() } });
  return { ok: true, user };
}

/** Panel va kabinet uchun xavfsiz ko'rinish — parol xeshi chiqmaydi. */
export interface PublicUser {
  id: string;
  telegramId?: number;
  username?: string;
  firstName?: string;
  email?: string;
  roles: string[];
  createdAt: string;
}

export function toPublicUser(user: UserDoc): PublicUser {
  return {
    id: user._id.toHexString(),
    telegramId: user.telegramId,
    username: user.username,
    firstName: user.firstName,
    email: user.email,
    roles: user.roles ?? [],
    createdAt: user.createdAt.toISOString(),
  };
}
