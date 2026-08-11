import { errorJson } from "@/lib/util/sse";
import { currentUser } from "@/lib/auth/session";
import { aiCalls } from "@/lib/db/collections";
import { isMongoConfigured } from "@/lib/db/mongo";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const PAGE_SIZE = 15;

/**
 * GET /api/kabinet/tarix?sahifa=1 — foydalanuvchining O'Z tarixi.
 *
 * Filtr har doim sessiyadan olingan shaxsga bog'lanadi: so'rov parametri
 * bilan boshqa birovning tarixini so'rab bo'lmaydi.
 */
export async function GET(request: Request): Promise<Response> {
  if (!isMongoConfigured()) {
    return errorJson("Kabinet hozircha ishlamayapti.", 503);
  }

  const user = await currentUser(request);
  if (!user) return errorJson("Avval tizimga kiring.", 401);

  const page = Math.max(1, Number(new URL(request.url).searchParams.get("sahifa") ?? 1) || 1);

  // Telegramdagi savollar ham shu yerga tushishi uchun ikkala belgi ham qidiriladi.
  const filter = user.telegramId
    ? { $or: [{ userId: user._id }, { telegramId: user.telegramId }] }
    : { userId: user._id };

  try {
    const col = await aiCalls();
    const [rows, jami] = await Promise.all([
      col
        .find(filter)
        .sort({ createdAt: -1 })
        .skip((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .toArray(),
      col.countDocuments(filter),
    ]);

    return Response.json({
      sahifa: page,
      sahifaHajmi: PAGE_SIZE,
      jami,
      yozuvlar: rows.map((r) => ({
        id: r._id.toHexString(),
        tur: r.kind,
        yuza: r.surface,
        savol: r.input,
        javob: r.output,
        sana: r.createdAt.toISOString(),
        xato: r.error,
      })),
    });
  } catch (err) {
    return errorJson(
      err instanceof Error ? err.message : "Tarixni oʻqib boʻlmadi.",
      500,
    );
  }
}
