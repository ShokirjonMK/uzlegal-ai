import { errorJson } from "@/lib/util/sse";
import { buildCookie, USER_COOKIE } from "@/lib/auth/cookie";
import { createSession } from "@/lib/auth/session";
import { loginWithEmail, registerWithEmail, toPublicUser } from "@/lib/auth/users";
import { isMongoConfigured } from "@/lib/db/mongo";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * POST /api/auth/kirish — pochta va parol bilan kirish yoki ro'yxatdan o'tish.
 * Tana: `{ email, parol, ism?, royxat?: boolean }`
 */
export async function POST(request: Request): Promise<Response> {
  if (!isMongoConfigured()) {
    return errorJson("Hisoblar bazasi sozlanmagan. MONGODB_URI kerak.", 503);
  }

  let body: { email?: unknown; parol?: unknown; ism?: unknown; royxat?: unknown };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return errorJson("Soʻrov tanasi notoʻgʻri.");
  }

  const email = typeof body.email === "string" ? body.email : "";
  const parol = typeof body.parol === "string" ? body.parol : "";
  const ism = typeof body.ism === "string" ? body.ism.trim().slice(0, 80) : undefined;

  if (!email || !parol) {
    return errorJson("Pochta va parol kiritilishi shart.");
  }

  try {
    const royxat = body.royxat === true;
    const result = royxat
      ? await registerWithEmail(email, parol, ism || undefined)
      : await loginWithEmail(email, parol);

    // Ro'yxatdan o'tishdagi xato — kiritilgan ma'lumot noto'g'ri (400),
    // kirishdagi xato — ruxsat berilmadi (401). Ikkisi bir xil emas.
    if (!result.ok) return errorJson(result.error, royxat ? 400 : 401);

    const session = await createSession(result.user._id, request);

    return Response.json(
      { ok: true, user: toPublicUser(result.user) },
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
    return errorJson(
      err instanceof Error ? err.message : "Kirishda xatolik.",
      500,
    );
  }
}
