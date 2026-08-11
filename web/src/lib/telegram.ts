/**
 * Telegram Bot API ga to'g'ridan-to'g'ri murojaat.
 *
 * `bot.ts` dan ataylab mustaqil: u yerda grammY `Bot` nusxasi butun buyruqlar
 * to'plami bilan quriladi, admin marshrutlariga esa faqat xabar yuborish
 * kerak. Shuning uchun bu yerda oddiy `fetch`.
 */

import { config } from "./config";

/** Telegram xabar uzunligi chegarasi. */
const TG_LIMIT = 4096;

/** Uzun matnni Telegram chegarasiga mos bo'laklarga bo'ladi. */
export function splitForTelegram(text: string, limit = TG_LIMIT): string[] {
  if (text.length <= limit) return [text];

  const parts: string[] = [];
  let rest = text;

  while (rest.length > limit) {
    let cut = rest.lastIndexOf("\n\n", limit);
    if (cut < limit * 0.5) cut = rest.lastIndexOf("\n", limit);
    if (cut < limit * 0.5) cut = rest.lastIndexOf(" ", limit);
    if (cut < limit * 0.5) cut = limit;
    parts.push(rest.slice(0, cut).trimEnd());
    rest = rest.slice(cut).trimStart();
  }
  if (rest) parts.push(rest);
  return parts;
}

/**
 * Bitta chatga xabar yuboradi. Uzun matn bo'laklarga bo'linadi.
 * Xatoga uchrasa `false` qaytaradi — chaqiruvchi hisobini o'zi yuritadi.
 */
export async function sendTelegramMessage(
  chatId: string | number,
  text: string,
): Promise<boolean> {
  const token = config.telegramToken;
  if (!token) return false;

  try {
    for (const part of splitForTelegram(text)) {
      const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          text: part,
          link_preview_options: { is_disabled: true },
        }),
      });
      if (!res.ok) return false;
    }
    return true;
  } catch {
    return false;
  }
}

/** Barcha adminlarga yuboradi. Kamida bittasiga yetib borsa `true`. */
export async function sendToAdmins(text: string): Promise<boolean> {
  const ids = config.adminChatIds;
  if (ids.length === 0) return false;

  const results = await Promise.all(ids.map((id) => sendTelegramMessage(id, text)));
  return results.some(Boolean);
}
