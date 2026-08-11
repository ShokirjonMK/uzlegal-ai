import { errorJson } from "@/lib/util/sse";
import { buildCookie, USER_COOKIE } from "@/lib/auth/cookie";
import { createSession } from "@/lib/auth/session";
import { pollBotLogin, startBotLogin, toPublicUser } from "@/lib/auth/users";
import { isMongoConfigured } from "@/lib/db/mongo";
import { botUsername } from "@/lib/auth/telegram-login";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** POST /api/auth/bot — kirish kodini yaratadi. */
export async function POST(): Promise<Response> {
  if (!isMongoConfigured()) {
    return errorJson("Hisoblar bazasi sozlanmagan. MONGODB_URI kerak.", 503);
  }
  try {
    const started = await startBotLogin();
    return Response.json({ ...started, bot: botUsername() });
  } catch (err) {
    return errorJson(err instanceof Error ? err.message : "Kod yaratilmadi.", 500);
  }
}

/**
 * GET /api/auth/bot?id=… — kod tasdiqlandimi.
 * Tasdiqlangan bo'lsa o'sha yerda sessiya ochiladi.
 */
export async function GET(request: Request): Promise<Response> {
  if (!isMongoConfigured()) {
    return errorJson("Hisoblar bazasi sozlanmagan. MONGODB_URI kerak.", 503);
  }

  const id = new URL(request.url).searchParams.get("id")?.trim();
  if (!id) return errorJson("`id` parametri koʻrsatilmagan.");

  try {
    const user = await pollBotLogin(id);
    if (!user) return Response.json({ ok: false, kutilmoqda: true });

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
    return errorJson(err instanceof Error ? err.message : "Tekshiruvda xatolik.", 500);
  }
}
