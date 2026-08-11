/**
 * Cookie o'qish va yozish.
 *
 * `Secure` bayrog'i so'rov protokoliga qarab qo'yiladi: lokal `http://localhost`
 * da `Secure` cookie brauzerda umuman saqlanmaydi, shuning uchun uni ko'r-ko'rona
 * qo'yib bo'lmaydi. Ishlab chiqarishda (proksi ortida ham) `Secure` yoqiladi.
 */

export const ADMIN_COOKIE = "admin_sessiya";
export const USER_COOKIE = "sessiya";

/** So'rov sarlavhasidan bitta cookie qiymatini oladi. */
export function readCookie(request: Request, name: string): string | undefined {
  const header = request.headers.get("cookie");
  if (!header) return undefined;

  for (const part of header.split(";")) {
    const eq = part.indexOf("=");
    if (eq < 0) continue;
    if (part.slice(0, eq).trim() === name) {
      return decodeURIComponent(part.slice(eq + 1).trim());
    }
  }
  return undefined;
}

function isSecure(request: Request): boolean {
  const forwarded = request.headers.get("x-forwarded-proto");
  if (forwarded) return forwarded.split(",")[0]?.trim() === "https";
  try {
    return new URL(request.url).protocol === "https:";
  } catch {
    return false;
  }
}

export interface CookieOptions {
  maxAgeSeconds: number;
  /** `strict` — admin uchun; `lax` — oddiy foydalanuvchi uchun. */
  sameSite?: "Strict" | "Lax";
}

export function buildCookie(
  request: Request,
  name: string,
  value: string,
  opts: CookieOptions,
): string {
  const parts = [
    `${name}=${encodeURIComponent(value)}`,
    "Path=/",
    "HttpOnly",
    `SameSite=${opts.sameSite ?? "Strict"}`,
    `Max-Age=${opts.maxAgeSeconds}`,
  ];
  if (isSecure(request)) parts.push("Secure");
  return parts.join("; ");
}

/** Cookie'ni o'chiradigan sarlavha. */
export function clearCookie(request: Request, name: string): string {
  return buildCookie(request, name, "", { maxAgeSeconds: 0 });
}
