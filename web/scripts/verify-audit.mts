/**
 * Audit topilmalarini amalda tekshirish.
 * Reviewer agentlar xato aytishi mumkin — har bir da'vo kod ustida sinaladi.
 */

import { chunkLegalText } from "../src/lib/rag/chunk";
import { stems } from "../src/lib/rag/retrieve";
import { foldForSearch, cyrillicToLatin } from "../src/lib/uz/orthography";
import { markdownToDocx } from "../src/lib/util/docx";

let pass = 0;
let fail = 0;

/**
 * Manbadan izohlarni olib tashlaydi.
 *
 * Bu tekshiruvlar naqsh bilan ishlaydi, izohlar esa aynan nuqsonni
 * TASVIRLAYDI («ilgari bu yerda `if (expected)` edi»). Izohlar
 * qoldirilsa, tuzatishni tushuntirgan matn tuzatilmagan kod deb
 * o'qiladi — va vosita yana yolg'on gapira boshlaydi.
 */
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^[ \t]*\/\/.*$/gm, "");
}

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
//
// DIQQAT: bu tekshiruv `retrieve.ts` dagi HAQIQIY `stems()` ni chaqiradi.
// Ilgari u `foldForSearch(...).includes(...)` ni sinardi — bu qidiruvning
// eski, allaqachon almashtirilgan mantiqi edi, shuning uchun tuzatilgan
// muammo abadiy «TASDIQLANDI» bo'lib qolardi.
{
  const chunkStems = new Set(stems("Mehnat shartnomasining bekor qilinishi tartibi"));
  const queries = ["shartnoma", "shartnomani", "shartnomaning", "shartnomalar"];
  const results = queries.map(
    (q) => `${q}=${stems(q).every((s) => chunkStems.has(s)) ? "✓" : "✗"}`,
  );
  const broken = queries.some((q) => !stems(q).every((s) => chunkStems.has(s)));
  check(
    "retrieve.ts: qo'shimchali so'rov o'zakli matnda topilmaydi (morfologiya)",
    broken,
    results.join("  "),
  );
}

// ── 4. Kirill korpus + lotin so'rov = 0 moslik ────────────────────────────
//
// Bu ham haqiqiy `stems()` ustida. `cyrillicToLatin` loyihada BOR, lekin
// `rag/store.ts` va `rag/ingest.ts` da chaqirilmaydi — nuqson aynan shu
// ulanmaganlikda, funksiyaning o'zida emas.
{
  const CYRILLIC = "Меҳнат шартномаси бекор қилиниши";
  const chunkStems = new Set(stems(CYRILLIC));
  const latQuery = ["mehnat", "shartnoma", "bekor"];

  const hits = latQuery.filter((t) => stems(t).every((s) => chunkStems.has(s)));
  const afterStems = new Set(stems(cyrillicToLatin(CYRILLIC)));
  const hitsAfter = latQuery.filter((t) => stems(t).every((s) => afterStems.has(s)));

  check(
    "store.ts: kirill matn lotin so'rov bilan topilmaydi (translit ulanmagan)",
    hits.length === 0,
    `hozir: ${hits.length}/3 moslik | translitdan keyin: ${hitsAfter.length}/3`,
  );
}

// ── 5. .docx pastki chiziqni o'chiradi → to'ldirish joyi buziladi ─────────
{
  // .docx — zip, matn siqilgan, shuning uchun natijani to'g'ridan-to'g'ri
  // o'qib bo'lmaydi. Ilgari bu yerda tozalash regexi QO'LDA takrorlangan
  // edi — ya'ni tekshiruv `docx.ts` ni umuman ko'rmasdi va u tuzatilsa
  // ham «TASDIQLANDI» deb qolaverardi. Endi regex MANBADAN olinadi.
  const buf = await markdownToDocx("Ijarachi: {{TOMON_NOMI}} va {{IJARA_HAQI}}", "Test");
  const src = await import("node:fs").then((fs) =>
    fs.readFileSync("src/lib/util/docx.ts", "utf8"),
  );
  const pattern = /part\.replace\((\/\[[^/]*\]\/g)/.exec(stripComments(src))?.[1];
  if (!pattern) throw new Error("docx.ts dagi tozalash regexi topilmadi");

  const cleaner = new Function(`return (s) => s.replace(${pattern}, "");`)() as (
    s: string,
  ) => string;
  const stripped = cleaner("{{TOMON_NOMI}}");

  check(
    "docx.ts: {{TOMON_NOMI}} dagi pastki chiziq o'chib ketadi",
    stripped !== "{{TOMON_NOMI}}",
    `regex ${pattern}: "{{TOMON_NOMI}}" → "${stripped}"  (docx hajmi: ${buf.length} bayt)`,
  );
}

// ── 6. topK validatsiyasi yo'q ────────────────────────────────────────────
//
// Bu topilma BIRLASHTIRISHDAN KEYIN eskirdi: `ask.ts` endi qidiruvni
// o'zi bajarmaydi, u `POST /v1/consult` ga uzatadi va `topK` degan
// maydonni umuman qabul qilmaydi. Tekshiruv shuni tasdiqlaydi — agar
// kimdir kelajakda `topK` ni qaytarib olib kelsa, chegarasiz holat
// yana ushlanadi.
{
  const src = await import("node:fs").then((fs) =>
    fs.readFileSync("src/lib/services/ask.ts", "utf8"),
  );
  const usesTopK = /\btopK\b/.test(src);
  const hasClamp = /Math\.min[\s\S]{0,80}topK|topK[\s\S]{0,40}Math\.min/.test(src);
  check(
    "ask.ts: topK cheklanmagan (butun korpus promptga tushishi mumkin)",
    usesTopK && !hasClamp,
    usesTopK
      ? hasClamp
        ? "clamp topildi"
        : "topK ishlatiladi, lekin yuqori chegara yo'q"
      : "ask.ts topK ni umuman qabul qilmaydi — qidiruv yadroda (/v1/consult)",
  );
}

// ── 7. Webhook siri majburiy emas (fail-open) ─────────────────────────────
{
  const src = await import("node:fs").then((fs) =>
    fs.readFileSync("src/app/api/telegram/route.ts", "utf8"),
  );
  // Izohlar olib tashlanadi: aks holda nuqsonni TASVIRLAYDIGAN izoh
  // nuqsonning o'zi deb o'qiladi. Bu aynan shu yerda sodir bo'lgan edi.
  const code = stripComments(src);
  const failClosed = /if\s*\(\s*!\s*expected\s*\)/.test(code);
  check(
    "telegram/route.ts: sir sozlanmagan bo'lsa tekshiruv butunlay o'tkazib yuboriladi",
    !failClosed,
    failClosed
      ? "`if (!expected) → 503` — sirsiz holatda marshrut ishlamaydi (fail-closed)"
      : "sirsiz holatda hech narsa tekshirilmaydi (fail-open)",
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
  // Oyna 300 belgi edi va funksiya undan uzunroq bo'lgach naqsh umuman
  // mos kelmay qoldi — bo'sh satr esa "parse_mode yo'q" deb o'qilardi.
  // Endi funksiya tanasi yopuvchi qavsgacha to'liq olinadi.
  const code = stripComments(src);
  const replyLong = /async function replyLong[\s\S]*?\n}/.exec(code)?.[0] ?? "";
  const hasParseMode = replyLong.includes("parse_mode");
  check(
    "bot.ts: replyLong parse_mode bermaydi → foydalanuvchi **yulduzcha** ko'radi",
    replyLong === "" || !hasParseMode,
    replyLong === ""
      ? "replyLong topilmadi — tekshiruvni yangilash kerak"
      : hasParseMode
        ? "parse_mode bor (HTML), xato bo'lsa belgilashsiz qayta yuboriladi"
        : "replyLong da parse_mode yo'q",
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
//
// DIQQAT: ilgari bu yerda `normalizeStatus` NUSXASI yozilgan edi.
// Ya'ni tekshiruv haqiqiy kodni emas, o'zi yozgan taqlidni sinardi —
// asl funksiya tuzatilsa ham natija o'zgarmasdi. Endi `review.ts`
// manbasidan funksiya ajratib olinadi va AYNAN U bajariladi.
{
  const src = await import("node:fs").then((fs) =>
    fs.readFileSync("src/lib/services/review.ts", "utf8"),
  );
  const body = /function normalizeStatus\(s: string\): CheckStatus \{[\s\S]*?\n}/.exec(src)?.[0];
  if (!body) throw new Error("normalizeStatus topilmadi — tekshiruvni yangilash kerak");

  // TypeScript tip belgilarini olib tashlab, funksiyani jonlantiramiz.
  const js = body
    .replace(/: CheckStatus\[\]/g, "")
    .replace(/: CheckStatus/g, "")
    .replace(/: string/g, "")
    .replace(/ as string\[\]/g, "")
    .replace(/ as CheckStatus/g, "");
  const normalize = new Function(`${js}; return normalizeStatus;`)() as (s: string) => string;

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
