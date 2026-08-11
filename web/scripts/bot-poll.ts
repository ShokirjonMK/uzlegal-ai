/**
 * Telegram botni polling rejimida ishga tushiradi.
 *
 * Ommaviy manzil (webhook) kerak emas — lokal ishlab chiqish uchun eng qulay yo'l.
 *   npm run bot:poll
 */

import { getBot } from "../src/lib/bot";
import { config } from "../src/lib/config";
import { stats } from "../src/lib/rag/store";

async function main(): Promise<void> {
  if (!config.telegramToken) {
    console.error(
      "TELEGRAM_BOT_TOKEN sozlanmagan.\n" +
        "@BotFather dan token oling va .env.local fayliga qoʻshing.",
    );
    process.exit(1);
  }

  const bot = getBot();
  await bot.init();

  try {
    const s = stats();
    console.log(
      s.chunks > 0
        ? `Qonun bazasi: ${s.chunks} boʻlak, ${s.documents.length} hujjat.`
        : "Qonun bazasi boʻsh — javoblarda modda havolalari boʻlmaydi. `npm run ingest` bilan toʻldiring.",
    );
  } catch {
    console.log("Qonun bazasi hali yaratilmagan.");
  }

  // Webhook o'rnatilgan bo'lsa, polling ishlamaydi — avval o'chiramiz.
  await bot.api.deleteWebhook({ drop_pending_updates: false }).catch(() => {});

  console.log(`Bot ishga tushdi: @${bot.botInfo.username}`);
  console.log("Toʻxtatish uchun Ctrl+C.");

  const stop = () => {
    console.log("\nToʻxtatilmoqda…");
    void bot.stop();
  };
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);

  await bot.start({ drop_pending_updates: true });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
