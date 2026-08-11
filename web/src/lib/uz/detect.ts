/**
 * Foydalanuvchi matnining tili va yozuvini aniqlash.
 *
 * Uch til qo'llab-quvvatlanadi: o'zbek (lotin/kirill), rus, ingliz.
 * Aniqlanmasa — o'zbek tili (loyihaning asosiy tili).
 */

import { detectScript, foldForSearch, type Script } from "./orthography";
import type { Lang } from "./style";

export type { Lang, Script };

/** Faqat o'zbek kirill alifbosida uchraydigan harflar. */
const UZ_CYRILLIC_ONLY = /[ЎўҒғҚқҲҳ]/;

/**
 * DIQQAT: bu lug'atdagi so'zlar APOSTROFSIZ yozilgan.
 * Qidirishdan oldin matn `foldForSearch` orqali o'tadi va u apostrofning
 * barcha ko'rinishini (ʻ ʼ ' ' `) butunlay olib tashlaydi. Ya'ni
 * foydalanuvchi "to'lov" ham, "toʻlov" ham, "tolov" ham yozsa — bu yerda
 * turgan `tolov` bilan mos keladi. Apostrofli variant qo'shilsa, aksincha,
 * hech qachon mos kelmaydi.
 */
const UZ_WORDS = new Set([
  "va", "bilan", "uchun", "boyicha", "qanday", "qanaqa", "qilish",
  "kerak", "mumkin", "men", "mening", "meni", "menga", "siz", "sizning",
  "nima", "nimaga", "qachon", "qayerda", "qaysi", "necha", "qancha",
  "haqida", "togrisida", "yoki", "ammo", "lekin", "agar",
  "shartnoma", "ariza", "sud", "qonun", "huquq", "hujjat", "ish", "ishdan",
  "javobgarlik", "majburiyat", "tolov", "muddat", "bor", "yoq",
  "boladi", "qildim", "qilaman", "yozing", "tushuntiring",
  "salom", "rahmat", "iltimos", "yordam", "savol", "javob",
  "ҳақида", "керак", "мумкин", "шартнома", "суд", "қонун", "ҳуқуқ", "ариза",
]);

const RU_WORDS = new Set([
  "и", "в", "не", "на", "что", "как", "мне", "мой", "моя", "я", "вы", "ваш",
  "это", "для", "или", "если", "но", "также", "быть", "есть", "нет",
  "договор", "суд", "закон", "право", "заявление", "иск", "документ",
  "ответственность", "обязательство", "срок", "оплата", "работник",
  "здравствуйте", "спасибо", "пожалуйста", "помогите", "вопрос", "можно",
]);

const EN_WORDS = new Set([
  "the", "and", "is", "are", "of", "to", "in", "for", "on", "with", "a", "an",
  "how", "what", "when", "where", "which", "can", "should", "must", "my", "i",
  "contract", "law", "court", "claim", "document", "employee", "employer",
  "liability", "obligation", "hello", "thanks", "please", "help", "question",
]);

function tokenize(text: string): string[] {
  return foldForSearch(text)
    .split(/[^\p{L}'']+/u)
    .filter((w) => w.length > 0);
}

function score(words: string[], dict: Set<string>): number {
  let n = 0;
  for (const w of words) if (dict.has(w)) n += 1;
  return n;
}

export interface Detected {
  lang: Lang;
  script: Script;
}

/**
 * Matn tilini va yozuvini aniqlaydi.
 * Qisqa yoki noaniq matnda `fallback` (standart: o'zbek lotin) qaytadi.
 */
export function detectLang(
  text: string,
  fallback: Detected = { lang: "uz", script: "latn" },
): Detected {
  if (!text || !text.trim()) return fallback;

  const script = detectScript(text);
  const words = tokenize(text);

  if (script === "cyrl") {
    // O'zbek kirilliga xos harflar bo'lsa — aniq o'zbekcha.
    if (UZ_CYRILLIC_ONLY.test(text)) return { lang: "uz", script: "cyrl" };
    const uz = score(words, UZ_WORDS);
    const ru = score(words, RU_WORDS);
    if (uz > ru) return { lang: "uz", script: "cyrl" };
    return { lang: "ru", script: "cyrl" };
  }

  const uz = score(words, UZ_WORDS);
  const en = score(words, EN_WORDS);

  // O'zbek lotiniga xos belgilar qo'shimcha dalil beradi.
  const uzSignals =
    (text.match(/[oO][''ʻ]|[gG][''ʻ]/g)?.length ?? 0) +
    (text.match(/\b\w*(ning|ga|dan|da|lar|ymiz|siz)\b/gi)?.length ?? 0) * 0.5 +
    (text.match(/[qxQX]/g)?.length ?? 0) * 0.2;

  if (uz + uzSignals > en) return { lang: "uz", script: "latn" };
  if (en > 0) return { lang: "en", script: "latn" };
  return fallback;
}

/**
 * Sozlamadagi majburiy til/yozuv bilan aniqlangan qiymatni birlashtiradi.
 * `auto` bo'lsa — aniqlangani, aks holda majburiy qiymat.
 */
export function resolveLang(
  text: string,
  forcedLang: Lang | "auto",
  forcedScript: Script | "auto",
): Detected {
  const detected = detectLang(text);
  return {
    lang: forcedLang === "auto" ? detected.lang : forcedLang,
    script: forcedScript === "auto" ? detected.script : forcedScript,
  };
}
