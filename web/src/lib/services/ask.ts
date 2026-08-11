/**
 * Savol-javob — uzlegal-ai yadrosi orqali.
 *
 * NIMA O'ZGARDI. Ilgari bu fayl butun ishni o'zi bajarardi: qonun bazasidan
 * bo'lak topar, prompt yig'ar, Claude SDK ni chaqirar, javobdagi modda
 * raqamlarini o'zi tekshirardi. Birlashtirishdan keyin bularning HAMMASI
 * yadroda (`POST /v1/consult`) bajariladi — qidiruv, agentlar, groundedness
 * gate va iqtiboslar o'sha yerda. Bu fayl endi shunchaki tarjimon:
 * qobiq so'rovini yadro so'roviga, yadro javobini qobiq hodisalariga
 * aylantiradi.
 *
 * NEGA SHUNDAY YAXSHI. Ikkita mustaqil huquqiy dvigatel (bittasi Python da,
 * bittasi TypeScript da) muqarrar ravishda BOSHQA javob beradi — bir xil
 * savolga web va CLI turlicha javob qaytarardi. Endi manba bitta.
 *
 * MUHIM: hodisa shakli (`StreamEvent`) o'zgarmadi, shuning uchun web,
 * Telegram bot, REST API va CLI qobiqlari tegilmasdan ishlayveradi.
 */

import { config } from "../config";
import {
  consult,
  consultStream,
  stepLabel,
  toWebCitations,
  uzlegalHumanError,
  type ConsultRequest,
  type ConsultResult,
} from "../uzlegal/client";
import { resolveLang } from "../uz/detect";
import { polishUzbek } from "../uz/orthography";
import type { AskRequest, AskResult, ChatMessage, StreamEvent } from "../types";

/** Suhbat tarixining oxirgi N ta xabari (kontekstni cheklash uchun). */
const HISTORY_LIMIT = 6;

/**
 * Yadro so'rovini yig'ish.
 *
 * `/v1/consult` da suhbat tarixi maydoni YO'Q — u bitta savolni qabul
 * qiladi. Shuning uchun tarix savol matniga qisqa kontekst sifatida
 * qo'shiladi: aks holda "u qancha?" kabi davomi savollar ma'nosini
 * yo'qotadi.
 */
function buildRequest(req: AskRequest, lang: "uz" | "ru" | "en"): ConsultRequest {
  const history = (req.history ?? []).slice(-HISTORY_LIMIT);

  let question = req.question;
  if (history.length > 0) {
    const context = history
      .map((m: ChatMessage) => `${m.role === "user" ? "Savol" : "Javob"}: ${m.content}`)
      .join("\n");
    question = `Oldingi suhbat:\n${context}\n\nYangi savol: ${req.question}`;
  }

  return {
    question,
    lang,
    mode: config.uzlegalMode,
  };
}

/**
 * Yadro natijasidan foydalanuvchiga ko'rsatiladigan matn.
 *
 * `caveats` — yadro o'zi qo'shgan ogohlantirishlar (masalan gate bir
 * da'voni manbasiz deb o'chirgan bo'lsa). Ular YASHIRILMAYDI: aynan
 * shular javobning qayeri ishonchsizligini ko'rsatadi.
 */
function renderAnswer(result: ConsultResult, uzLatin: boolean): string {
  let text = uzLatin ? polishUzbek(result.answer) : result.answer.trim();

  if (result.caveats.length > 0) {
    const list = result.caveats.map((c) => `> - ${c}`).join("\n");
    text += `\n\n> ⚠️ **Eʼtiborga oling:**\n${list}`;
  }

  // Yadro ishonchli javob bera olmagan holat. Bu xato emas — "bilmayman"
  // to'liq huquqli javob, lekin foydalanuvchi buni bilishi kerak.
  if (result.confidence === 0) {
    text +=
      `\n\n> ℹ️ Tizim bu savolga ishonchli javob topa olmadi. ` +
      `Quyidagi manbalarni oʻzingiz koʻrib chiqing yoki advokatga murojaat qiling.`;
  }

  return `${text}\n\n---\n_${result.disclaimer}_`;
}

/** Streaming savol-javob. Hodisalarni ketma-ket qaytaradi. */
export async function* askStream(
  req: AskRequest,
): AsyncGenerator<StreamEvent, void, unknown> {
  const { lang, script } = resolveLang(
    req.question,
    req.lang ?? config.lang,
    req.script ?? config.script,
  );

  try {
    yield { type: "status", message: "Yuridik yadroga yuborilmoqda…" };

    let answered = false;

    for await (const ev of consultStream(buildRequest(req, lang))) {
      if (ev.type === "step") {
        yield { type: "status", message: stepLabel(ev.node) };
        continue;
      }

      if (ev.type === "error") {
        yield { type: "error", message: ev.message };
        return;
      }

      if (ev.type === "answer") {
        answered = true;
        // Iqtiboslar javobdan OLDIN yuboriladi — qobiq ularni javob
        // paydo bo'lgan zahoti yonida ko'rsata olsin.
        yield { type: "citations", citations: toWebCitations(ev.result.citations) };
        yield {
          type: "delta",
          text: renderAnswer(ev.result, lang === "uz" && script === "latn"),
        };
      }
    }

    // Oqim javobsiz tugadi — bu yadro tomonidagi nosozlik, jimgina
    // "tayyor" deb ko'rsatish yolg'on bo'lardi.
    if (!answered) {
      yield {
        type: "error",
        message: "Yadro javobni yubormasdan oqimni yopdi. Qayta urinib koʻring.",
      };
      return;
    }

    yield { type: "done" };
  } catch (err) {
    yield { type: "error", message: uzlegalHumanError(err) };
  }
}

/** Streamingsiz savol-javob (bot va CLI uchun qulay). */
export async function ask(req: AskRequest): Promise<AskResult> {
  const { lang, script } = resolveLang(
    req.question,
    req.lang ?? config.lang,
    req.script ?? config.script,
  );

  const result = await consult(buildRequest(req, lang));

  return {
    answer: renderAnswer(result, lang === "uz" && script === "latn"),
    citations: toWebCitations(result.citations),
    lang,
    script,
    // Token hisobi yadroda qoladi — qobiq uni ko'rmaydi.
    usage: undefined,
  };
}
