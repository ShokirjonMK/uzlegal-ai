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
  // Webhook maxfiy tokenini tekshirish — FAIL-CLOSED (audit #21).
  //
  // Ilgari bu blok `if (expected) {…}` edi: sir sozlanmagan bo'lsa
  // tekshiruv BUTUNLAY o'tkazib yuborilardi. Ya'ni standart holatda
  // (`.env` da o'zgaruvchi yo'q) marshrut har kimga ochiq edi va
  // istalgan odam bot nomidan soxta `Update` yubora olardi — bu esa
  // model chaqiruvi, ya'ni to'g'ridan-to'g'ri pul.
  //
  // Endi sir MAJBURIY. Sozlanmagan bo'lsa marshrut ishlamaydi va sabab
  // aniq aytiladi. Lokal ishlab chiqish uchun webhook shart emas —
  // `npm run bot:poll` (long-polling) ishlatiladi.
  const expected = config.telegramWebhookSecret;
  if (!expected) {
    console.error("[telegram] TELEGRAM_WEBHOOK_SECRET sozlanmagan — webhook oʻchirilgan");
    return new Response("Webhook sozlanmagan: TELEGRAM_WEBHOOK_SECRET kerak", { status: 503 });
  }
  if (request.headers.get("x-telegram-bot-api-secret-token") !== expected) {
    return new Response("Forbidden", { status: 403 });
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

/**
 * GET — webhook manzili to'g'ri sozlanganini tekshirish uchun.
 *
 * `secretRequired` maydoni olib tashlandi: u `false` qaytarganda
 * marshrut himoyasiz ekanini OSHKOR QILARDI. Endi sir baribir majburiy,
 * shuning uchun `ready` bitta halol signal beradi va hech qanday
 * chetlab o'tish yo'lini ko'rsatmaydi.
 */
export async function GET(): Promise<Response> {
  const ready = Boolean(config.telegramToken) && Boolean(config.telegramWebhookSecret);
  return Response.json({
    ok: true,
    ready,
    hint: ready
      ? "Bu manzilni Telegram webhook sifatida sozlang: npm run bot:set-webhook"
      : "TELEGRAM_BOT_TOKEN va TELEGRAM_WEBHOOK_SECRET sozlanishi kerak",
  });
}
