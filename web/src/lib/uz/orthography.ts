/**
 * O'zbek tili orfografiyasi: apostroflar, yozuv (skript) aniqlash va translitteratsiya.
 *
 * Rasmiy o'zbek lotin alifbosida ikkita turli belgi ishlatiladi va ular
 * klaviaturadagi oddiy apostrof (') EMAS:
 *
 *   ʻ  U+02BB  MODIFIER LETTER TURNED COMMA  →  oʻ, gʻ  (harf tarkibiy qismi)
 *   ʼ  U+02BC  MODIFIER LETTER APOSTROPHE    →  tutuq belgisi: maʼno, sanʼat
 *
 * Foydalanuvchilar odatda ' yoki ' yoki ` yozadi. Model chiqarishida ham
 * aralashib ketishi mumkin. Bu modul hamma variantni to'g'ri belgiga keltiradi.
 */

/** U+02BB — oʻ va gʻ tarkibidagi belgi. */
export const TURNED_COMMA = "ʻ";
/** U+02BC — tutuq belgisi (maʼno, sanʼat, taʼsir). */
export const MODIFIER_APOSTROPHE = "ʼ";

/** Apostrof sifatida yozilishi mumkin bo'lgan barcha belgilar. */
const APOSTROPHE_VARIANTS = [
  "'", // ' ASCII apostrof
  "‘", // ' chap burchakli qo'shtirnoq
  "’", // ' o'ng burchakli qo'shtirnoq
  "‛", // ‛
  "`", // ` grave
  "´", // ´ acute
  "ʹ", // ʹ
  "ʻ", // ʻ (allaqachon to'g'ri, lekin joyi noto'g'ri bo'lishi mumkin)
  "ʼ", // ʼ
  "ˈ", // ˈ
  "′", // ′ prime
];

const APOSTROPHE_CLASS = `[${APOSTROPHE_VARIANTS.join("")}]`;

/**
 * Matndagi apostroflarni o'zbek orfografiyasi bo'yicha to'g'rilaydi.
 *
 * - o/O/g/G dan keyin kelsa → ʻ (oʻzbek, gʻalaba, Oʻzbekiston)
 * - qolgan barcha holatda   → ʼ (maʼno, sanʼat, taʼsir, sunʼiy)
 *
 * Ingliz tilidagi qisqartmalar (don't, it's) buzilmasligi uchun
 * `skipLatinContractions` yoqilganda ASCII apostrof lotin harflari orasida
 * `s`, `t`, `re`, `ve`, `ll`, `d`, `m` dan oldin kelsa tegilmaydi.
 */
export function fixApostrophes(
  input: string,
  opts: { skipLatinContractions?: boolean } = {},
): string {
  if (!input) return input;
  const { skipLatinContractions = false } = opts;

  let out = input;

  // Ingliz qisqartmalarini (don' t, it' s) himoyalash uchun vaqtinchalik
  // joy egallovchi belgi — Unicode Private Use Area, oddiy matnda uchramaydi.
  const PLACEHOLDER = "\uE000";

  if (skipLatinContractions) {
    out = out.replace(
      /([A-Za-z])'(s|t|re|ve|ll|d|m)\b/g,
      (_m, a: string, b: string) => `${a}${PLACEHOLDER}${b}`,
    );
  }

  // Bitta o'tishda: oldingi harfga qarab to'g'ri belgini tanlaymiz.
  // Ikki bosqichda qilib bo'lmaydi — ʻ ning o'zi ham "apostrof variantlari"
  // ro'yxatida, shuning uchun ikkinchi bosqich birinchisining natijasini buzadi.
  out = out.replace(
    new RegExp(`(.?)${APOSTROPHE_CLASS}`, "gs"),
    (_m, prev: string) =>
      /[oOgG]/.test(prev)
        ? `${prev}${TURNED_COMMA}` // oʻ, gʻ — harf tarkibiy qismi
        : `${prev}${MODIFIER_APOSTROPHE}`, // tutuq belgisi: maʼno, sanʼat
  );

  if (skipLatinContractions) {
    out = out.split(PLACEHOLDER).join("'");
  }

  return out;
}

/**
 * Qidiruv va taqqoslash uchun: apostrofni BUTUNLAY olib tashlaydi va matnni
 * kichik harfga o'tkazadi. `oʻzbek`, `o'zbek`, `ozbek` — uchalasi ham `ozbek`.
 *
 * NEGA OLIB TASHLANADI, ASCII `'` GA KELTIRILMAYDI. Ilgari apostrof `'` ga
 * aylantirilardi, keyin esa tokenlashtirish `\p{L}` bo'lmagan har qanday
 * belgi bo'yicha bo'lardi — ya'ni apostrof so'zni ikkiga yorib yuborardi:
 *
 *     yo'l   → "yo" + "l"  → ikkalasi ham 3 belgidan qisqa → SO'Z YO'QOLADI
 *     to'lov → "to" + "lov" → qidiruvda "lov" qoladi
 *     bo'shatish → "shatish"
 *
 * Ya'ni eng ko'p uchraydigan o'zbek yuridik atamalari qidiruvda yarim yoki
 * umuman ishlamasdi (audit #10a). Apostrofni olib tashlash ham shuni, ham
 * "ozbek" deb yozgan foydalanuvchini topish vazifasini (#10b) hal qiladi.
 *
 * DIQQAT: bu funksiya lokal embedder va `chunks.folded` ustuniga ham ta'sir
 * qiladi. O'zgargandan keyin korpusni QAYTA yuklash kerak.
 */
export function foldForSearch(input: string): string {
  return input
    .replace(new RegExp(APOSTROPHE_CLASS, "g"), "")
    .toLocaleLowerCase("uz");
}

// ── Yozuv (skript) aniqlash ────────────────────────────────────────────────

export type Script = "latn" | "cyrl";

const CYRILLIC_RE = /[Ѐ-ӿ]/g;
const LATIN_RE = /[A-Za-z]/g;

/** Matn kirillmi yoki lotinmi? Harflar sonini solishtiradi. */
export function detectScript(input: string): Script {
  const cyr = input.match(CYRILLIC_RE)?.length ?? 0;
  const lat = input.match(LATIN_RE)?.length ?? 0;
  return cyr > lat ? "cyrl" : "latn";
}

// ── Translitteratsiya ──────────────────────────────────────────────────────

/** Kirill → lotin. Ko'p belgili mosliklar avval keladi. */
const CYRL_TO_LATN: Array<[string, string]> = [
  ["Ў", `O${TURNED_COMMA}`],
  ["ў", `o${TURNED_COMMA}`],
  ["Ғ", `G${TURNED_COMMA}`],
  ["ғ", `g${TURNED_COMMA}`],
  ["Ё", "Yo"],
  ["ё", "yo"],
  ["Ю", "Yu"],
  ["ю", "yu"],
  ["Я", "Ya"],
  ["я", "ya"],
  ["Ч", "Ch"],
  ["ч", "ch"],
  ["Ш", "Sh"],
  ["ш", "sh"],
  ["Ц", "Ts"],
  ["ц", "ts"],
  ["Қ", "Q"],
  ["қ", "q"],
  ["Ҳ", "H"],
  ["ҳ", "h"],
  ["Х", "X"],
  ["х", "x"],
  ["Ж", "J"],
  ["ж", "j"],
  ["Ъ", MODIFIER_APOSTROPHE],
  ["ъ", MODIFIER_APOSTROPHE],
  ["Ь", ""],
  ["ь", ""],
  ["А", "A"],
  ["а", "a"],
  ["Б", "B"],
  ["б", "b"],
  ["В", "V"],
  ["в", "v"],
  ["Г", "G"],
  ["г", "g"],
  ["Д", "D"],
  ["д", "d"],
  ["Е", "E"],
  ["е", "e"],
  ["З", "Z"],
  ["з", "z"],
  ["И", "I"],
  ["и", "i"],
  ["Й", "Y"],
  ["й", "y"],
  ["К", "K"],
  ["к", "k"],
  ["Л", "L"],
  ["л", "l"],
  ["М", "M"],
  ["м", "m"],
  ["Н", "N"],
  ["н", "n"],
  ["О", "O"],
  ["о", "o"],
  ["П", "P"],
  ["п", "p"],
  ["Р", "R"],
  ["р", "r"],
  ["С", "S"],
  ["с", "s"],
  ["Т", "T"],
  ["т", "t"],
  ["У", "U"],
  ["у", "u"],
  ["Ф", "F"],
  ["ф", "f"],
  ["Э", "E"],
  ["э", "e"],
  ["Ы", "I"],
  ["ы", "i"],
];

/** Lotin → kirill. Digraflar avval. */
const LATN_TO_CYRL: Array<[string, string]> = [
  [`O${TURNED_COMMA}`, "Ў"],
  [`o${TURNED_COMMA}`, "ў"],
  [`G${TURNED_COMMA}`, "Ғ"],
  [`g${TURNED_COMMA}`, "ғ"],
  ["Yo", "Ё"],
  ["yo", "ё"],
  ["YO", "Ё"],
  ["Yu", "Ю"],
  ["yu", "ю"],
  ["YU", "Ю"],
  ["Ya", "Я"],
  ["ya", "я"],
  ["YA", "Я"],
  ["Ch", "Ч"],
  ["ch", "ч"],
  ["CH", "Ч"],
  ["Sh", "Ш"],
  ["sh", "ш"],
  ["SH", "Ш"],
  ["Ts", "Ц"],
  ["ts", "ц"],
  ["A", "А"],
  ["a", "а"],
  ["B", "Б"],
  ["b", "б"],
  ["V", "В"],
  ["v", "в"],
  ["G", "Г"],
  ["g", "г"],
  ["D", "Д"],
  ["d", "д"],
  ["E", "Е"],
  ["e", "е"],
  ["J", "Ж"],
  ["j", "ж"],
  ["Z", "З"],
  ["z", "з"],
  ["I", "И"],
  ["i", "и"],
  ["Y", "Й"],
  ["y", "й"],
  ["K", "К"],
  ["k", "к"],
  ["Q", "Қ"],
  ["q", "қ"],
  ["L", "Л"],
  ["l", "л"],
  ["M", "М"],
  ["m", "м"],
  ["N", "Н"],
  ["n", "н"],
  ["O", "О"],
  ["o", "о"],
  ["P", "П"],
  ["p", "п"],
  ["R", "Р"],
  ["r", "р"],
  ["S", "С"],
  ["s", "с"],
  ["T", "Т"],
  ["t", "т"],
  ["U", "У"],
  ["u", "у"],
  ["F", "Ф"],
  ["f", "ф"],
  ["X", "Х"],
  ["x", "х"],
  ["H", "Ҳ"],
  ["h", "ҳ"],
  [MODIFIER_APOSTROPHE, "ъ"],
];

function applyMap(input: string, map: Array<[string, string]>): string {
  let out = "";
  let i = 0;
  outer: while (i < input.length) {
    for (const [from, to] of map) {
      if (from.length > 0 && input.startsWith(from, i)) {
        out += to;
        i += from.length;
        continue outer;
      }
    }
    out += input[i];
    i += 1;
  }
  return out;
}

/** Kirill yozuvidagi o'zbekchani lotinga o'giradi. */
export function cyrillicToLatin(input: string): string {
  return applyMap(input, CYRL_TO_LATN);
}

/** Lotin yozuvidagi o'zbekchani kirillga o'giradi. */
export function latinToCyrillic(input: string): string {
  return applyMap(fixApostrophes(input), LATN_TO_CYRL);
}

/** Matnni kerakli yozuvga keltiradi. */
export function toScript(input: string, script: Script): string {
  const current = detectScript(input);
  if (current === script) {
    return script === "latn" ? fixApostrophes(input) : input;
  }
  return script === "latn" ? cyrillicToLatin(input) : latinToCyrillic(input);
}

// ── Yakuniy tozalash ───────────────────────────────────────────────────────

/**
 * Model chiqargan o'zbekcha matnni yakuniy tozalash.
 * Faqat xavfsiz, ma'noga tegmaydigan tuzatishlar.
 */
export function polishUzbek(text: string): string {
  let out = fixApostrophes(text);

  // Tinish belgilaridan oldingi ortiqcha bo'sh joy.
  out = out.replace(/[ \t]+([,.;:!?])/g, "$1");
  // Ketma-ket bo'sh joylar (satr boshidagi chekinishga tegmaydi).
  out = out.replace(/(\S)[ \t]{2,}(\S)/g, "$1 $2");
  // Ikkitadan ortiq bo'sh satr.
  out = out.replace(/\n{3,}/g, "\n\n");
  // Tartib son defisi: "5 - modda" → "5-modda"
  out = out.replace(/(\d)\s*[-–—]\s*(modda|band|qism|bob|ilova|yil|son)\b/gi, "$1-$2");

  return out.trim();
}
