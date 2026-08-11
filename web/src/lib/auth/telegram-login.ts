/**
 * Telegram Login Widget imzosini tekshirish.
 *
 * Telegram ma'lumotni brauzer orqali yuboradi — ya'ni foydalanuvchi uni
 * o'zgartira oladi. Shuning uchun imzo SERVER tomonda qayta hisoblanadi:
 *   secret = SHA256(bot_token)
 *   hash   = HMAC-SHA256(secret, "kalit=qiymat\n…" alifbo tartibida)
 * Bot tokenini bilmasdan to'g'ri `hash` yasab bo'lmaydi.
 *
 * Hujjat: https://core.telegram.org/widgets/login
 */

import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { config } from "../config";

export interface TelegramLoginData {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
}

/** Imzo shuncha vaqtdan keyin eskirgan hisoblanadi (takroriy hujumga qarshi). */
const MAX_AGE_SECONDS = 24 * 3600;

export type LoginCheck =
  | { ok: true; data: TelegramLoginData }
  | { ok: false; error: string };

export function verifyTelegramLogin(raw: Record<string, unknown>): LoginCheck {
  const token = config.telegramToken;
  if (!token) {
    return { ok: false, error: "Telegram bot sozlanmagan." };
  }

  const hash = typeof raw.hash === "string" ? raw.hash : "";
  if (!hash) return { ok: false, error: "Imzo yoʻq." };

  const id = Number(raw.id);
  const authDate = Number(raw.auth_date);
  if (!Number.isFinite(id) || !Number.isFinite(authDate)) {
    return { ok: false, error: "Maʼlumot toʻliq emas." };
  }

  const ageSeconds = Math.floor(Date.now() / 1000) - authDate;
  if (ageSeconds > MAX_AGE_SECONDS) {
    return { ok: false, error: "Kirish maʼlumoti eskirgan. Qaytadan urinib koʻring." };
  }

  // `hash` dan boshqa barcha maydonlar alifbo tartibida qatorlarga yoziladi.
  const checkString = Object.keys(raw)
    .filter((k) => k !== "hash" && raw[k] !== undefined && raw[k] !== null)
    .sort()
    .map((k) => `${k}=${String(raw[k])}`)
    .join("\n");

  const secret = createHash("sha256").update(token).digest();
  const expected = createHmac("sha256", secret).update(checkString).digest("hex");

  const a = Buffer.from(expected, "hex");
  const b = Buffer.from(hash, "hex");
  if (a.length !== b.length || !timingSafeEqual(a, b)) {
    return { ok: false, error: "Imzo notoʻgʻri." };
  }

  return {
    ok: true,
    data: {
      id,
      auth_date: authDate,
      hash,
      first_name: typeof raw.first_name === "string" ? raw.first_name : undefined,
      last_name: typeof raw.last_name === "string" ? raw.last_name : undefined,
      username: typeof raw.username === "string" ? raw.username : undefined,
      photo_url: typeof raw.photo_url === "string" ? raw.photo_url : undefined,
    },
  };
}

/** Widget uchun bot foydalanuvchi nomi (`@` siz). Sozlanmagan bo'lsa `undefined`. */
export function botUsername(): string | undefined {
  return process.env.TELEGRAM_BOT_USERNAME?.trim().replace(/^@/, "") || undefined;
}
