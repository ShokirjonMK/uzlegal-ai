/**
 * O'zbek yuridik atamalari lug'ati.
 *
 * Maqsad — model ruscha kalkalar ("dogovor", "isk", "zayavleniye") o'rniga
 * O'zbekiston qonunchiligida rasman qo'llanadigan atamalarni ishlatsin.
 * Lug'at tizim promptiga siqiq ko'rinishda qo'shiladi, shuning uchun
 * faqat chalkashlik ko'p uchraydigan atamalar kiritilgan.
 */

export interface Term {
  /** To'g'ri o'zbekcha atama. */
  uz: string;
  /** Ruscha ekvivalenti (foydalanuvchi ruscha so'rasa ham tushunsin). */
  ru: string;
  /** Ishlatilmasligi kerak bo'lgan kalka/varvarizmlar. */
  avoid?: string[];
}

export const LEGAL_TERMS: Term[] = [
  // Umumiy
  { uz: "shartnoma", ru: "договор", avoid: ["dogovor"] },
  { uz: "bitim", ru: "сделка", avoid: ["sdelka"] },
  { uz: "majburiyat", ru: "обязательство", avoid: ["obyazatelstvo"] },
  { uz: "javobgarlik", ru: "ответственность", avoid: ["otvetstvennost"] },
  { uz: "huquq", ru: "право" },
  { uz: "burch", ru: "обязанность" },
  { uz: "huquqbuzarlik", ru: "правонарушение" },
  { uz: "qonun hujjatlari", ru: "законодательство", avoid: ["zakonodatelstvo"] },
  { uz: "normativ-huquqiy hujjat", ru: "нормативно-правовой акт" },

  // Hujjatlar
  { uz: "ariza", ru: "заявление", avoid: ["zayavleniye"] },
  { uz: "shikoyat", ru: "жалоба", avoid: ["jaloba"] },
  { uz: "murojaat", ru: "обращение" },
  { uz: "ishonchnoma", ru: "доверенность", avoid: ["doverennost"] },
  { uz: "tilxat", ru: "расписка", avoid: ["raspiska"] },
  { uz: "maʼlumotnoma", ru: "справка", avoid: ["spravka"] },
  { uz: "dalolatnoma", ru: "акт" },
  { uz: "bayonnoma", ru: "протокол" },
  { uz: "vasiyatnoma", ru: "завещание" },
  { uz: "qoʻshimcha kelishuv", ru: "дополнительное соглашение" },
  { uz: "taʼsis hujjatlari", ru: "учредительные документы" },
  { uz: "ustav", ru: "устав" },
  { uz: "rekvizitlar", ru: "реквизиты" },

  // Sud
  { uz: "daʼvo", ru: "иск", avoid: ["isk"] },
  { uz: "daʼvo arizasi", ru: "исковое заявление" },
  { uz: "daʼvogar", ru: "истец", avoid: ["istets"] },
  { uz: "javobgar", ru: "ответчик", avoid: ["otvetchik"] },
  { uz: "uchinchi shaxs", ru: "третье лицо" },
  { uz: "sud qarori", ru: "решение суда" },
  { uz: "sud ajrimi", ru: "определение суда" },
  { uz: "hukm", ru: "приговор" },
  { uz: "apellyatsiya shikoyati", ru: "апелляционная жалоба" },
  { uz: "kassatsiya shikoyati", ru: "кассационная жалоба" },
  { uz: "daʼvo muddati", ru: "исковая давность" },
  { uz: "davlat boji", ru: "государственная пошлина", avoid: ["poshlina"] },
  { uz: "ijro varaqasi", ru: "исполнительный лист" },
  { uz: "undirish", ru: "взыскание" },
  { uz: "dalil", ru: "доказательство" },
  { uz: "guvoh", ru: "свидетель" },
  { uz: "ekspertiza", ru: "экспертиза" },
  { uz: "hakamlik sudi", ru: "третейский суд" },

  // Shaxslar
  { uz: "jismoniy shaxs", ru: "физическое лицо" },
  { uz: "yuridik shaxs", ru: "юридическое лицо" },
  { uz: "yakka tartibdagi tadbirkor (YTT)", ru: "индивидуальный предприниматель (ИП)" },
  { uz: "tadbirkorlik subyekti", ru: "субъект предпринимательства" },
  { uz: "muassis", ru: "учредитель" },
  { uz: "vakil", ru: "представитель" },

  // Fuqarolik-huquqiy
  { uz: "mulk huquqi", ru: "право собственности", avoid: ["sobstvennost"] },
  { uz: "koʻchmas mulk", ru: "недвижимость", avoid: ["nedvijimost"] },
  { uz: "egalik qilish, foydalanish va tasarruf etish", ru: "владение, пользование и распоряжение" },
  { uz: "oldi-sotdi shartnomasi", ru: "договор купли-продажи" },
  { uz: "ijara shartnomasi", ru: "договор аренды", avoid: ["arenda dogovori"] },
  { uz: "pudrat shartnomasi", ru: "договор подряда" },
  { uz: "yetkazib berish shartnomasi", ru: "договор поставки" },
  { uz: "xizmat koʻrsatish shartnomasi", ru: "договор оказания услуг" },
  { uz: "garov", ru: "залог" },
  { uz: "kafillik", ru: "поручительство" },
  { uz: "kafolat", ru: "гарантия" },
  { uz: "neustoyka (jarima, penya)", ru: "неустойка (штраф, пеня)" },
  { uz: "zarar", ru: "ущерб / убытки" },
  { uz: "yengib boʻlmas kuch (fors-major)", ru: "непреодолимая сила (форс-мажор)" },
  { uz: "meros", ru: "наследство" },

  // Mehnat
  { uz: "mehnat shartnomasi", ru: "трудовой договор" },
  { uz: "ish haqi", ru: "заработная плата", avoid: ["zarplata"] },
  { uz: "ishdan boʻshatish", ru: "увольнение", avoid: ["uvolneniye"] },
  { uz: "mehnat taʼtili", ru: "трудовой отпуск", avoid: ["otpusk"] },
  { uz: "intizomiy jazo", ru: "дисциплинарное взыскание" },
  { uz: "moddiy javobgarlik", ru: "материальная ответственность" },
  { uz: "sinov muddati", ru: "испытательный срок" },
  { uz: "ish vaqti", ru: "рабочее время" },

  // Oila
  { uz: "nikoh", ru: "брак" },
  { uz: "nikohdan ajratish", ru: "расторжение брака" },
  { uz: "aliment", ru: "алименты" },
  { uz: "vasiylik va homiylik", ru: "опека и попечительство" },

  // Soliq va davlat
  { uz: "soliq", ru: "налог" },
  { uz: "qoʻshilgan qiymat soligʻi (QQS)", ru: "налог на добавленную стоимость (НДС)" },
  { uz: "bazaviy hisoblash miqdori (BHM)", ru: "базовая расчётная величина (БРВ)" },
  { uz: "soliq toʻlovchining identifikatsiya raqami (STIR)", ru: "ИНН" },
  { uz: "litsenziya", ru: "лицензия" },
  { uz: "ruxsatnoma", ru: "разрешение" },
  { uz: "maʼmuriy javobgarlik", ru: "административная ответственность" },
  { uz: "jarima", ru: "штраф", avoid: ["shtraf"] },
];

/** O'zbekiston Respublikasi asosiy kodekslari va ularning qisqartmalari. */
export const CODES: Array<{ uz: string; abbr: string; ru: string }> = [
  { uz: "Oʻzbekiston Respublikasi Konstitutsiyasi", abbr: "Konstitutsiya", ru: "Конституция" },
  { uz: "Fuqarolik kodeksi", abbr: "FK", ru: "Гражданский кодекс (ГК)" },
  { uz: "Fuqarolik protsessual kodeksi", abbr: "FPK", ru: "ГПК" },
  { uz: "Iqtisodiy protsessual kodeks", abbr: "IPK", ru: "ЭПК" },
  { uz: "Mehnat kodeksi", abbr: "MK", ru: "Трудовой кодекс (ТК)" },
  { uz: "Oila kodeksi", abbr: "OK", ru: "Семейный кодекс (СК)" },
  { uz: "Jinoyat kodeksi", abbr: "JK", ru: "Уголовный кодекс (УК)" },
  { uz: "Jinoyat-protsessual kodeksi", abbr: "JPK", ru: "УПК" },
  { uz: "Maʼmuriy javobgarlik toʻgʻrisidagi kodeks", abbr: "MJtK", ru: "КоАО" },
  { uz: "Soliq kodeksi", abbr: "SK", ru: "Налоговый кодекс (НК)" },
  { uz: "Yer kodeksi", abbr: "YeK", ru: "Земельный кодекс" },
  { uz: "Uy-joy kodeksi", abbr: "UJK", ru: "Жилищный кодекс" },
  { uz: "Byudjet kodeksi", abbr: "BK", ru: "Бюджетный кодекс" },
  { uz: "Bojxona kodeksi", abbr: "BojK", ru: "Таможенный кодекс" },
];

/** Lug'atni tizim prompti uchun siqiq matnga aylantiradi. */
export function glossaryBlock(): string {
  const terms = LEGAL_TERMS.map((t) => {
    const avoid = t.avoid?.length ? ` [emas: ${t.avoid.join(", ")}]` : "";
    return `${t.uz} = ${t.ru}${avoid}`;
  }).join("; ");

  const codes = CODES.map((c) => `${c.uz} (${c.abbr}) = ${c.ru}`).join("; ");

  return `ATAMALAR (oʻzbekcha = ruscha):\n${terms}\n\nKODEKSLAR:\n${codes}`;
}
