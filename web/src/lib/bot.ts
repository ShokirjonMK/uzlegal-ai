/**
 * Telegram bot (grammY).
 *
 * Ikki rejimda ishlaydi:
 *  - webhook  — `/api/telegram` marshruti orqali (ishlab chiqarish uchun);
 *  - polling  — `npm run bot:poll` (lokal ishlab chiqish, ommaviy manzil kerak emas).
 *
 * Super admin (ADMIN_CHAT_ID) statistika buyruqlariga ega bo'ladi va
 * yangi foydalanuvchi hamda xatoliklar haqida bildirishnoma oladi.
 */

import { Bot, InputFile } from "grammy";
import type { Context } from "grammy";
import { config } from "./config";
import { callMeta, humanError } from "./llm";
import { ask } from "./services/ask";
import { analyze } from "./services/analyze";
import { generate } from "./services/generate";
import { extractText, isSupported } from "./util/extract";
import { resultToDocx, safeFilename } from "./util/docx";
import { stats } from "./rag/store";
import { allUserIds, formatSummary, record, summary, lifetime } from "./analytics";
import { recordAiCall } from "./db/log";
import { confirmBotLogin } from "./auth/users";
import { isMongoConfigured } from "./db/mongo";
import type { ChatMessage, DocTemplateId } from "./types";

/** Telegram xabar uzunligi chegarasi. */
const TG_LIMIT = 4096;
/** Telegram Bot API orqali yuklab olish mumkin bo'lgan maksimal hajm. */
const MAX_FILE_BYTES = 20 * 1024 * 1024;

/** Suhbat tarixi (jarayon xotirasida). Qayta ishga tushirilsa tozalanadi. */
const histories = new Map<number, ChatMessage[]>();
const HISTORY_LIMIT = 10;

function getHistory(chatId: number): ChatMessage[] {
  return histories.get(chatId) ?? [];
}

function pushHistory(chatId: number, user: string, assistant: string): void {
  const h = getHistory(chatId);
  h.push({ role: "user", content: user }, { role: "assistant", content: assistant });
  histories.set(chatId, h.slice(-HISTORY_LIMIT * 2));
}

// ── Yordamchilar ───────────────────────────────────────────────────────────

/** Uzun matnni Telegram chegarasiga mos bo'laklarga bo'ladi. */
function splitMessage(text: string, limit = TG_LIMIT): string[] {
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

async function replyLong(ctx: Context, text: string): Promise<void> {
  for (const part of splitMessage(text)) {
    await ctx.reply(part, { link_preview_options: { is_disabled: true } });
  }
}

/** "Yozmoqda…" holatini uzoq amal davomida ushlab turadi. */
function keepTyping(ctx: Context): () => void {
  const send = () => void ctx.replyWithChatAction("typing").catch(() => {});
  send();
  const timer = setInterval(send, 5000);
  return () => clearInterval(timer);
}

function isAdmin(ctx: Context): boolean {
  const id = ctx.chat?.id;
  return id !== undefined && config.adminChatIds.includes(id);
}

/** Adminlarga bildirishnoma yuboradi (xatoga uchrasa jim o'tadi). */
async function notifyAdmins(b: Bot, text: string): Promise<void> {
  for (const id of config.adminChatIds) {
    await b.api
      .sendMessage(id, text, { link_preview_options: { is_disabled: true } })
      .catch(() => {});
  }
}

/** Amalni statistikaga yozadi va yangi foydalanuvchi bo'lsa adminni xabardor qiladi. */
async function track(
  b: Bot,
  ctx: Context,
  input: Parameters<typeof record>[0],
): Promise<void> {
  const { isNewUser } = record(input);
  if (isNewUser && config.adminChatIds.length > 0) {
    const u = ctx.from;
    const name = [u?.first_name, u?.last_name].filter(Boolean).join(" ");
    const life = lifetime();
    await notifyAdmins(
      b,
      `👤 Yangi foydalanuvchi\n` +
        `Ism: ${name || "—"}\n` +
        `Username: ${u?.username ? `@${u.username}` : "—"}\n` +
        `ID: ${ctx.chat?.id}\n` +
        `Til: ${u?.language_code ?? "—"}\n\n` +
        `Jami foydalanuvchilar: ${life.users}`,
    );
  }
}

// ── Matnlar ────────────────────────────────────────────────────────────────

const WELCOME = `Assalomu alaykum! Men — AI Lawyer, Oʻzbekiston qonunchiligi boʻyicha yordamchiman.

Nima qila olaman:

• *Savol-javob* — huquqiy savolingizni shunchaki yozing.
• *Hujjat tahlili* — shartnoma yoki hujjatni fayl qilib yuboring (PDF, DOCX, TXT). Xavflarni topib beraman.
• *Hujjat tayyorlash* — /hujjat buyrugʻi.

Buyruqlar:
/hujjat — hujjat loyihasini tayyorlash
/tozalash — suhbat tarixini oʻchirish
/baza — qonun bazasi holati
/id — chat ID ingizni koʻrsatish
/yordam — batafsil maʼlumot

⚠️ Men advokat emasman. Javoblarim maʼlumot uchun, yuridik maslahat emas.`;

const HELP = `*Qanday foydalanish*

*1. Savol berish*
Savolingizni oddiy matn bilan yozing. Masalan:
_"Ish beruvchi meni ogohlantirmasdan ishdan boʻshata oladimi?"_

Javobda qonun moddasiga havola boʻladi (agar bazada topilsa).

*2. Hujjatni tahlil qilish*
Shartnoma yoki boshqa hujjatni fayl qilib yuboring.
Qoʻllab-quvvatlanadi: PDF, DOCX, TXT, MD, HTML (20 MB gacha).

Faylga izoh yozsangiz, kim nuqtai nazaridan tahlil qilishni koʻrsatishingiz mumkin:
_"ijarachi tomonidan"_

*3. Hujjat tayyorlash*
\`/hujjat <tur> <tafsilotlar>\`

Masalan:
\`/hujjat ijara-shartnomasi Toshkentda 2 xonali kvartira, oyiga 5 mln soʻm, 1 yil\`

Turlar: mehnat-shartnomasi, ijara-shartnomasi, oldi-sotdi-shartnomasi,
xizmat-korsatish-shartnomasi, pudrat-shartnomasi, davo-arizasi,
ishonchnoma, tilxat, ariza, pretenziya, erkin

Tayyor hujjat .docx fayl sifatida yuboriladi.

*Tillar*
Oʻzbek (lotin va kirill), rus va ingliz tillarini tushunaman.
Qaysi tilda yozsangiz, shu tilda javob beraman.

⚠️ Bu — maʼlumot uchun tushuntirish, yuridik maslahat emas.
Aniq ish boʻyicha advokatga murojaat qiling.`;

const ADMIN_HELP = `*Admin buyruqlari*

/stat — oxirgi 24 soat statistikasi
/stat 7 — oxirgi 7 kun
/stat 1 — oxirgi 1 kun
/tizim — tizim holati (model, baza, sozlamalar)
/xabar <matn> — barcha foydalanuvchilarga xabar yuborish`;

// ── Bot ────────────────────────────────────────────────────────────────────

let bot: Bot | null = null;

/** Bot namunasini qaytaradi (bir marta yaratiladi). */
export function getBot(): Bot {
  if (bot) return bot;

  const token = config.telegramToken;
  if (!token) {
    throw new Error(
      "TELEGRAM_BOT_TOKEN sozlanmagan. @BotFather dan token oling va .env.local ga qoʻshing.",
    );
  }

  bot = new Bot(token);
  registerHandlers(bot);
  return bot;
}

function registerHandlers(b: Bot): void {
  // ── Umumiy buyruqlar ─────────────────────────────────────────────────────

  b.command("start", async (ctx) => {
    await track(b, ctx, {
      kind: "start",
      surface: "telegram",
      userId: String(ctx.chat.id),
      username: ctx.from?.username,
    });
    await ctx.reply(WELCOME, { parse_mode: "Markdown" });
    if (isAdmin(ctx)) {
      await ctx.reply(ADMIN_HELP, { parse_mode: "Markdown" });
    }
  });

  b.command(["help", "yordam"], async (ctx) => {
    await ctx.reply(HELP, { parse_mode: "Markdown" });
    if (isAdmin(ctx)) await ctx.reply(ADMIN_HELP, { parse_mode: "Markdown" });
  });

  b.command("id", async (ctx) => {
    await ctx.reply(
      `Chat ID: \`${ctx.chat.id}\`` +
        (ctx.from?.username ? `\nUsername: @${ctx.from.username}` : "") +
        (isAdmin(ctx) ? "\n\n✅ Siz adminsiz." : ""),
      { parse_mode: "Markdown" },
    );
  });

  b.command(["clear", "tozalash"], async (ctx) => {
    histories.delete(ctx.chat.id);
    await ctx.reply("Suhbat tarixi oʻchirildi. Yangi savol berishingiz mumkin.");
  });

  /*
   * Saytga bot orqali kirish. Sayt 6 belgilik kod ko'rsatadi, foydalanuvchi
   * uni shu yerga yozadi. Kod bazada tekshiriladi — shuning uchun bot alohida
   * jarayonda ishlasa ham (`npm run bot:poll`) oqim buziladi.
   */
  b.command(["kirish", "login"], async (ctx) => {
    const code = ctx.match?.toString().trim();

    if (!isMongoConfigured()) {
      await ctx.reply("Saytdagi shaxsiy kabinet hozircha ishlamayapti.");
      return;
    }

    if (!code) {
      await ctx.reply(
        "Saytga kirish uchun:\n" +
          "1. Saytda «Telegram bot orqali kirish» tugmasini bosing;\n" +
          "2. Chiqqan kodni shu yerga `/kirish KOD` shaklida yuboring.",
        { parse_mode: "Markdown" },
      );
      return;
    }

    try {
      const res = await confirmBotLogin(code, ctx.chat.id, {
        username: ctx.from?.username,
        firstName: ctx.from?.first_name,
      });
      await ctx.reply(
        res.ok
          ? "✅ Tasdiqlandi. Saytdagi oynaga qayting — u oʻzi ochiladi."
          : `❌ ${res.error ?? "Kod tasdiqlanmadi."}`,
      );
    } catch {
      await ctx.reply("Kodni tekshirib boʻlmadi. Birozdan keyin urinib koʻring.");
    }
  });

  b.command(["corpus", "baza"], async (ctx) => {
    try {
      const s = stats();
      if (s.chunks === 0) {
        await ctx.reply(
          "Qonun bazasi boʻsh. Javoblar umumiy bilimga tayanadi va modda havolalari boʻlmaydi.",
        );
        return;
      }
      const docs = s.documents
        .map((d) => `• ${d.document} — ${d.chunks} boʻlak`)
        .join("\n");
      await ctx.reply(`*Qonun bazasi*\nJami boʻlaklar: ${s.chunks}\n\n${docs}`, {
        parse_mode: "Markdown",
      });
    } catch (err) {
      await ctx.reply(humanError(err));
    }
  });

  // ── Admin buyruqlari ─────────────────────────────────────────────────────

  b.command(["stat", "statistika"], async (ctx) => {
    if (!isAdmin(ctx)) {
      await ctx.reply("Bu buyruq faqat administrator uchun.");
      return;
    }
    const days = Number(ctx.match?.toString().trim()) || 1;
    const hours = Math.min(Math.max(days, 1), 365) * 24;
    try {
      await replyLong(ctx, formatSummary(summary(hours), hours));
    } catch (err) {
      await ctx.reply(humanError(err));
    }
  });

  b.command(["tizim", "system"], async (ctx) => {
    if (!isAdmin(ctx)) {
      await ctx.reply("Bu buyruq faqat administrator uchun.");
      return;
    }
    let corpus = "oʻqib boʻlmadi";
    try {
      const s = stats();
      corpus = `${s.chunks} boʻlak, ${s.documents.length} hujjat (${s.embedder ?? "—"})`;
    } catch {
      /* baza hali yaratilmagan */
    }
    await ctx.reply(
      `⚙️ *Tizim holati*\n\n` +
        `Model: \`${config.model}\`\n` +
        `Fikrlash: \`${config.effort}\`\n` +
        `Til / yozuv: \`${config.lang}\` / \`${config.script}\`\n` +
        `Anthropic kalit: ${config.anthropicApiKey ? "✅" : "❌"}\n` +
        `Embedding: \`${config.embeddingProvider}\`\n` +
        `Qonun bazasi: ${corpus}\n` +
        `Adminlar: ${config.adminChatIds.length}`,
      { parse_mode: "Markdown" },
    );
  });

  b.command(["xabar", "broadcast"], async (ctx) => {
    if (!isAdmin(ctx)) {
      await ctx.reply("Bu buyruq faqat administrator uchun.");
      return;
    }
    const text = ctx.match?.toString().trim();
    if (!text) {
      await ctx.reply("Foydalanish: /xabar <yuboriladigan matn>");
      return;
    }
    const ids = allUserIds("telegram");
    let sent = 0;
    let failed = 0;
    for (const id of ids) {
      const ok = await b.api
        .sendMessage(Number(id), text)
        .then(() => true)
        .catch(() => false);
      if (ok) sent++;
      else failed++;
      // Telegram cheklovi: sekundiga ~30 xabar.
      await new Promise((r) => setTimeout(r, 40));
    }
    await ctx.reply(`Yuborildi: ${sent}\nYuborilmadi: ${failed}`);
  });

  // ── Hujjat yaratish ──────────────────────────────────────────────────────

  b.command(["document", "hujjat"], async (ctx) => {
    const arg = ctx.match?.toString().trim() ?? "";
    if (!arg) {
      await ctx.reply(
        "Foydalanish:\n`/hujjat <tur> <tafsilotlar>`\n\n" +
          "Masalan:\n`/hujjat ijara-shartnomasi Toshkentda 2 xonali kvartira, oyiga 5 mln soʻm, 1 yil`\n\n" +
          "Turlar roʻyxatini /yordam da koʻring.",
        { parse_mode: "Markdown" },
      );
      return;
    }

    const [first, ...rest] = arg.split(/\s+/);
    const template = (first ?? "erkin") as DocTemplateId;
    const details = rest.join(" ") || arg;

    const stop = keepTyping(ctx);
    const started = Date.now();
    try {
      const result = await generate({ template, details });
      const buffer = await resultToDocx(result);

      await ctx.replyWithDocument(
        new InputFile(buffer, safeFilename(result.title, "docx")),
        {
          caption:
            `*${result.title}*\n\n` +
            (result.placeholders.length
              ? `Toʻldirilishi kerak: ${result.placeholders.slice(0, 10).join(", ")}` +
                (result.placeholders.length > 10 ? " va boshqalar" : "")
              : "Barcha maydonlar toʻldirilgan.") +
            `\n\n⚠️ Bu — loyiha. Imzolashdan oldin yuristga koʻrsating.`,
          parse_mode: "Markdown",
        },
      );

      await track(b, ctx, {
        kind: "generate",
        surface: "telegram",
        userId: String(ctx.chat.id),
        username: ctx.from?.username,
        label: template,
        inputChars: details.length,
        inputTokens: result.usage?.inputTokens,
        outputTokens: result.usage?.outputTokens,
        durationMs: Date.now() - started,
      });
    } catch (err) {
      await handleFailure(b, ctx, err, "generate", started);
    } finally {
      stop();
    }
  });

  // ── Fayl yuborilganda — tahlil ───────────────────────────────────────────

  b.on("message:document", async (ctx) => {
    const doc = ctx.message.document;
    const name = doc.file_name ?? "hujjat";

    if (!isSupported(name)) {
      await ctx.reply(
        "Bu format qoʻllab-quvvatlanmaydi. PDF, DOCX, TXT, MD yoki HTML yuboring.",
      );
      return;
    }
    if ((doc.file_size ?? 0) > MAX_FILE_BYTES) {
      await ctx.reply("Fayl juda katta (chegara: 20 MB).");
      return;
    }

    const stop = keepTyping(ctx);
    const started = Date.now();
    try {
      const file = await ctx.getFile();
      const url = `https://api.telegram.org/file/bot${config.telegramToken}/${file.file_path}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Faylni yuklab boʻlmadi.");

      const buffer = Buffer.from(await res.arrayBuffer());
      const text = await extractText(buffer, name);

      const result = await analyze({
        text,
        filename: name,
        perspective: ctx.message.caption?.trim() || undefined,
      });

      await replyLong(ctx, formatAnalysis(result));

      await track(b, ctx, {
        kind: "analyze",
        surface: "telegram",
        userId: String(ctx.chat.id),
        username: ctx.from?.username,
        label: name.split(".").pop(),
        inputChars: text.length,
        inputTokens: result.usage?.inputTokens,
        outputTokens: result.usage?.outputTokens,
        durationMs: Date.now() - started,
      });
    } catch (err) {
      await handleFailure(b, ctx, err, "analyze", started);
    } finally {
      stop();
    }
  });

  // ── Oddiy matn — savol-javob ─────────────────────────────────────────────

  b.on("message:text", async (ctx) => {
    const question = ctx.message.text.trim();
    if (!question || question.startsWith("/")) return;

    const chatId = ctx.chat.id;
    const stop = keepTyping(ctx);
    const started = Date.now();
    try {
      const result = await ask({ question, history: getHistory(chatId) });
      pushHistory(chatId, question, result.answer);
      await replyLong(ctx, result.answer);

      recordAiCall({
        kind: "ask",
        surface: "telegram",
        telegramId: chatId,
        ...callMeta(),
        input: question,
        output: result.answer,
        citations: result.citations,
        inputTokens: result.usage?.inputTokens,
        outputTokens: result.usage?.outputTokens,
        durationMs: Date.now() - started,
        label: `${result.lang}/${result.script}`,
      });

      await track(b, ctx, {
        kind: "ask",
        surface: "telegram",
        userId: String(chatId),
        username: ctx.from?.username,
        inputChars: question.length,
        inputTokens: result.usage?.inputTokens,
        outputTokens: result.usage?.outputTokens,
        durationMs: Date.now() - started,
        label: `${result.lang}/${result.script}`,
      });
    } catch (err) {
      await handleFailure(b, ctx, err, "ask", started);
    } finally {
      stop();
    }
  });

  b.catch((err) => {
    console.error("[telegram] xatolik:", err.error);
  });
}

/** Xatolikni foydalanuvchiga bildiradi, statistikaga yozadi va adminni ogohlantiradi. */
async function handleFailure(
  b: Bot,
  ctx: Context,
  err: unknown,
  kind: "ask" | "analyze" | "generate",
  started: number,
): Promise<void> {
  const message = humanError(err);
  await ctx.reply(message).catch(() => {});

  const technical = err instanceof Error ? `${err.name}: ${err.message}` : String(err);
  record({
    kind,
    surface: "telegram",
    userId: ctx.chat ? String(ctx.chat.id) : undefined,
    username: ctx.from?.username,
    error: technical.slice(0, 500),
    durationMs: Date.now() - started,
  });

  await notifyAdmins(
    b,
    `🚨 Xatolik (${kind})\n` +
      `Foydalanuvchi: ${ctx.from?.username ? `@${ctx.from.username}` : ctx.chat?.id}\n` +
      `${technical.slice(0, 500)}`,
  );
}

/** Tahlil natijasini Telegram uchun matnga aylantiradi. */
function formatAnalysis(r: Awaited<ReturnType<typeof analyze>>): string {
  const lines: string[] = [];

  lines.push(`📄 ${r.documentType.toUpperCase()}`, "", r.summary, "");

  if (r.parties.length) {
    lines.push("Tomonlar:");
    for (const p of r.parties) lines.push(`• ${p.role}: ${p.name}`);
    lines.push("");
  }

  if (r.keyTerms.length) {
    lines.push("Muhim shartlar:");
    for (const k of r.keyTerms) lines.push(`• ${k.label}: ${k.value}`);
    lines.push("");
  }

  if (r.risks.length) {
    lines.push(`⚠️ Aniqlangan xavflar (${r.risks.length} ta):`, "");
    for (const [i, risk] of r.risks.entries()) {
      const icon =
        risk.level === "yuqori" ? "🔴" : risk.level === "oʻrta" ? "🟡" : "🟢";
      lines.push(`${icon} ${i + 1}. ${risk.title} [${risk.level}]`);
      if (risk.location) lines.push(`   Joyi: ${risk.location}`);
      lines.push(`   ${risk.explanation}`);
      lines.push(`   ✅ Tavsiya: ${risk.recommendation}`);
      if (risk.legalBasis) lines.push(`   📖 ${risk.legalBasis}`);
      lines.push("");
    }
  } else {
    lines.push("✅ Jiddiy xavf aniqlanmadi.", "");
  }

  if (r.missingClauses.length) {
    lines.push("Yetishmayotgan shartlar:");
    for (const cl of r.missingClauses) lines.push(`• ${cl}`);
    lines.push("");
  }

  lines.push("Xulosa:", r.conclusion, "");
  lines.push("⚠️ Bu — maʼlumot uchun tahlil, yuridik maslahat emas.");

  return lines.join("\n");
}
