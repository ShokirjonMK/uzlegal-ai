import { config } from "@/lib/config";
import { getBot } from "@/lib/bot";
import type { Update } from "grammy/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

/**
 * POST /api/telegram — Telegram webhook.
 *
 * Telegram 60 soniya ichida javob kutadi, model esa undan uzoq ishlashi mumkin.
 * Shuning uchun update darhol qabul qilinadi (200 qaytariladi), ishlov esa
 * fon rejimida davom etadi — aks holda Telegram bir xil xabarni qayta yuboradi.
 *
 * DIQQAT: bu yondashuv doimiy ishlaydigan Node serveri uchun. Serverless
 * muhitda (funksiya javobdan keyin to'xtatiladi) navbat (queue) kerak bo'ladi —
 * yoki `npm run bot:poll` bilan polling rejimidan foydalaning.
 */
export async function POST(request: Request): Promise<Response> {
  // Webhook maxfiy tokenini tekshirish.
  const expected = config.telegramWebhookSecret;
  if (expected) {
    const got = request.headers.get("x-telegram-bot-api-secret-token");
    if (got !== expected) {
      return new Response("Forbidden", { status: 403 });
    }
  }

  let update: Update;
  try {
    update = (await request.json()) as Update;
  } catch {
    return new Response("Bad Request", { status: 400 });
  }

  let bot;
  try {
    bot = getBot();
    await bot.init();
  } catch (err) {
    console.error("[telegram] bot ishga tushmadi:", err);
    return new Response("Bot sozlanmagan", { status: 503 });
  }

  // Fon rejimida ishlov beramiz, Telegram'ga darhol javob qaytaramiz.
  void bot.handleUpdate(update).catch((err) => {
    console.error("[telegram] update ishlovida xatolik:", err);
  });

  return new Response("OK");
}

/** GET — webhook manzili to'g'ri sozlanganini tekshirish uchun. */
export async function GET(): Promise<Response> {
  return Response.json({
    ok: true,
    configured: Boolean(config.telegramToken),
    secretRequired: Boolean(config.telegramWebhookSecret),
    hint: "Bu manzilni Telegram webhook sifatida sozlang: npm run bot:set-webhook",
  });
}
