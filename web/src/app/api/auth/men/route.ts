import { clearCookie, USER_COOKIE } from "@/lib/auth/cookie";
import { currentUser, destroySession } from "@/lib/auth/session";
import { toPublicUser } from "@/lib/auth/users";
import { botUsername } from "@/lib/auth/telegram-login";
import { isMongoConfigured } from "@/lib/db/mongo";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** GET /api/auth/men — joriy foydalanuvchi va mavjud kirish usullari. */
export async function GET(request: Request): Promise<Response> {
  const user = await currentUser(request);
  return Response.json({
    user: user ? toPublicUser(user) : null,
    usullar: {
      pochta: isMongoConfigured(),
      bot: isMongoConfigured() && Boolean(process.env.TELEGRAM_BOT_TOKEN),
      widget: Boolean(process.env.TELEGRAM_BOT_TOKEN) && Boolean(botUsername()),
    },
    bot: botUsername(),
  });
}

/** DELETE /api/auth/men — chiqish. */
export async function DELETE(request: Request): Promise<Response> {
  await destroySession(request);
  return Response.json(
    { ok: true },
    { headers: { "set-cookie": clearCookie(request, USER_COOKIE) } },
  );
}
