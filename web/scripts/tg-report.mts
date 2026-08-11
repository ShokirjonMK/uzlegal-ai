/**
 * Telegram hisobot yuboruvchi.
 *
 * Loyiha qoidalariga ko'ra (CLAUDE.md) har bir topshiriq bo'yicha ikki marta
 * hisobot yuboriladi: boshida (Senior PM tahlili) va oxirida (Senior PM hisoboti).
 *
 * Foydalanish:
 *   npm run report -- --kind pm-start --id 12 --title "..." --body "..."
 *   npm run report -- --kind pm-done  --id 12 --title "..." --body "..." --status ok
 *   echo "matn" | npm run report -- --kind info --title "..."
 *
 * Turlar (--kind):
 *   pm-start   Senior PM — topshiriq qabul qilindi, reja
 *   pm-done    Senior PM — yakuniy hisobot
 *   dev        Senior Developer — bajarish holati
 *   qa         Senior QA — test natijasi
 *   qa-fail    Senior QA — test o'tmadi, devga qaytarildi
 *   info       Erkin xabar
 */

import { loadEnv } from "../src/lib/load-env";
loadEnv();

import { config } from "../src/lib/config";

const TG_LIMIT = 4096;

interface Args {
  kind: string;
  id?: string;
  title?: string;
  body?: string;
  status?: string;
}

function parseArgs(argv: string[]): Args {
  const out: Record<string, string> = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a?.startsWith("--")) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next && !next.startsWith("--")) {
        out[key] = next;
        i++;
      } else {
        out[key] = "true";
      }
    }
  }
  return { kind: out.kind ?? "info", ...out } as Args;
}

const HEADERS: Record<string, string> = {
  "pm-start": "🧭 SENIOR PM — TOPSHIRIQ QABUL QILINDI",
  "pm-done": "✅ SENIOR PM — YAKUNIY HISOBOT",
  dev: "🛠 SENIOR DEVELOPER",
  qa: "🔍 SENIOR QA — TEST NATIJASI",
  "qa-fail": "⛔️ SENIOR QA — TEST OʻTMADI, DEVGA QAYTARILDI",
  info: "ℹ️ MAʼLUMOT",
};

/** stdin bo'sh bo'lmasa o'qiydi (quvur orqali uzun matn yuborish uchun). */
async function readStdin(): Promise<string> {
  if (process.stdin.isTTY) return "";
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) chunks.push(Buffer.from(chunk));
  return Buffer.concat(chunks).toString("utf8").trim();
}

function splitMessage(text: string): string[] {
  if (text.length <= TG_LIMIT) return [text];
  const parts: string[] = [];
  let rest = text;
  while (rest.length > TG_LIMIT) {
    let cut = rest.lastIndexOf("\n\n", TG_LIMIT);
    if (cut < TG_LIMIT * 0.5) cut = rest.lastIndexOf("\n", TG_LIMIT);
    if (cut < TG_LIMIT * 0.5) cut = TG_LIMIT;
    parts.push(rest.slice(0, cut).trimEnd());
    rest = rest.slice(cut).trimStart();
  }
  if (rest) parts.push(rest);
  return parts;
}

/** Bitta chatga xabar yuboradi. */
async function send(chatId: number, text: string): Promise<void> {
  const token = config.telegramToken;
  if (!token) throw new Error("TELEGRAM_BOT_TOKEN sozlanmagan.");

  for (const part of splitMessage(text)) {
    const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text: part,
        link_preview_options: { is_disabled: true },
      }),
    });
    const json = (await res.json()) as { ok: boolean; description?: string };
    if (!json.ok) {
      throw new Error(`Telegram xatosi: ${json.description ?? "nomaʼlum"}`);
    }
  }
}

/** Hisobotni barcha adminlarga yuboradi. Dastur oqimini hech qachon to'xtatmaydi. */
export async function report(args: Args, extraBody = ""): Promise<boolean> {
  const admins = config.adminChatIds;
  if (admins.length === 0) {
    console.error("ADMIN_CHAT_ID sozlanmagan — hisobot yuborilmadi.");
    return false;
  }

  const header = HEADERS[args.kind] ?? HEADERS.info!;
  const stamp = new Date().toLocaleString("uz-UZ", {
    timeZone: "Asia/Tashkent",
    dateStyle: "short",
    timeStyle: "short",
  });

  const lines = [header];
  if (args.id || args.title) {
    lines.push(
      `${args.id ? `#${args.id} · ` : ""}${args.title ?? ""}`.trim(),
    );
  }
  if (args.status) lines.push(`Holat: ${args.status}`);
  lines.push(`⏱ ${stamp} (Toshkent)`);
  lines.push("");
  lines.push([args.body, extraBody].filter(Boolean).join("\n\n"));

  const text = lines.join("\n").trim();

  let allOk = true;
  for (const chatId of admins) {
    try {
      await send(chatId, text);
    } catch (err) {
      allOk = false;
      console.error(
        `Hisobot yuborilmadi (${chatId}):`,
        err instanceof Error ? err.message : err,
      );
    }
  }
  return allOk;
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const piped = await readStdin();
  const ok = await report(args, piped);
  if (ok) console.log("✅ Hisobot yuborildi.");
  else process.exitCode = 1;
}

// To'g'ridan-to'g'ri ishga tushirilganda bajariladi (import qilinganda emas).
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((err) => {
    console.error(err instanceof Error ? err.message : err);
    process.exit(1);
  });
}
