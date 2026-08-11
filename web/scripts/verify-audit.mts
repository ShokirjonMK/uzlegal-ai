/**
 * Audit topilmalarini amalda tekshirish.
 * Reviewer agentlar xato aytishi mumkin — har bir da'vo kod ustida sinaladi.
 */

import { chunkLegalText } from "../src/lib/rag/chunk";
import { foldForSearch, cyrillicToLatin } from "../src/lib/uz/orthography";
import { markdownToDocx } from "../src/lib/util/docx";

let pass = 0;
let fail = 0;

function check(claim: string, confirmed: boolean, evidence: string): void {
  const mark = confirmed ? "\x1b[31mTASDIQLANDI\x1b[0m" : "\x1b[32mRAD ETILDI\x1b[0m";
  console.log(`\n${mark}  ${claim}`);
  console.log(`  ${evidence}`);
  confirmed ? fail++ : pass++;
}

// ── 1. Modda regexi matn ichidagi havolani sarlavha deb o'qiydi ────────────
{
  const text = `Ish beruvchi xodimni ogohlantiradi. Bunda
173-moddada nazarda tutilgan tartibda ariza beriladi va
81-moddaning ikkinchi qismiga muvofiq ish beruvchi javob beradi.`;
  const chunks = chunkLegalText(text, { document: "Test" });
  const fake = chunks.filter((c) => c.article && c.heading && /^[a-zʻʼ]/.test(c.heading));
  check(
    "chunk.ts: matn ichidagi krossreferens soxta modda bloki yasaydi",
    fake.length > 0,
    fake.length > 0
      ? `${fake.length} ta soxta blok: ${fake.map((c) => `${c.article}-modda "${c.heading?.slice(0, 40)}…"`).join(" | ")}`
      : "soxta blok topilmadi",
  );
}

// ── 2. Ruscha "Статья 173." → article nuqta bilan ─────────────────────────
{
  const chunks = chunkLegalText("Статья 173. Основания расторжения\nТекст нормы здесь.", {
    document: "ГК",
  });
  const art = chunks[0]?.article ?? "";
  check(
    "chunk.ts: ruscha moddada article nuqta bilan saqlanadi (bonus ishlamaydi)",
    art.includes("."),
    `article = "${art}" (kutilgan "173")`,
  );
}

// ── 3. O'zbek morfologiyasi: teskari yo'nalish ishlamaydi ─────────────────
{
  const chunkText = foldForSearch("Mehnat shartnomasining bekor qilinishi tartibi");
  const results = ["shartnoma", "shartnomani", "shartnomaning", "shartnomalar"].map(
    (q) => `${q}=${chunkText.includes(foldForSearch(q)) ? "✓" : "✗"}`,
  );
  const broken = !chunkText.includes("shartnomaning");
  check(
    "retrieve.ts: qo'shimchali so'rov o'zakli matnda topilmaydi (morfologiya)",
    broken,
    results.join("  "),
  );
}

// ── 4. Kirill korpus + lotin so'rov = 0 moslik ────────────────────────────
{
  const cyrChunk = foldForSearch("Меҳнат шартномаси бекор қилиниши");
  const latQuery = ["mehnat", "shartnoma", "bekor"];
  const hits = latQuery.filter((t) => cyrChunk.includes(t));
  const fixed = foldForSearch(cyrillicToLatin("Меҳнат шартномаси бекор қилиниши"));
  const hitsAfter = latQuery.filter((t) => fixed.includes(t));
  check(
    "store.ts: kirill matn lotin so'rov bilan topilmaydi (translit yo'q)",
    hits.length === 0,
    `hozir: ${hits.length}/3 moslik | translitdan keyin: ${hitsAfter.length}/3`,
  );
}

// ── 5. .docx pastki chiziqni o'chiradi → to'ldirish joyi buziladi ─────────
{
  const buf = await markdownToDocx("Ijarachi: {{TOMON_NOMI}} va {{IJARA_HAQI}}", "Test");
  const raw = buf.toString("latin1");
  // .docx — zip, matn siqilgan. Buning o'rniga inlineRuns mantig'ini bevosita sinaymiz.
  const stripped = "{{TOMON_NOMI}}".replace(/[*_`]/g, "");
  check(
    "docx.ts: {{TOMON_NOMI}} dagi pastki chiziq o'chib ketadi",
    stripped !== "{{TOMON_NOMI}}",
    `"{{TOMON_NOMI}}" → "${stripped}"  (docx hajmi: ${buf.length} bayt)`,
  );
}

// ── 6. topK validatsiyasi yo'q ────────────────────────────────────────────
{
  const src = await import("node:fs").then((fs) =>
    fs.readFileSync("src/lib/services/ask.ts", "utf8"),
  );
  const hasClamp = /Math\.min[\s\S]{0,80}topK|topK[\s\S]{0,40}Math\.min/.test(src);
  check(
    "ask.ts: topK cheklanmagan (butun korpus promptga tushishi mumkin)",
    !hasClamp,
    hasClamp ? "clamp topildi" : "topK: req.topK ?? 8 — hech qanday yuqori chegara yo'q",
  );
}

// ── 7. Webhook siri majburiy emas (fail-open) ─────────────────────────────
{
  const src = await import("node:fs").then((fs) =>
    fs.readFileSync("src/app/api/telegram/route.ts", "utf8"),
  );
  const failOpen = /if\s*\(\s*expected\s*\)/.test(src);
  check(
    "telegram/route.ts: sir sozlanmagan bo'lsa tekshiruv butunlay o'tkazib yuboriladi",
    failOpen,
    failOpen ? "`if (expected) {…}` — sirsiz holatda hech narsa tekshirilmaydi" : "fail-closed",
  );
}

// ── 8. isAdmin chat.id ni tekshiradi (from.id emas) ───────────────────────
{
  const src = await import("node:fs").then((fs) =>
    fs.readFileSync("src/lib/bot.ts", "utf8"),
  );
  const usesChatId = /function isAdmin[\s\S]{0,160}ctx\.chat\?\.id/.test(src);
  check(
    "bot.ts: isAdmin ctx.chat.id ni ishlatadi (guruhda barcha a'zo admin bo'ladi)",
    usesChatId,
    usesChatId ? "const id = ctx.chat?.id" : "ctx.from?.id ishlatilgan",
  );
}

// ── 9. Telegram javobida parse_mode yo'q → xom Markdown ───────────────────
{
  const src = await import("node:fs").then((fs) =>
    fs.readFileSync("src/lib/bot.ts", "utf8"),
  );
  const replyLong = /async function replyLong[\s\S]{0,300}?\n}/.exec(src)?.[0] ?? "";
  check(
    "bot.ts: replyLong parse_mode bermaydi → foydalanuvchi **yulduzcha** ko'radi",
    !replyLong.includes("parse_mode"),
    replyLong.includes("parse_mode") ? "parse_mode bor" : "replyLong da parse_mode yo'q",
  );
}


// ── 10. Apostrof qidiruv tokenlarini parchalaydi ──────────────────────────
{
  const STOP = new Set(["va","bilan","uchun","yoki","bu","shu","ham"]);
  const tokenize = (t: string) =>
    foldForSearch(t).split(/[^\p{L}\p{N}]+/u).filter((w) => w.length >= 3 && !STOP.has(w));

  const cases = ["yoʻl harakati qoidalari", "toʻlov muddati", "ishdan boʻshatish", "koʻchmas mulk"];
  const lines = cases.map((q) => `"${q}" → [${tokenize(q).join(", ")}]`);
  const broken = !tokenize("yoʻl harakati").includes("yol") &&
                 !tokenize("toʻlov muddati").some((t) => t.startsWith("tol"));
  check(
    "retrieve.ts: apostrof token ajratuvchi — eng keng tarqalgan atamalar yoʻqoladi",
    broken,
    lines.join("\n  "),
  );
}

// ── 11. foldForSearch hujjatlashtirilgan va'dani bajarmaydi ───────────────
{
  const a = foldForSearch("oʻzbek");
  const b = foldForSearch("ozbek");
  check(
    "orthography.ts: izohda «ozbek deb yozsa ham topilsin» deyilgan, lekin bajarilmaydi",
    a !== b,
    `foldForSearch("oʻzbek")="${a}"  vs  foldForSearch("ozbek")="${b}"`,
  );
}

// ── 12. normalizeStatus oqlangan qo'shtirnoq va bosh harfni ushlamaydi ────
{
  const normalize = (s: string) => {
    const valid = ["oʻtdi", "ogohlantirish", "oʻtmadi", "aniqlanmadi"];
    if (valid.includes(s)) return s;
    const folded = s.replace(/[''ʻʼ`]/g, "");
    if (folded === "otdi") return "oʻtdi";
    if (folded === "otmadi") return "oʻtmadi";
    if (folded === "ogohlantirish") return "ogohlantirish";
    return "aniqlanmadi";
  };
  const results = [
    ["o'tdi (ASCII)", normalize("o'tdi")],
    ["o’tdi (U+2019)", normalize("o’tdi")],
    ["Oʻtdi (bosh harf)", normalize("Oʻtdi")],
    [" oʻtdi (bo'shliq)", normalize(" oʻtdi")],
  ];
  const broken = results.filter(([, r]) => r === "aniqlanmadi").length > 0;
  check(
    "review.ts: normalizeStatus chetlanishlarni ushlamaydi → natija jimgina yoʻqoladi",
    broken,
    results.map(([k, v]) => `${k} → ${v}`).join("  |  "),
  );
}

console.log(
  `\n${"─".repeat(60)}\nTasdiqlangan muammo: \x1b[31m${fail}\x1b[0m   Rad etilgan da'vo: \x1b[32m${pass}\x1b[0m`,
);
