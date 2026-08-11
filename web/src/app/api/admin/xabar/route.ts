import { config } from "@/lib/config";
import { adminGuard } from "@/lib/auth/admin";
import { errorJson } from "@/lib/util/sse";
import { allUserIds } from "@/lib/analytics";
import { sendTelegramMessage, sendToAdmins } from "@/lib/telegram";
import { isMongoConfigured } from "@/lib/db/mongo";
import { users } from "@/lib/db/collections";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

const MAX_TEXT = 3500;
/** Telegram cheklovi: sekundiga ~30 xabar. */
const SEND_DELAY_MS = 40;

/**
 * Qabul qiluvchilar ro'yxati. Ikki manba birlashtiriladi: eski statistika
 * bazasi (bot shu yerga yozadi) va Mongo dagi hisoblar.
 */
async function recipients(): Promise<number[]> {
  const ids = new Set<number>();

  for (const raw of allUserIds("telegram")) {
    const n = Number(raw);
    if (Number.isFinite(n) && n !== 0) ids.add(n);
  }

  if (isMongoConfigured()) {
    try {
      const col = await users();
      const rows = await col
        .find({ telegramId: { $exists: true }, blocked: { $ne: true } })
        .project<{ telegramId: number }>({ telegramId: 1 })
        .toArray();
      for (const r of rows) if (r.telegramId) ids.add(r.telegramId);
    } catch {
      // Mongo yetib bormasa — eski manbadagi ro'yxat bilan davom etadi.
    }
  }

  return [...ids];
}

/** GET /api/admin/xabar — qabul qiluvchilar soni. */
export async function GET(request: Request): Promise<Response> {
  const denied = adminGuard(request);
  if (denied) return denied;

  const list = await recipients();
  return Response.json({
    qabulQiluvchilar: list.length,
    adminlar: config.adminChatIds.length,
    botSozlangan: Boolean(config.telegramToken),
  });
}

/**
 * POST /api/admin/xabar — ommaviy xabar.
 *
 * Ikki bosqich, ataylab:
 *   `{ matn, sinov: true }` — faqat adminning o'ziga yuboriladi;
 *   `{ matn, tasdiq: <son> }` — `tasdiq` qabul qiluvchilar soniga TENG bo'lishi
 *   shart. Ya'ni sonni qo'lda yozib kiritish kerak — tasodifan bosib yuborish
 *   imkonsiz.
 */
export async function POST(request: Request): Promise<Response> {
  const denied = adminGuard(request);
  if (denied) return denied;

  if (!config.telegramToken) {
    return errorJson("Telegram bot sozlanmagan (TELEGRAM_BOT_TOKEN).", 503);
  }

  let body: { matn?: unknown; sinov?: unknown; tasdiq?: unknown };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return errorJson("Soʻrov tanasi notoʻgʻri.");
  }

  const matn = typeof body.matn === "string" ? body.matn.trim() : "";
  if (!matn) return errorJson("Xabar matni boʻsh.");
  if (matn.length > MAX_TEXT) {
    return errorJson(`Xabar juda uzun — ${MAX_TEXT} belgigacha ruxsat etiladi.`);
  }

  // ── Sinov: faqat adminlarga ──────────────────────────────────────────────
  if (body.sinov === true) {
    const ok = await sendToAdmins(`🧪 SINOV XABARI (faqat sizga)\n\n${matn}`);
    return ok
      ? Response.json({
          ok: true,
          sinov: true,
          xabar: "Sinov xabari Telegramdagi admin kanalingizga yuborildi.",
        })
      : errorJson("Sinov xabari yuborilmadi. Bot sozlamalarini tekshiring.", 502);
  }

  // ── Haqiqiy yuborish: tasdiq soni talab qilinadi ─────────────────────────
  const list = await recipients();
  if (list.length === 0) {
    return errorJson("Qabul qiluvchi topilmadi.", 404);
  }

  if (body.tasdiq !== list.length) {
    return errorJson(
      `Tasdiq notoʻgʻri. Yuborish uchun qabul qiluvchilar sonini (${list.length}) ` +
        `qoʻlda yozib kiriting.`,
      409,
    );
  }

  let yuborildi = 0;
  let yuborilmadi = 0;

  for (const id of list) {
    const ok = await sendTelegramMessage(id, matn);
    if (ok) yuborildi++;
    else yuborilmadi++;
    await new Promise((r) => setTimeout(r, SEND_DELAY_MS));
  }

  await sendToAdmins(
    `📣 Ommaviy xabar yuborildi\nYetib bordi: ${yuborildi}\nYetmadi: ${yuborilmadi}`,
  );

  return Response.json({
    ok: true,
    yuborildi,
    yuborilmadi,
    xabar: `Yuborildi: ${yuborildi}, yetmadi: ${yuborilmadi}.`,
  });
}
