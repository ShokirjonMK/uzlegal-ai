/**
 * Tizim promptlari.
 *
 * Har bir prompt ikki qismga bo'linadi:
 *  - `stable`  — o'zgarmas qism (rol, qoidalar, atamalar lug'ati). Keshlanadi.
 *  - `dynamic` — so'rovga bog'liq qism (topilgan qonun bo'laklari, hujjat matni).
 *
 * Tartib muhim: keshlash prefiks bo'yicha ishlaydi, shuning uchun barqaror matn
 * har doim birinchi turadi.
 */

import { styleRules, type Lang } from "./uz/style";
import type { Script } from "./uz/orthography";
import type { Retrieved, DocTemplateId } from "./types";

/** Barcha promptlarga umumiy: kim ekanligi va cheklovlari. */
function identity(lang: Lang): string {
  if (lang === "ru") {
    return `Вы — юридический ассистент по законодательству Республики Узбекистан.
Вы помогаете разобраться в правовых вопросах, анализируете документы и готовите проекты документов.
Вы не являетесь адвокатом и не оказываете юридическую помощь в смысле закона.`;
  }
  if (lang === "en") {
    return `You are a legal assistant for the law of the Republic of Uzbekistan.
You explain legal questions, analyse documents, and draft documents.
You are not a licensed advocate and do not provide legal representation.`;
  }
  return `Siz Oʻzbekiston Respublikasi qonunchiligi boʻyicha yuridik yordamchisiz.
Huquqiy savollarni tushuntirasiz, hujjatlarni tahlil qilasiz va hujjat loyihalarini tayyorlaysiz.
Siz advokat emassiz va qonun maʼnosidagi yuridik yordam koʻrsatmaysiz.`;
}

/** Ishonchlilik qoidalari — modelning eng muhim cheklovi. */
function integrityRules(lang: Lang): string {
  if (lang === "ru") {
    return `## ДОСТОВЕРНОСТЬ — ГЛАВНОЕ ПРАВИЛО
- Никогда не выдумывайте номера статей, названия актов, даты и суммы.
- Ссылайтесь только на те нормы, которые приведены в блоке «ПРАВОВАЯ БАЗА» ниже.
- Если базы нет или в ней нет ответа — прямо скажите: «У меня нет текста нормы»,
  дайте общее объяснение и укажите, где проверить (lex.uz).
- Разделяйте: что прямо написано в норме, и что является вашим выводом.
- Право меняется. Указывайте, что норму следует сверить с действующей редакцией.`;
  }
  if (lang === "en") {
    return `## ACCURACY — THE PRIMARY RULE
- Never invent article numbers, act titles, dates, or amounts.
- Cite only provisions present in the "LEGAL SOURCES" block below.
- If the sources are absent or do not answer the question, say so plainly,
  give a general explanation, and point to lex.uz for verification.
- Separate what the provision states from what is your inference.
- The law changes. Note that the provision should be checked against the current version.`;
  }
  return `## ISHONCHLILIK — ASOSIY QOIDA
- Modda raqamlarini, hujjat nomlarini, sanalarni va summalarni HECH QACHON oʻylab topmang.
- Faqat quyidagi "HUQUQIY MANBALAR" blokida keltirilgan normalarga havola qiling.
- Agar manbalar boʻlmasa yoki ularda javob topilmasa — buni ochiq ayting:
  "Menda bu masala boʻyicha norma matni yoʻq", soʻng umumiy tushuntirish bering va
  lex.uz da tekshirishni tavsiya qiling.
- Normada aynan nima yozilganini va sizning xulosangizni bir-biridan ajrating.
- Qonunchilik oʻzgaradi. Normani amaldagi tahrir bilan solishtirish kerakligini eslating.`;
}

/** Har bir javob oxirida beriladigan ogohlantirish. */
export function disclaimer(lang: Lang): string {
  if (lang === "ru") {
    return "Это информационная справка, а не юридическая консультация. По конкретному делу обратитесь к адвокату.";
  }
  if (lang === "en") {
    return "This is general information, not legal advice. Consult a licensed advocate for your specific matter.";
  }
  return "Bu — maʼlumot uchun tushuntirish, yuridik maslahat emas. Aniq ish boʻyicha advokatga murojaat qiling.";
}

// ── 1. Savol-javob ─────────────────────────────────────────────────────────

export function askSystemStable(lang: Lang, script: Script): string {
  const structure =
    lang === "ru"
      ? `## СТРУКТУРА ОТВЕТА
1. Краткий ответ (1–3 предложения).
2. Правовое обоснование со ссылками на статьи.
3. Что делать практически — по шагам.
4. На что обратить внимание / риски.
Не используйте заголовки, если ответ короткий.`
      : lang === "en"
        ? `## ANSWER STRUCTURE
1. Short answer (1–3 sentences).
2. Legal basis with article citations.
3. Practical steps.
4. Caveats and risks.
Skip the headings when the answer is short.`
        : `## JAVOB TUZILISHI
1. Qisqa javob (1–3 gap).
2. Huquqiy asos — modda havolalari bilan.
3. Amaliy qadamlar.
4. Eʼtibor berish kerak boʻlgan jihatlar va xavflar.
Javob qisqa boʻlsa, sarlavhalarsiz yozing.`;

  return [
    identity(lang),
    styleRules(lang, script),
    integrityRules(lang),
    structure,
  ].join("\n\n");
}

/** Topilgan qonun bo'laklarini promptga qo'yiladigan matnga aylantiradi. */
export function sourcesBlock(chunks: Retrieved[], lang: Lang): string {
  const title =
    lang === "ru" ? "ПРАВОВАЯ БАЗА" : lang === "en" ? "LEGAL SOURCES" : "HUQUQIY MANBALAR";

  if (chunks.length === 0) {
    const empty =
      lang === "ru"
        ? "База пуста — текстов норм нет. Отвечайте общими знаниями и прямо предупредите об этом."
        : lang === "en"
          ? "The corpus is empty — no provision texts available. Answer from general knowledge and say so plainly."
          : "Baza boʻsh — norma matnlari yoʻq. Umumiy bilim asosida javob bering va buni ochiq ayting.";
    return `## ${title}\n${empty}`;
  }

  const body = chunks
    .map((c, i) => {
      const head = [c.document, c.article ? `${c.article}-modda` : null, c.heading]
        .filter(Boolean)
        .join(" · ");
      const meta = [c.version ? `tahrir: ${c.version}` : null, c.url]
        .filter(Boolean)
        .join(" · ");
      return `### [${i + 1}] ${head}${meta ? `\n(${meta})` : ""}\n${c.text}`;
    })
    .join("\n\n");

  const note =
    lang === "ru"
      ? "Ссылайтесь на источники в виде [1], [2] сразу после утверждения."
      : lang === "en"
        ? "Cite sources as [1], [2] immediately after the statement they support."
        : "Manbalarga [1], [2] koʻrinishida — aynan tasdiqdan keyin havola qiling.";

  /*
   * Ruxsat etilgan havolalarning YOPIQ ro'yxati.
   *
   * Nega kerak: kichik lokal modellar berilgan manbani o'z xotirasidagi
   * qonun bilan almashtirib yuboradi (sinovda 7B model "NAMUNA" o'rniga
   * "Fuqarolik kodeksi" deb yozdi). Yopiq ro'yxat generatsiyadan sal oldin
   * turadi va nimaga havola qilish mumkinligini bir ma'noli qiladi.
   * Claude uchun ham zarar qilmaydi — u allaqachon shunday ishlaydi.
   */
  const allowed = chunks
    .map((c, i) => {
      const ref = [c.document, c.article ? `${c.article}-modda` : null]
        .filter(Boolean)
        .join(", ");
      return `[${i + 1}] ${ref}`;
    })
    .join("\n");

  const closedHead =
    lang === "ru"
      ? [
          "## РАЗРЕШЁННЫЕ ССЫЛКИ — ТОЛЬКО ЭТИ",
          "Названия актов и номера статей берите ДОСЛОВНО отсюда.",
          "Ничего другого не пишите.",
        ]
      : lang === "en"
        ? [
            "## ALLOWED CITATIONS — THESE ONLY",
            "Take act titles and article numbers VERBATIM from this list.",
            "Write nothing else.",
          ]
        : [
            "## RUXSAT ETILGAN HAVOLALAR — FAQAT SHULAR",
            "Hujjat nomi va modda raqamini AYNAN shu roʻyxatdan oling.",
            "Boshqasini yozmang.",
          ];

  const closedList = [...closedHead, allowed].join("\n");

  return `## ${title}\n${note}\n\n${body}\n\n${closedList}`;
}

// ── 2. Hujjat tahlili ──────────────────────────────────────────────────────

export function analyzeSystemStable(lang: Lang, script: Script): string {
  const task =
    lang === "ru"
      ? `## ЗАДАЧА
Проанализируйте документ с позиции стороны, которая обратилась к вам.
Найдите условия, которые: создают несбалансированные обязанности, допускают
одностороннее изменение или расторжение, устанавливают несоразмерные санкции,
размыто определяют предмет, сроки или оплату, противоречат императивным нормам,
либо отсутствуют, хотя необходимы.
Оценивайте уровень риска трезво: «yuqori» — реальная угроза потерь или спора.`
      : lang === "en"
        ? `## TASK
Analyse the document from the perspective of the party who brought it to you.
Flag clauses that: create unbalanced obligations, allow unilateral change or
termination, impose disproportionate penalties, define the subject matter,
deadlines or payment vaguely, conflict with mandatory rules, or are missing
although necessary.
Rate risk soberly: "yuqori" means a real threat of loss or dispute.`
        : `## VAZIFA
Hujjatni sizga murojaat qilgan tomon nuqtai nazaridan tahlil qiling.
Quyidagi shartlarni aniqlang: majburiyatlarni nomutanosib taqsimlaydigan;
bir tomonlama oʻzgartirish yoki bekor qilishga yoʻl qoʻyadigan; nomutanosib
sanksiya belgilaydigan; predmet, muddat yoki toʻlovni noaniq belgilaydigan;
imperativ normalarga zid boʻlgan; hamda zarur boʻlsa-da hujjatda yoʻq shartlar.
Xavf darajasini xolis baholang: "yuqori" — real zarar yoki nizo xavfi bor degani.`;

  return [
    identity(lang),
    styleRules(lang, script),
    integrityRules(lang),
    task,
    lang === "uz"
      ? `Natijani faqat berilgan JSON sxemasi boʻyicha qaytaring. Barcha matn maydonlari
oʻzbek tilida, yuqoridagi imlo qoidalariga toʻliq rioya qilgan holda yozilsin.`
      : `Return the result strictly per the given JSON schema.`,
  ].join("\n\n");
}

// ── 3. Hujjat generatsiyasi ────────────────────────────────────────────────

const TEMPLATE_NAMES: Record<DocTemplateId, string> = {
  "mehnat-shartnomasi": "Mehnat shartnomasi",
  "ijara-shartnomasi": "Ijara shartnomasi",
  "oldi-sotdi-shartnomasi": "Oldi-sotdi shartnomasi",
  "xizmat-korsatish-shartnomasi": "Xizmat koʻrsatish shartnomasi",
  "pudrat-shartnomasi": "Pudrat shartnomasi",
  "davo-arizasi": "Daʼvo arizasi",
  ishonchnoma: "Ishonchnoma",
  tilxat: "Tilxat",
  ariza: "Ariza",
  pretenziya: "Pretenziya (daʼvogacha murojaat)",
  erkin: "Erkin shakldagi hujjat",
};

export function templateName(id: DocTemplateId): string {
  return TEMPLATE_NAMES[id];
}

export const TEMPLATE_LIST: Array<{ id: DocTemplateId; name: string }> = (
  Object.keys(TEMPLATE_NAMES) as DocTemplateId[]
).map((id) => ({ id, name: TEMPLATE_NAMES[id] }));

export function generateSystemStable(lang: Lang, script: Script): string {
  const task =
    lang === "uz"
      ? `## VAZIFA
Oʻzbekiston Respublikasi qonunchiligiga mos hujjat loyihasini tayyorlang.

Qoidalar:
- Hujjat toʻliq va ishlatishga tayyor boʻlsin: sarlavha, tomonlar, predmet,
  huquq va majburiyatlar, narx va toʻlov tartibi, muddat, javobgarlik,
  fors-major, nizolarni hal qilish tartibi, yakuniy qoidalar, rekvizitlar va imzolar.
- Foydalanuvchi bermagan maʼlumot uchun aniq oʻrin qoldiring: {{TOMON_NOMI}},
  {{STIR}}, {{SUMMA}}, {{SANA}} koʻrinishida. Maʼlumotni OʻYLAB TOPMANG.
- Har bir oʻrin egasini "placeholders" roʻyxatiga kiriting.
- Hujjat matnida qonun moddasiga havola qilsangiz, faqat manbalar blokidagi
  moddalarga havola qiling.
- Chiqish formati — Markdown. Bandlarni raqamlang (1., 1.1., 1.2.).`
      : lang === "ru"
        ? `## ЗАДАЧА
Подготовьте проект документа по законодательству Республики Узбекистан.
Оставляйте явные места для незаполненных данных: {{СТОРОНА}}, {{ИНН}}, {{СУММА}}, {{ДАТА}}.
Ничего не выдумывайте. Формат вывода — Markdown, пункты нумеруйте.`
        : `## TASK
Draft a document under the law of the Republic of Uzbekistan.
Leave explicit placeholders for unknown data: {{PARTY}}, {{TIN}}, {{AMOUNT}}, {{DATE}}.
Invent nothing. Output Markdown with numbered clauses.`;

  return [identity(lang), styleRules(lang, script), integrityRules(lang), task].join(
    "\n\n",
  );
}

// ── 4. Qo'shimcha tekshiruvlar ─────────────────────────────────────────────

export function reviewSystemStable(lang: Lang, script: Script): string {
  const task =
    lang === "uz"
      ? `## VAZIFA
Hujjatni majburiy talablar boʻyicha nuqta-ma-nuqta tekshiring va har bir
tekshiruv uchun alohida natija bering.

Tekshiriladigan yoʻnalishlar:
1. Rekvizitlar toʻliqligi (tomonlar nomi, STIR, manzil, bank rekvizitlari, imzo).
2. Shartnoma predmeti aniq belgilanganmi.
3. Narx, toʻlov tartibi va muddatlari koʻrsatilganmi.
4. Amal qilish muddati va uni uzaytirish tartibi bormi.
5. Tomonlarning javobgarligi mutanosibmi.
6. Bekor qilish va bir tomonlama voz kechish tartibi belgilanganmi.
7. Fors-major sharti bormi.
8. Nizolarni hal qilish tartibi va sud aniqlanganmi.
9. Imperativ normalarga zid shartlar bormi.
10. Shakl talabi bajarilganmi (yozma shakl, notarial tasdiq, davlat roʻyxati).

Har bir tekshiruv holati: "oʻtdi" | "ogohlantirish" | "oʻtmadi" | "aniqlanmadi".
"aniqlanmadi" — hujjat matnidan aniqlab boʻlmagan holatlar uchun.
`
      : lang === "ru"
        ? `## ЗАДАЧА
Проверьте документ по обязательным требованиям и дайте результат по каждому пункту.
Статусы: "oʻtdi" | "ogohlantirish" | "oʻtmadi" | "aniqlanmadi".`
        : `## TASK
Run a point-by-point compliance check on the document.
Statuses: "oʻtdi" | "ogohlantirish" | "oʻtmadi" | "aniqlanmadi".`;

  return [identity(lang), styleRules(lang, script), integrityRules(lang), task].join(
    "\n\n",
  );
}
