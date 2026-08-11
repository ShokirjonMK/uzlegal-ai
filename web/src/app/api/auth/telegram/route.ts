import { errorJson } from "@/lib/util/sse";
import { buildCookie, USER_COOKIE } from "@/lib/auth/cookie";
import { createSession } from "@/lib/auth/session";
import { verifyTelegramLogin } from "@/lib/auth/telegram-login";
import { toPublicUser, upsertTelegramUser } from "@/lib/auth/users";
import { isMongoConfigured } from "@/lib/db/mongo";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * POST /api/auth/telegram — Telegram Login Widget qaytargan ma'lumot.
 * Imzo bot tokeni bilan qayta hisoblanadi; ishonchsiz ma'lumot rad etiladi.
 */
export async function POST(request: Request): Promise<Response> {
  if (!isMongoConfigured()) {
    return errorJson("Hisoblar bazasi sozlanmagan. MONGODB_URI kerak.", 503);
  }

  let raw: Record<string, unknown>;
  try {
    raw = (await request.json()) as Record<string, unknown>;
  } catch {
    return errorJson("Soʻrov tanasi notoʻgʻri.");
  }

  const check = verifyTelegramLogin(raw);
  if (!check.ok) return errorJson(check.error, 401);

  try {
    const user = await upsertTelegramUser(check.data.id, {
      username: check.data.username,
      firstName: check.data.first_name,
    });
    const session = await createSession(user._id, request);

    return Response.json(
      { ok: true, user: toPublicUser(user) },
      {
        headers: {
          "set-cookie": buildCookie(request, USER_COOKIE, session.token, {
            maxAgeSeconds: session.maxAgeSeconds,
            sameSite: "Lax",
          }),
        },
      },
    );
  } catch (err) {
    return errorJson(err instanceof Error ? err.message : "Kirishda xatolik.", 500);
  }
}
