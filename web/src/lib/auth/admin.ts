/**
 * Admin panel himoyasi.
 *
 * NEGA MONGO EMAS. Admin sessiyasi HMAC bilan imzolangan cookie'da yashaydi
 * va bazaga umuman murojaat qilmaydi. Sabab amaliy: agar admin sessiyasi
 * Mongo da saqlansa, Mongo o'chganda panelga kira olmaysiz — holbuki aynan
 * o'shanda panelga «baza ishlamayapti» deb qarash kerak bo'ladi.
 *
 * Kirish oqimi ikki bosqichli:
 *   1) parol → to'g'ri bo'lsa 6 xonali kod yaratiladi va bot orqali
 *      ADMIN_CHAT_ID ga yuboriladi;
 *   2) kod → to'g'ri bo'lsa imzolangan cookie beriladi.
 *
 * Bot tokeni yoki admin chat ID sozlanmagan bo'lsa ikkinchi bosqich o'tkazib
 * yuboriladi (aks holda bot ishlamay qolganda panel butunlay yopilib qoladi).
 */

import { createHmac, randomBytes, randomInt, timingSafeEqual } from "node:crypto";
import { config } from "../config";
import { sendToAdmins } from "../telegram";
import { ADMIN_COOKIE, readCookie } from "./cookie";

/** Kod amal qilish muddati. */
const CODE_TTL_MS = 5 * 60_000;
/** Bitta kodga necha marta urinish mumkin. */
const MAX_CODE_TRIES = 5;
/** Bitta IP dan ketma-ket necha marta parol xato kiritilishi mumkin. */
const MAX_PASSWORD_FAILS = 6;
const FAIL_WINDOW_MS = 10 * 60_000;

interface PendingCode {
  codeHash: string;
  expiresAt: number;
  tries: number;
}

interface FailRecord {
  count: number;
  resetAt: number;
}

/*
 * Kutilayotgan kodlar va urinish hisobi jarayon xotirasida. Mongo ga
 * bog'lanmaslik ataylab (yuqoridagi izohga qarang). Server qayta ishga
 * tushsa kutilayotgan kod bekor bo'ladi — bu 5 daqiqalik noqulaylik, xolos.
 */
const globalForAuth = globalThis as unknown as {
  __aiLowyerAdminCodes?: Map<string, PendingCode>;
  __aiLowyerAdminFails?: Map<string, FailRecord>;
};

const pending = (globalForAuth.__aiLowyerAdminCodes ??= new Map());
const fails = (globalForAuth.__aiLowyerAdminFails ??= new Map());

function hmac(data: string): string {
  const secret = config.adminSessionSecret;
  if (!secret) throw new Error("ADMIN_SESSION_SECRET sozlanmagan.");
  return createHmac("sha256", secret).update(data).digest("base64url");
}

function equal(a: string, b: string): boolean {
  const bufA = Buffer.from(a);
  const bufB = Buffer.from(b);
  if (bufA.length !== bufB.length) return false;
  return timingSafeEqual(bufA, bufB);
}

// ── Sozlanganlik holati ────────────────────────────────────────────────────

export interface AdminSetup {
  ready: boolean;
  /** Nima yetishmayotgani — panelda ko'rsatiladi. */
  missing: string[];
  twoFactor: boolean;
}

export function adminSetup(): AdminSetup {
  const missing: string[] = [];
  if (!config.adminPassword) missing.push("ADMIN_PASSWORD");
  if (!config.adminSessionSecret) missing.push("ADMIN_SESSION_SECRET");
  return {
    ready: missing.length === 0,
    missing,
    twoFactor: config.adminTwoFactor,
  };
}

// ── Sessiya ────────────────────────────────────────────────────────────────

function sign(expiresAt: number): string {
  return `${expiresAt}.${hmac(`admin:${expiresAt}`)}`;
}

export function createAdminToken(): { token: string; maxAgeSeconds: number } {
  const seconds = config.adminSessionHours * 3600;
  const expiresAt = Date.now() + seconds * 1000;
  return { token: sign(expiresAt), maxAgeSeconds: seconds };
}

function verifyToken(token: string | undefined): boolean {
  if (!token || !config.adminSessionSecret) return false;

  const dot = token.indexOf(".");
  if (dot < 0) return false;

  const expiresAt = Number(token.slice(0, dot));
  if (!Number.isFinite(expiresAt) || expiresAt < Date.now()) return false;

  try {
    return equal(token.slice(dot + 1), hmac(`admin:${expiresAt}`));
  } catch {
    return false;
  }
}

/** So'rovda haqiqiy admin sessiyasi bormi. */
export function isAdminRequest(request: Request): boolean {
  if (!adminSetup().ready) return false;
  return verifyToken(readCookie(request, ADMIN_COOKIE));
}

/** Cookie satridan tekshirish (server komponentlari uchun). */
export function isAdminCookie(token: string | undefined): boolean {
  if (!adminSetup().ready) return false;
  return verifyToken(token);
}

/**
 * Marshrut qorovuli. Ruxsat bo'lmasa tayyor javob qaytaradi, bo'lsa `null`.
 * Har bir `/api/admin/*` marshruti shu bilan boshlanadi.
 */
export function adminGuard(request: Request): Response | null {
  if (isAdminRequest(request)) return null;
  return Response.json({ error: "Ruxsat yoʻq." }, { status: 401 });
}

// ── Urinishlar chegarasi ───────────────────────────────────────────────────

export function tooManyAttempts(ip: string): boolean {
  const rec = fails.get(ip);
  if (!rec) return false;
  if (Date.now() > rec.resetAt) {
    fails.delete(ip);
    return false;
  }
  return rec.count >= MAX_PASSWORD_FAILS;
}

function registerFail(ip: string): void {
  const now = Date.now();
  const rec = fails.get(ip);
  if (!rec || now > rec.resetAt) {
    fails.set(ip, { count: 1, resetAt: now + FAIL_WINDOW_MS });
  } else {
    rec.count += 1;
  }
}

function clearFails(ip: string): void {
  fails.delete(ip);
}

// ── Birinchi bosqich: parol ────────────────────────────────────────────────

export type PasswordStep =
  | { ok: false; error: string }
  | { ok: true; step: "kod"; attemptId: string }
  | { ok: true; step: "kirdi" };

export async function checkAdminPassword(
  password: string,
  ip: string,
): Promise<PasswordStep> {
  const setup = adminSetup();
  if (!setup.ready) {
    return {
      ok: false,
      error: `Panel sozlanmagan. .env.local ga qoʻshing: ${setup.missing.join(", ")}.`,
    };
  }

  if (tooManyAttempts(ip)) {
    return {
      ok: false,
      error: "Urinishlar soni koʻp. 10 daqiqadan keyin qayta urinib koʻring.",
    };
  }

  if (!equal(password, config.adminPassword ?? "")) {
    registerFail(ip);
    return { ok: false, error: "Parol notoʻgʻri." };
  }

  clearFails(ip);

  if (!setup.twoFactor) {
    // Telegram sozlanmagan — parolning o'zi yetarli.
    return { ok: true, step: "kirdi" };
  }

  const code = String(randomInt(100_000, 1_000_000));
  const attemptId = randomBytes(18).toString("base64url");

  pending.set(attemptId, {
    codeHash: hmac(`code:${code}`),
    expiresAt: Date.now() + CODE_TTL_MS,
    tries: 0,
  });

  const sent = await sendToAdmins(
    `🔐 Admin panelga kirish kodi: ${code}\n\n` +
      `5 daqiqa amal qiladi. Agar bu siz boʻlmasangiz — parolni darhol oʻzgartiring.`,
  );

  if (!sent) {
    pending.delete(attemptId);
    return {
      ok: false,
      error: "Tasdiqlash kodini Telegramga yuborib boʻlmadi. Bot sozlamalarini tekshiring.",
    };
  }

  return { ok: true, step: "kod", attemptId };
}

// ── Ikkinchi bosqich: kod ──────────────────────────────────────────────────

export function checkAdminCode(
  attemptId: string,
  code: string,
): { ok: false; error: string } | { ok: true } {
  const rec = pending.get(attemptId);
  if (!rec) {
    return { ok: false, error: "Urinish topilmadi yoki muddati oʻtgan. Qaytadan boshlang." };
  }

  if (Date.now() > rec.expiresAt) {
    pending.delete(attemptId);
    return { ok: false, error: "Kod muddati oʻtdi. Qaytadan boshlang." };
  }

  rec.tries += 1;
  if (rec.tries > MAX_CODE_TRIES) {
    pending.delete(attemptId);
    return { ok: false, error: "Urinishlar tugadi. Qaytadan boshlang." };
  }

  let matches = false;
  try {
    matches = equal(hmac(`code:${code.trim()}`), rec.codeHash);
  } catch {
    matches = false;
  }

  if (!matches) {
    return {
      ok: false,
      error: `Kod notoʻgʻri. Yana ${MAX_CODE_TRIES - rec.tries + 1} urinish qoldi.`,
    };
  }

  pending.delete(attemptId);
  return { ok: true };
}
