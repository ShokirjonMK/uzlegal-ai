/**
 * Telegram webhook manzilini o'rnatadi.
 *
 *   npm run bot:set-webhook              — PUBLIC_BASE_URL asosida o'rnatadi
 *   npm run bot:set-webhook -- --delete  — webhook'ni o'chiradi (polling uchun)
 *   npm run bot:set-webhook -- --info    — joriy holatni ko'rsatadi
 */

import { getBot } from "../src/lib/bot";
import { config } from "../src/lib/config";

async function main(): Promise<void> {
  if (!config.telegramToken) {
    console.error("TELEGRAM_BOT_TOKEN sozlanmagan.");
    process.exit(1);
  }

  const bot = getBot();
  await bot.init();
  const args = process.argv.slice(2);

  if (args.includes("--info")) {
    const info = await bot.api.getWebhookInfo();
    console.log(JSON.stringify(info, null, 2));
    return;
  }

  if (args.includes("--delete")) {
    await bot.api.deleteWebhook({ drop_pending_updates: false });
    console.log("Webhook oʻchirildi. Endi polling rejimida ishlatish mumkin.");
    return;
  }

  const base = config.publicBaseUrl;
  if (!base) {
    console.error(
      "PUBLIC_BASE_URL sozlanmagan.\n" +
        "Masalan: PUBLIC_BASE_URL=https://ai-lowyer.example.com\n" +
        "Lokal sinov uchun `npm run bot:poll` dan foydalaning.",
    );
    process.exit(1);
  }

  if (!base.startsWith("https://")) {
    console.error("Telegram faqat HTTPS manzillarni qabul qiladi.");
    process.exit(1);
  }

  const url = `${base}/api/telegram`;
  const secret = config.telegramWebhookSecret;

  if (!secret) {
    console.warn(
      "Ogohlantirish: TELEGRAM_WEBHOOK_SECRET sozlanmagan. " +
        "Uni qoʻshish tavsiya etiladi — aks holda manzilni bilgan har kim " +
        "botga soxta xabar yubora oladi.",
    );
  }

  await bot.api.setWebhook(url, {
    secret_token: secret,
    drop_pending_updates: true,
    allowed_updates: ["message"],
  });

  console.log(`Webhook oʻrnatildi: ${url}`);
  console.log(`Bot: @${bot.botInfo.username}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
