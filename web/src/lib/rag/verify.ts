/**
 * Javobdagi modda havolalarini manbalarga solishtiradi.
 *
 * NEGA KERAK. Promptdagi qoidalar modelga ISHONISHNI talab qiladi, lokal
 * modellar esa buni uddalay olmadi: sinovda 7B ham, 14B ham bazada umuman
 * bo'lmagan "Fuqarolik kodeksi 234-moddasi" kabi havolalarni yozdi.
 *
 * Bu tekshiruv modelga bog'liq emas — u oddiy matn solishtiruvi. Shuning
 * uchun har qanday provayder uchun ishlaydi va Claude to'g'ri ishlaganda
 * umuman sezilmaydi (hech qachon ishga tushmaydi).
 *
 * Tekshiruv javobni O'CHIRMAYDI: oqim allaqachon foydalanuvchiga ketgan
 * bo'ladi. Uning o'rniga oxiriga ochiq ogohlantirish qo'shiladi.
 */

import type { Retrieved } from "../types";

/** Javob matnidan `123-modda` ko'rinishidagi havolalarni ajratadi. */
export function mentionedArticles(text: string): string[] {
  const found = new Set<string>();
  // `5-modda`, `5 - modda`, `5-moddasi`, `5-moddada` — hammasi hisobga olinadi.
  for (const m of text.matchAll(/(\d+)\s*-\s*modda/gi)) {
    if (m[1]) found.add(m[1]);
  }
  return [...found];
}

/** Manbalarda haqiqatan mavjud modda raqamlari. */
export function allowedArticles(sources: Retrieved[]): Set<string> {
  const allowed = new Set<string>();
  for (const s of sources) {
    if (s.article) allowed.add(s.article);
  }
  return allowed;
}

/**
 * Manbalarda yo'q modda raqamlarini qaytaradi.
 * Bo'sh massiv — hammasi joyida.
 */
export function unsupportedArticles(
  answer: string,
  sources: Retrieved[],
): string[] {
  // Manba umuman bo'lmasa, javobda modda raqami bo'lishi mumkin emas.
  const allowed = allowedArticles(sources);
  return mentionedArticles(answer).filter((a) => !allowed.has(a));
}

/**
 * Ogohlantirish matni. `null` — ogohlantirish kerak emas.
 *
 * Matn foydalanuvchiga ko'rinadi, shuning uchun aniq va o'zbekcha:
 * nima bo'lgani va nima qilish kerakligi aytiladi.
 */
export function citationWarning(
  answer: string,
  sources: Retrieved[],
): string | null {
  const bad = unsupportedArticles(answer, sources);
  if (bad.length === 0) return null;

  const list = bad.map((a) => `${a}-modda`).join(", ");

  return (
    `\n\n> ⚠️ **Tekshiruv ogohlantirishi.** Javobda qonun bazasida ` +
    `topilmagan modda havolasi bor: ${list}. Bu havola oʻylab topilgan ` +
    `boʻlishi mumkin — unga tayanmang va lex.uz saytidan tekshiring.`
  );
}
