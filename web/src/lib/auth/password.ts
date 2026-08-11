/**
 * Parol bilan ishlash.
 *
 * `scrypt` — Node tarkibida, tashqi paket kerak emas (bcrypt/argon2 native
 * kompilyatsiya talab qiladi). Har parol uchun alohida tuz (salt) yaratiladi.
 * Solishtirish doim `timingSafeEqual` bilan — javob vaqti parol qanchalik
 * to'g'ri ekanini oshkor qilmasligi kerak.
 */

import { randomBytes, scrypt, timingSafeEqual } from "node:crypto";
import { promisify } from "node:util";

const scryptAsync = promisify(scrypt) as (
  password: string,
  salt: string,
  keylen: number,
) => Promise<Buffer>;

const KEY_LENGTH = 64;

export async function hashPassword(
  password: string,
): Promise<{ hash: string; salt: string }> {
  const salt = randomBytes(16).toString("hex");
  const derived = await scryptAsync(password, salt, KEY_LENGTH);
  return { hash: derived.toString("hex"), salt };
}

export async function verifyPassword(
  password: string,
  hash: string,
  salt: string,
): Promise<boolean> {
  try {
    const derived = await scryptAsync(password, salt, KEY_LENGTH);
    const expected = Buffer.from(hash, "hex");
    if (expected.length !== derived.length) return false;
    return timingSafeEqual(derived, expected);
  } catch {
    return false;
  }
}

/** Ikkita satrni vaqt bo'yicha xavfsiz solishtiradi. */
export function safeEqual(a: string, b: string): boolean {
  const bufA = Buffer.from(a, "utf8");
  const bufB = Buffer.from(b, "utf8");
  if (bufA.length !== bufB.length) return false;
  return timingSafeEqual(bufA, bufB);
}

/**
 * Parol talablari. Xato matni foydalanuvchiga ko'rsatiladi, shuning uchun
 * aniq va o'zbekcha.
 */
export function checkPasswordStrength(password: string): string | null {
  if (password.length < 8) return "Parol kamida 8 belgidan iborat boʻlsin.";
  if (password.length > 200) return "Parol juda uzun.";
  if (!/[a-zA-Z]/.test(password) || !/[0-9]/.test(password)) {
    return "Parolda kamida bitta harf va bitta raqam boʻlsin.";
  }
  return null;
}
