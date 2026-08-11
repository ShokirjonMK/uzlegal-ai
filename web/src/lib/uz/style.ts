/**
 * O'zbek tilida yozish qoidalari — tizim promptiga qo'shiladigan blok.
 *
 * Bu fayl loyihaning eng muhim qismlaridan biri: LLM o'zbek tilida ravon,
 * xatosiz va yuridik jihatdan to'g'ri atamalar bilan yozishi shu blokka bog'liq.
 */

import { glossaryBlock } from "./glossary";
import type { Script } from "./orthography";

export type Lang = "uz" | "ru" | "en";

/** O'zbek tilida yozish bo'yicha qat'iy qoidalar. */
export function uzbekStyleRules(script: Script): string {
  const scriptRule =
    script === "cyrl"
      ? `Javobni KIRILL yozuvida yozing (ўзбек кирилл алифбоси). Лотин ҳарфларини аралаштирманг.`
      : `Javobni LOTIN yozuvida yozing. Ikki belgini toʻgʻri qoʻllang:
   • ʻ (U+02BB) — faqat oʻ va gʻ tarkibida: oʻzbek, gʻalaba, Oʻzbekiston, toʻgʻri, soʻm.
   • ʼ (U+02BC) — tutuq belgisi: maʼno, sanʼat, taʼsir, sunʼiy, eʼlon, masʼul, qatʼiy.
   Oddiy apostrof (') yoki qoʻshtirnoq (' ') ni ishlatmang.`;

  return `## OʻZBEK TILIDA YOZISH QOIDALARI

${scriptRule}

**Til sofligi**
- Adabiy oʻzbek tilida yozing. Soʻzlashuv shevasi va qisqartmalarga yoʻl qoʻymang.
- Ruscha yoki inglizcha soʻzni oʻzbekcha muqobili bor joyda ishlatmang.
  Notoʻgʻri: "dogovor tuzish", "isk berish", "zayavleniye yozish", "otvetstvennost".
  Toʻgʻri:   "shartnoma tuzish", "daʼvo qoʻzgʻatish", "ariza yozish", "javobgarlik".
- Muqobili yoʻq xalqaro atamani ishlatsangiz, birinchi marta qavs ichida izohlang:
  "fors-major (yengib boʻlmas kuch)".
- Ruscha gap qurilishini nusxa koʻchirmang. Oʻzbek tilida kesim gap oxirida keladi.
  Notoʻgʻri: "Sud qaror qildi haqida shartnoma bekor qilinishi."
  Toʻgʻri:   "Sud shartnomani bekor qilish toʻgʻrisida qaror qabul qildi."

**Murojaat va ohang**
- Foydalanuvchiga "siz" deb, hurmat bilan murojaat qiling.
- Xolis va aniq yozing. Ortiqcha muqaddima, uzr va takrorlarsiz.
- Javobni xulosadan boshlang, keyin asoslang.

**Raqamlar, sanalar, havolalar**
- Sana: "2026-yil 8-avgust" (kun-oy-yil emas, aynan shu tartib).
- Tartib sonlar defis bilan: 5-modda, 2-qism, 3-band, 4-bob, 1-ilova.
- Pul: "1 500 000 soʻm" (uch xonadan boʻsh joy bilan ajratiladi).
- Qonunga havola shakli: "Mehnat kodeksining 173-moddasi",
  "Fuqarolik kodeksi 234-moddasining 2-qismi",
  "Vazirlar Mahkamasining 2023-yil 12-maydagi 145-son qarori".

**Imlo boʻyicha tez-tez uchraydigan xatolar**
- "toʻgʻri" (toʻgri emas), "koʻp" (kop emas), "soʻrash", "boʻlim", "yoʻq".
- "maʼlumot" (malumot emas), "taʼlim", "eʼtibor", "shuʼba emas — boʻlim".
- Jarangsizlashish: "kitob" + "ni" = "kitobni"; "hujjat" + "ga" = "hujjatga".
- Koʻplik: "hujjatlar", "moddalar", "tomonlar" (hujjatlari emas, agar egalik boʻlmasa).

${glossaryBlock()}`;
}

/** Rus tilida yozish qoidalari. */
export function russianStyleRules(): string {
  return `## ПРАВИЛА ПИСЬМА
- Отвечайте на русском языке, деловым юридическим стилем, обращение на «Вы».
- Используйте терминологию законодательства Республики Узбекистан.
- Ссылки на закон: «статья 173 Трудового кодекса», «часть 2 статьи 234 Гражданского кодекса».
- Дата: «8 августа 2026 года». Суммы: «1 500 000 сум».
- Начинайте с вывода, затем обоснование.`;
}

/** Ingliz tilida yozish qoidalari. */
export function englishStyleRules(): string {
  return `## WRITING RULES
- Answer in English, in plain professional legal register.
- Use the terminology of the legislation of the Republic of Uzbekistan; give the
  Uzbek term in parentheses on first use, e.g. "employment contract (mehnat shartnomasi)".
- Citations: "Article 173 of the Labour Code", "Article 234(2) of the Civil Code".
- Lead with the conclusion, then the reasoning.`;
}

/** Tanlangan tilga mos yozish qoidalarini qaytaradi. */
export function styleRules(lang: Lang, script: Script): string {
  switch (lang) {
    case "uz":
      return uzbekStyleRules(script);
    case "ru":
      return russianStyleRules();
    case "en":
      return englishStyleRules();
  }
}

/** Til nomlari (log va UI uchun). */
export const LANG_NAMES: Record<Lang, string> = {
  uz: "oʻzbekcha",
  ru: "ruscha",
  en: "inglizcha",
};
