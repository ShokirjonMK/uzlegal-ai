import { errorJson } from "@/lib/util/sse";
import {
  adminSetup,
  checkAdminCode,
  checkAdminPassword,
  createAdminToken,
} from "@/lib/auth/admin";
import { ADMIN_COOKIE, buildCookie, clearCookie } from "@/lib/auth/cookie";
import { clientIp } from "@/lib/auth/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function grant(request: Request, extra: Record<string, unknown> = {}): Response {
  const { token, maxAgeSeconds } = createAdminToken();
  return Response.json(
    { ok: true, bosqich: "kirdi", ...extra },
    {
      headers: {
        "set-cookie": buildCookie(request, ADMIN_COOKIE, token, {
          maxAgeSeconds,
          sameSite: "Strict",
        }),
      },
    },
  );
}

/**
 * POST /api/admin/kirish — ikki bosqichli kirish.
 *
 * Birinchi bosqich: `{ parol }`.
 *   → Telegram sozlangan bo'lsa `{ bosqich: "kod", urinish }` qaytadi va
 *     6 xonali kod ADMIN_CHAT_ID ga yuboriladi.
 *   → Sozlanmagan bo'lsa darhol sessiya beriladi.
 *
 * Ikkinchi bosqich: `{ urinish, kod }`.
 */
export async function POST(request: Request): Promise<Response> {
  const setup = adminSetup();
  if (!setup.ready) {
    return errorJson(
      `Admin panel sozlanmagan. .env.local ga qoʻshing: ${setup.missing.join(", ")}.`,
      503,
    );
  }

  let body: { parol?: unknown; kod?: unknown; urinish?: unknown };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return errorJson("Soʻrov tanasi notoʻgʻri.");
  }

  // ── Ikkinchi bosqich ─────────────────────────────────────────────────────
  if (typeof body.urinish === "string" && typeof body.kod === "string") {
    const res = checkAdminCode(body.urinish, body.kod);
    if (!res.ok) return errorJson(res.error, 401);
    return grant(request);
  }

  // ── Birinchi bosqich ─────────────────────────────────────────────────────
  if (typeof body.parol !== "string" || !body.parol) {
    return errorJson("Parol kiritilmagan.");
  }

  const res = await checkAdminPassword(body.parol, clientIp(request));
  if (!res.ok) return errorJson(res.error, 401);

  if (res.step === "kirdi") {
    return grant(request, {
      ogohlantirish:
        "Telegram tasdigʻi sozlanmagan — parolning oʻzi bilan kirildi. " +
        "TELEGRAM_BOT_TOKEN va ADMIN_CHAT_ID ni sozlash tavsiya etiladi.",
    });
  }

  return Response.json({
    ok: true,
    bosqich: "kod",
    urinish: res.attemptId,
    izoh: "Tasdiqlash kodi Telegramga yuborildi. 5 daqiqa amal qiladi.",
  });
}

/** DELETE /api/admin/kirish — paneldan chiqish. */
export async function DELETE(request: Request): Promise<Response> {
  return Response.json(
    { ok: true },
    { headers: { "set-cookie": clearCookie(request, ADMIN_COOKIE) } },
  );
}
