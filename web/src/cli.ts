#!/usr/bin/env node
/**
 * AI Lawyer — buyruqlar qatori interfeysi.
 *
 *   npm run cli -- <buyruq> [parametrlar]
 *
 * Misollar:
 *   npm run cli -- baza
 *   npm run cli -- yukla
 *   npm run cli -- soragan "Sinov muddati necha oy?"
 *   npm run cli -- qidir "ishdan boshatish"
 *   npm run cli -- tahlil shartnoma.pdf
 *   npm run cli -- tekshir shartnoma.docx
 *   npm run cli -- yarat ijara-shartnomasi "Toshkent, 2 xonali, 5 mln som" --out ijara.docx
 */

import { loadEnv } from "./lib/load-env";
loadEnv();

import { readFile, writeFile } from "node:fs/promises";
import { basename } from "node:path";
import { humanError } from "./lib/llm";
import { config } from "./lib/config";
import { ingestDirectory } from "./lib/rag/ingest";
import { retrieve } from "./lib/rag/retrieve";
import { clearStore, closeStore, stats } from "./lib/rag/store";
import { analyze } from "./lib/services/analyze";
import { askStream } from "./lib/services/ask";
import { generate } from "./lib/services/generate";
import { review } from "./lib/services/review";
import { extractText } from "./lib/util/extract";
import { resultToDocx, safeFilename } from "./lib/util/docx";
import type { DocTemplateId } from "./lib/types";

// ── Argument tahlili ───────────────────────────────────────────────────────

interface Args {
  command: string;
  positional: string[];
  flags: Record<string, string | boolean>;
}

function parseArgs(argv: string[]): Args {
  const [command = "yordam", ...rest] = argv;
  const positional: string[] = [];
  const flags: Record<string, string | boolean> = {};

  for (let i = 0; i < rest.length; i++) {
    const arg = rest[i]!;
    if (arg.startsWith("--")) {
      const key = arg.slice(2);
      const next = rest[i + 1];
      if (next && !next.startsWith("--")) {
        flags[key] = next;
        i++;
      } else {
        flags[key] = true;
      }
    } else {
      positional.push(arg);
    }
  }

  return { command, positional, flags };
}

// ── Chiqish formatlash ─────────────────────────────────────────────────────

const c = {
  bold: (s: string) => `\x1b[1m${s}\x1b[0m`,
  dim: (s: string) => `\x1b[2m${s}\x1b[0m`,
  red: (s: string) => `\x1b[31m${s}\x1b[0m`,
  green: (s: string) => `\x1b[32m${s}\x1b[0m`,
  yellow: (s: string) => `\x1b[33m${s}\x1b[0m`,
  cyan: (s: string) => `\x1b[36m${s}\x1b[0m`,
};

function out(s = ""): void {
  process.stdout.write(`${s}\n`);
}

// ── Buyruqlar ──────────────────────────────────────────────────────────────

const HELP = `${c.bold("AI Lawyer")} — Oʻzbekiston qonunchiligi boʻyicha yordamchi

${c.bold("BUYRUQLAR")}

  ${c.cyan("baza")}                          Qonun bazasi holati
  ${c.cyan("yukla")} [papka]                 Qonun matnlarini bazaga yuklash
  ${c.cyan("tozala")}                        Bazani butunlay tozalash

  ${c.cyan("soragan")} <savol>               Huquqiy savolga javob
  ${c.cyan("qidir")} <soʻrov>                Bazadan qidirish (modelsiz)

  ${c.cyan("tahlil")} <fayl>                 Hujjat tahlili — xavflarni topadi
  ${c.cyan("tekshir")} <fayl>                Majburiy talablar boʻyicha tekshiruv
  ${c.cyan("yarat")} <tur> <tafsilot>        Hujjat loyihasini tayyorlash

  ${c.cyan("holat")}                         Sozlamalar holati
  ${c.cyan("yordam")}                        Shu maʼlumot

${c.bold("PARAMETRLAR")}

  --out <fayl>     Natijani faylga yozish (yarat: .docx yoki .md)
  --k <son>        Qidiruvda nechta natija (standart: 8)
  --til <uz|ru|en> Javob tili
  --json           Natijani JSON koʻrinishida chiqarish
  --tez            Tezroq va arzonroq javob (fikrlash chuqurligi past)

${c.bold("HUJJAT TURLARI")}

  mehnat-shartnomasi, ijara-shartnomasi, oldi-sotdi-shartnomasi,
  xizmat-korsatish-shartnomasi, pudrat-shartnomasi, davo-arizasi,
  ishonchnoma, tilxat, ariza, pretenziya, erkin

${c.bold("MISOLLAR")}

  npm run cli -- yukla
  npm run cli -- soragan "Sinov muddati necha oy boʻlishi mumkin?"
  npm run cli -- tahlil ~/Downloads/shartnoma.pdf
  npm run cli -- yarat ijara-shartnomasi "Toshkent, 2 xonali, oyiga 5 mln" --out ijara.docx
`;

async function cmdCorpus(): Promise<void> {
  const s = stats();
  if (s.chunks === 0) {
    out(c.yellow("Qonun bazasi boʻsh."));
    out(`Matnlarni ${c.cyan(config.corpusDir)} papkasiga joylang, soʻng: npm run ingest`);
    return;
  }
  out(c.bold("Qonun bazasi"));
  out(`  Jami boʻlaklar : ${s.chunks}`);
  out(`  Embedder       : ${s.embedder ?? "nomaʼlum"}${s.dim ? ` (${s.dim} oʻlcham)` : ""}`);
  out(`  Baza fayli     : ${config.corpusDbPath}`);
  out();
  out(c.bold("Hujjatlar"));
  for (const d of s.documents) {
    out(`  ${d.chunks.toString().padStart(5)}  ${d.document}`);
  }
}

async function cmdIngest(args: Args): Promise<void> {
  const dir = args.positional[0] ?? config.corpusDir;
  out(`Papka: ${c.cyan(dir)}`);
  out(`Embedder: ${c.cyan(config.embeddingProvider)}`);
  if (config.embeddingProvider === "local") {
    out(
      c.yellow(
        "Diqqat: `local` embedder sinov uchun. Sifatli qidiruv uchun VOYAGE_API_KEY qoʻshing.",
      ),
    );
  }
  out();

  const summary = await ingestDirectory(dir, {
    replace: true,
    onProgress: (p) => out(`  ${c.green("✓")} ${p.file} → ${p.chunks} boʻlak`),
  });

  out();
  out(
    `${c.green("Tayyor.")} ${summary.files} fayl, ${summary.chunks} boʻlak, ` +
      `${summary.documents.length} hujjat.`,
  );
  if (summary.skipped.length) {
    out(c.dim(`Oʻtkazib yuborildi: ${summary.skipped.join(", ")}`));
  }
}

async function cmdAsk(args: Args): Promise<void> {
  const question = args.positional.join(" ").trim();
  if (!question) {
    out(c.red("Savol koʻrsatilmagan."));
    out('Masalan: npm run cli -- soragan "Sinov muddati necha oy?"');
    process.exitCode = 1;
    return;
  }

  const lang = typeof args.flags.til === "string" ? args.flags.til : undefined;

  for await (const event of askStream({
    question,
    lang: lang as never,
    topK: Number(args.flags.k) || undefined,
  })) {
    switch (event.type) {
      case "status":
        process.stderr.write(c.dim(`${event.message}\n`));
        break;
      case "citations":
        if (event.citations.length) {
          process.stderr.write(c.dim(`Manbalar (${event.citations.length}):\n`));
          for (const [i, cit] of event.citations.entries()) {
            const head = [cit.document, cit.article ? `${cit.article}-modda` : null]
              .filter(Boolean)
              .join(" · ");
            process.stderr.write(c.dim(`  [${i + 1}] ${head}\n`));
          }
          process.stderr.write("\n");
        }
        break;
      case "delta":
        process.stdout.write(event.text);
        break;
      case "done":
        out();
        if (event.usage) {
          process.stderr.write(
            c.dim(
              `\n${event.usage.inputTokens} kirish / ${event.usage.outputTokens} chiqish token\n`,
            ),
          );
        }
        break;
      case "error":
        out();
        out(c.red(event.message));
        process.exitCode = 1;
        break;
    }
  }
}

async function cmdSearch(args: Args): Promise<void> {
  const query = args.positional.join(" ").trim();
  if (!query) {
    out(c.red("Soʻrov koʻrsatilmagan."));
    process.exitCode = 1;
    return;
  }

  const results = await retrieve(query, { topK: Number(args.flags.k) || 8 });

  if (args.flags.json) {
    out(JSON.stringify(results, null, 2));
    return;
  }

  if (results.length === 0) {
    out(c.yellow("Hech narsa topilmadi."));
    return;
  }

  for (const [i, r] of results.entries()) {
    const head = [r.document, r.article ? `${r.article}-modda` : null, r.heading]
      .filter(Boolean)
      .join(" · ");
    out(`${c.bold(`[${i + 1}]`)} ${head}  ${c.dim(r.score.toFixed(3))}`);
    out(c.dim(r.text.slice(0, 300).replace(/\n/g, " ") + (r.text.length > 300 ? "…" : "")));
    if (r.url) out(c.dim(r.url));
    out();
  }
}

async function readDocument(path: string): Promise<{ text: string; name: string }> {
  const buffer = await readFile(path);
  const name = basename(path);
  return { text: await extractText(buffer, name), name };
}

async function cmdAnalyze(args: Args): Promise<void> {
  const path = args.positional[0];
  if (!path) {
    out(c.red("Fayl koʻrsatilmagan."));
    process.exitCode = 1;
    return;
  }

  const { text, name } = await readDocument(path);
  process.stderr.write(c.dim(`Tahlil qilinmoqda: ${name}\n\n`));

  const result = await analyze({
    text,
    filename: name,
    lang: (args.flags.til as never) ?? undefined,
  });

  if (args.flags.json) {
    out(JSON.stringify(result, null, 2));
    return;
  }

  out(c.bold(`📄 ${result.documentType.toUpperCase()}`));
  out();
  out(result.summary);
  out();

  if (result.parties.length) {
    out(c.bold("Tomonlar"));
    for (const p of result.parties) out(`  ${p.role}: ${p.name}`);
    out();
  }

  if (result.keyTerms.length) {
    out(c.bold("Muhim shartlar"));
    for (const k of result.keyTerms) out(`  ${k.label}: ${k.value}`);
    out();
  }

  out(c.bold(`Xavflar (${result.risks.length})`));
  if (result.risks.length === 0) out(c.green("  Jiddiy xavf aniqlanmadi."));
  for (const [i, risk] of result.risks.entries()) {
    const color =
      risk.level === "yuqori" ? c.red : risk.level === "oʻrta" ? c.yellow : c.green;
    out();
    out(`  ${color(`${i + 1}. ${risk.title} [${risk.level}]`)}`);
    if (risk.location) out(`     ${c.dim(`Joyi: ${risk.location}`)}`);
    out(`     ${risk.explanation}`);
    out(`     ${c.green("→")} ${risk.recommendation}`);
    if (risk.legalBasis) out(`     ${c.dim(`📖 ${risk.legalBasis}`)}`);
  }
  out();

  if (result.missingClauses.length) {
    out(c.bold("Yetishmayotgan shartlar"));
    for (const m of result.missingClauses) out(`  • ${m}`);
    out();
  }

  out(c.bold("Xulosa"));
  out(result.conclusion);
  out();
  out(c.dim("⚠️  Bu — maʼlumot uchun tahlil, yuridik maslahat emas."));
}

async function cmdReview(args: Args): Promise<void> {
  const path = args.positional[0];
  if (!path) {
    out(c.red("Fayl koʻrsatilmagan."));
    process.exitCode = 1;
    return;
  }

  const { text, name } = await readDocument(path);
  process.stderr.write(c.dim(`Tekshirilmoqda: ${name}\n\n`));

  const result = await review({ text, filename: name });

  if (args.flags.json) {
    out(JSON.stringify(result, null, 2));
    return;
  }

  const icon: Record<string, string> = {
    "oʻtdi": c.green("✓"),
    ogohlantirish: c.yellow("!"),
    "oʻtmadi": c.red("✗"),
    aniqlanmadi: c.dim("?"),
  };

  out(c.bold(`Umumiy baho: ${result.score}/100`));
  out();
  for (const check of result.checks) {
    out(`${icon[check.status] ?? "?"} ${check.title}`);
    out(`   ${c.dim(check.detail)}`);
    if (check.legalBasis) out(`   ${c.dim(`📖 ${check.legalBasis}`)}`);
  }
  out();
  out(c.bold("Xulosa"));
  out(result.summary);
}

async function cmdGenerate(args: Args): Promise<void> {
  const [template, ...rest] = args.positional;
  const details = rest.join(" ").trim();

  if (!template) {
    out(c.red("Hujjat turi koʻrsatilmagan."));
    out("Turlar roʻyxatini koʻrish: npm run cli -- yordam");
    process.exitCode = 1;
    return;
  }
  if (!details) {
    out(c.red("Tafsilotlar koʻrsatilmagan."));
    process.exitCode = 1;
    return;
  }

  process.stderr.write(c.dim("Hujjat tayyorlanmoqda…\n\n"));

  const result = await generate({
    template: template as DocTemplateId,
    details,
    lang: (args.flags.til as never) ?? undefined,
  });

  const outPath = typeof args.flags.out === "string" ? args.flags.out : undefined;

  if (outPath?.endsWith(".docx")) {
    await writeFile(outPath, await resultToDocx(result));
    out(c.green(`Saqlandi: ${outPath}`));
  } else if (outPath) {
    await writeFile(outPath, result.markdown, "utf8");
    out(c.green(`Saqlandi: ${outPath}`));
  } else {
    out(result.markdown);
  }

  if (result.placeholders.length) {
    process.stderr.write(
      `\n${c.yellow("Toʻldirilishi kerak:")} ${result.placeholders.join(", ")}\n`,
    );
  }
  process.stderr.write(
    c.dim("\n⚠️  Bu — loyiha. Imzolashdan oldin yuristga koʻrsating.\n"),
  );
}

async function cmdStatus(): Promise<void> {
  out(c.bold("Sozlamalar"));
  out(`  Model            : ${config.model}`);
  out(`  Fikrlash (effort): ${config.effort}`);
  out(`  Til              : ${config.lang}`);
  out(`  Yozuv            : ${config.script}`);
  out(
    `  ANTHROPIC_API_KEY: ${config.anthropicApiKey ? c.green("bor") : c.red("yoʻq")}`,
  );
  out(`  Embedding        : ${config.embeddingProvider}`);
  out(
    `  VOYAGE_API_KEY   : ${config.voyageApiKey ? c.green("bor") : c.dim("yoʻq")}`,
  );
  out(
    `  Telegram token   : ${config.telegramToken ? c.green("bor") : c.dim("yoʻq")}`,
  );
  out(`  Korpus papkasi   : ${config.corpusDir}`);
  out(`  Baza fayli       : ${config.corpusDbPath}`);
}

// ── Kirish nuqtasi ─────────────────────────────────────────────────────────

const COMMANDS: Record<string, (args: Args) => Promise<void>> = {
  baza: cmdCorpus,
  corpus: cmdCorpus,
  yukla: cmdIngest,
  ingest: cmdIngest,
  soragan: cmdAsk,
  sora: cmdAsk,
  ask: cmdAsk,
  qidir: cmdSearch,
  search: cmdSearch,
  tahlil: cmdAnalyze,
  analyze: cmdAnalyze,
  tekshir: cmdReview,
  review: cmdReview,
  yarat: cmdGenerate,
  generate: cmdGenerate,
  holat: cmdStatus,
  status: cmdStatus,
  tozala: async () => {
    clearStore();
    out(c.green("Baza tozalandi."));
  },
};

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));

  if (args.command === "yordam" || args.command === "help" || args.flags.help) {
    out(HELP);
    return;
  }

  const handler = COMMANDS[args.command];
  if (!handler) {
    out(c.red(`Nomaʼlum buyruq: ${args.command}`));
    out("Buyruqlar roʻyxati: npm run cli -- yordam");
    process.exitCode = 1;
    return;
  }

  // `--tez` — arzonroq va tezroq javob.
  if (args.flags.tez) process.env.AI_LOWYER_EFFORT = "low";

  await handler(args);
}

main()
  .catch((err) => {
    out();
    out(c.red(humanError(err)));
    process.exitCode = 1;
  })
  .finally(() => {
    closeStore();
  });
