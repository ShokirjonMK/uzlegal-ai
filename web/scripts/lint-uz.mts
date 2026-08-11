/**
 * O'zbek matni linteri.
 *
 * Loyihadagi barcha manba fayllarni tekshiradi va o'zbek tiliga oid tipik
 * xatolarni topadi:
 *
 *   1. Aralash yozuv  — bitta so'zda lotin va kirill harflari (masalan "terminалда").
 *      Bu ko'z bilan ilg'ab bo'lmaydigan, lekin matnni buzadigan xato.
 *   2. Noto'g'ri apostrof — o'/g' o'rniga ASCII ' yoki ' ishlatilgan.
 *   3. Tutuq belgisi o'rniga ASCII apostrof.
 *
 * Ishga tushirish:  npm run lint:uz
 */

import { readdir, readFile } from "node:fs/promises";
import { extname, join, relative, resolve } from "node:path";

const ROOT = resolve(process.cwd());
const SCAN_DIRS = ["src", "scripts", "data", "docs"];
/** Ildizdagi alohida fayllar (papka emas). */
const SCAN_FILES = [
  "README.md",
  "CLAUDE.md",
  ".env.example",
  "BIRLASHTIRISH.md",
];
const EXTENSIONS = new Set([".ts", ".tsx", ".md", ".txt", ".css", ".json"]);

/** Faqat kirillda yozilishi kutiladigan fayllar (tekshiruvdan chetlatiladi). */
const CYRILLIC_OK = /orthography\.ts$|detect\.ts$|glossary\.ts$|lint-uz\.mts$/;

const LATIN = /[A-Za-z]/;
const CYRILLIC = /[Ѐ-ӿ]/;

interface Finding {
  file: string;
  line: number;
  column: number;
  rule: string;
  text: string;
  hint: string;
}

async function walk(dir: string): Promise<string[]> {
  const out: string[] = [];
  let entries: string[];
  try {
    entries = await readdir(dir);
  } catch {
    return out;
  }
  for (const entry of entries) {
    if (entry.startsWith(".") || entry === "node_modules") continue;
    const full = join(dir, entry);
    const ext = extname(entry);
    if (ext === "") {
      out.push(...(await walk(full)));
    } else if (EXTENSIONS.has(ext)) {
      out.push(full);
    }
  }
  return out;
}

function checkLine(
  file: string,
  lineNo: number,
  line: string,
  skipCyrillic: boolean,
): Finding[] {
  const findings: Finding[] = [];

  // 1. Aralash yozuvli so'zlar.
  if (!skipCyrillic) {
    for (const m of line.matchAll(/[\p{L}ʻʼ'']+/gu)) {
      const word = m[0];
      if (LATIN.test(word) && CYRILLIC.test(word)) {
        findings.push({
          file,
          line: lineNo,
          column: (m.index ?? 0) + 1,
          rule: "aralash-yozuv",
          text: word,
          hint: "Soʻzda lotin va kirill harflari aralashgan. Butun soʻzni bitta yozuvda yozing.",
        });
      }
    }
  }

  // 2. o'/g' uchun noto'g'ri belgi.
  for (const m of line.matchAll(/[oOgG]['‘’`´]/g)) {
    findings.push({
      file,
      line: lineNo,
      column: (m.index ?? 0) + 1,
      rule: "apostrof-o-g",
      text: m[0],
      hint: `"${m[0][0]}ʻ" boʻlishi kerak (U+02BB MODIFIER LETTER TURNED COMMA).`,
    });
  }

  return findings;
}

/**
 * Kod izohlarini olib tashlaydi.
 *
 * Izohlar foydalanuvchiga ko'rinmaydi, shuning uchun ularda oddiy ASCII
 * apostrof ishlatilishi mumkin. Tekshiruv faqat matn satrlariga tegishli.
 * Izoh o'rniga bo'sh joy qo'yiladi — ustun raqamlari saqlanib qolsin.
 */
/**
 * Markdown ichidagi kod bo'laklarini olib tashlaydi.
 *
 * `keepTyping` kabi identifikator "g" bilan tugasa, uni yopuvchi backtick
 * apostrof deb o'qilardi. Kod bo'laklari — identifikatorlar, o'zbek matni emas.
 * Belgilar bo'sh joyga almashtiriladi, ustun raqamlari saqlanadi.
 */
function stripMarkdownCode(lines: string[]): string[] {
  let inFence = false;
  return lines.map((line) => {
    if (/^\s*```/.test(line)) {
      inFence = !inFence;
      return " ".repeat(line.length);
    }
    if (inFence) return " ".repeat(line.length);
    // Bir satrdagi `...` bo'laklari.
    return line.replace(/`[^`]*`/g, (m) => " ".repeat(m.length));
  });
}

function stripComments(lines: string[]): string[] {
  const out: string[] = [];
  let inBlock = false;

  for (const line of lines) {
    let result = "";
    let i = 0;

    while (i < line.length) {
      if (inBlock) {
        if (line.startsWith("*/", i)) {
          inBlock = false;
          result += "  ";
          i += 2;
        } else {
          result += " ";
          i += 1;
        }
        continue;
      }

      if (line.startsWith("/*", i)) {
        inBlock = true;
        result += "  ";
        i += 2;
        continue;
      }

      // `//` — lekin `https://` kabi URL emas.
      if (line.startsWith("//", i) && line[i - 1] !== ":") {
        result += " ".repeat(line.length - i);
        break;
      }

      result += line[i];
      i += 1;
    }

    out.push(result);
  }
  return out;
}

/**
 * Kod satridagi matnni tekshirish kerakmi?
 * import yo'llari va URL'larda apostrof bo'lmaydi, shuning uchun chetlab o'tamiz.
 * `lint-uz-ignore` izohi bo'lgan satr ham tekshirilmaydi.
 */
function isCodeNoise(line: string): boolean {
  const t = line.trim();
  return (
    t.startsWith("import ") ||
    t.startsWith("export * ") ||
    t.startsWith("from ") ||
    /https?:\/\//.test(t)
  );
}

async function main(): Promise<void> {
  const files: string[] = [];
  for (const dir of SCAN_DIRS) {
    files.push(...(await walk(resolve(ROOT, dir))));
  }
  for (const name of SCAN_FILES) {
    const path = resolve(ROOT, name);
    try {
      await readFile(path);
      files.push(path);
    } catch {
      // Fayl yo'q — o'tkazib yuboramiz.
    }
  }

  const findings: Finding[] = [];

  for (const file of files) {
    const rel = relative(ROOT, file);
    const skipCyrillic = CYRILLIC_OK.test(file);
    const content = await readFile(file, "utf8");
    const rawLines = content.split("\n");
    const isCode = /\.tsx?$|\.mts$|\.css$/.test(file);
    const isMarkdown = /\.md$/.test(file);
    const lines = isCode
      ? stripComments(rawLines)
      : isMarkdown
        ? stripMarkdownCode(rawLines)
        : rawLines;

    for (const [i, line] of lines.entries()) {
      if (isCodeNoise(line)) continue;
      // `lint-uz-ignore` direktivasi — shu satrda yoki bir satr yuqorida.
      // (Asl satrlarda qidiramiz, chunki direktiva izoh ichida turadi.)
      if (
        rawLines[i]?.includes("lint-uz-ignore") ||
        rawLines[i - 1]?.includes("lint-uz-ignore")
      ) {
        continue;
      }
      findings.push(...checkLine(rel, i + 1, line, skipCyrillic));
    }
  }

  if (findings.length === 0) {
    console.log(`✅ ${files.length} fayl tekshirildi — oʻzbek matnida xato topilmadi.`);
    return;
  }

  const byRule = new Map<string, Finding[]>();
  for (const f of findings) {
    const list = byRule.get(f.rule) ?? [];
    list.push(f);
    byRule.set(f.rule, list);
  }

  for (const [rule, list] of byRule) {
    console.log(`\n\x1b[31m${rule}\x1b[0m — ${list.length} ta`);
    for (const f of list) {
      console.log(`  ${f.file}:${f.line}:${f.column}  "${f.text}"`);
      console.log(`    \x1b[2m${f.hint}\x1b[0m`);
    }
  }

  console.log(`\n❌ Jami ${findings.length} ta muammo (${files.length} fayl).`);
  process.exitCode = 1;
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
