/**
 * Yagona qidiruv interfeysi — yadro API yoki lokal RAG.
 *
 * ## Standart: `api`
 *
 * | `UZLEGAL_RAG` | Xatti-harakat |
 * |---|---|
 * | `api` *(standart)* | Faqat Python yadro. Yadro ishlamasa — xato |
 * | `auto` | Yadro mavjud boʻlsa u, aks holda lokal (ogohlantirish bilan) |
 * | `local` | Faqat lokal TS RAG |
 *
 * ## Nima uchun `auto` STANDART EMAS
 *
 * Ilgari standart `auto` edi va yadro ishlamasa u **jimgina** lokal
 * RAG ga tushardi. Bu xavfli, chunki ikkala baza bir xil emas:
 *
 *     yadro:  20 kodeks · 7 090 modda · 8 636 boʻlak — HAQIQIY qonun
 *     lokal:  `data/corpus/` — standart holda faqat NAMUNA fayl,
 *             uning sarlavhasi «BU HAQIQIY QONUN EMAS» deb turadi
 *
 * Yaʼni jimgina tushish foydalanuvchiga **oʻylab topilgan qonun**
 * asosida javob berardi va u buni sezmasdi. «Javob yoʻq» bunday
 * javobdan yaxshiroq.
 *
 * `auto` rejimida ham endi ogohlantirish yoziladi va lokal korpus
 * boʻsh boʻlsa boʻsh natija qaytadi — «manba topilmadi» yoʻliga
 * tushadi.
 */

import { config } from "../config";
import type { Retrieved } from "../types";
import { apiRetrieve, isApiAvailable, type ApiRetrieveOptions } from "./api-client";

type RagMode = "api" | "local" | "auto";

function ragMode(): RagMode {
  const v = process.env["UZLEGAL_RAG"]?.trim().toLowerCase();
  if (v === "api" || v === "local" || v === "auto") return v;
  return "api";
}

let apiChecked = false;
let apiAvailable = false;

async function checkApi(): Promise<boolean> {
  if (apiChecked) return apiAvailable;
  apiAvailable = await isApiAvailable();
  apiChecked = true;
  // 60 soniyadan keyin qayta tekshiradi
  setTimeout(() => { apiChecked = false; }, 60_000).unref?.();
  return apiAvailable;
}

export interface UnifiedRetrieveOptions {
  topK?: number;
  minScore?: number;
  documents?: string[];
}

/**
 * Qidiruv — API yoki lokal, sozlamaga qarab.
 */
export async function unifiedRetrieve(
  query: string,
  opts: UnifiedRetrieveOptions = {},
): Promise<Retrieved[]> {
  const mode = ragMode();

  if (mode === "local") {
    return localRetrieve(query, opts);
  }

  if (mode === "api") {
    return apiRetrieve(query, opts as ApiRetrieveOptions);
  }

  // auto: yadro mavjud bo'lsa — shu, aks holda lokal (ogohlantirish bilan)
  if (await checkApi()) {
    try {
      return await apiRetrieve(query, opts as ApiRetrieveOptions);
    } catch (err) {
      apiChecked = false;
      warnFallback((err as Error).message);
    }
  } else {
    warnFallback("yadro javob bermadi");
  }

  return localRetrieve(query, opts);
}

/** Lokal RAG ga tushish — bir marta va BALAND ovozda ogohlantiradi.
 *
 * Jimgina tushish eng yomon variant: javob sifati keskin tushadi,
 * lekin buni hech kim sezmaydi.
 */
let fallbackWarned = false;

function warnFallback(reason: string): void {
  if (fallbackWarned) return;
  fallbackWarned = true;
  console.warn(
    [
      `[rag] YADRO ISHLAMAYAPTI (${reason}) — lokal korpusga tushildi.`,
      `[rag] DIQQAT: lokal korpus yadronikidan boshqa va standart holda`,
      `      faqat NAMUNA fayldan iborat. Javoblar ishonchsiz.`,
      `[rag] Yechim: yadroni ishga tushiring (uzlegal serve) yoki`,
      `      UZLEGAL_RAG=local deb ATAYLAB tanlang.`,
    ].join("\n"),
  );
  setTimeout(() => {
    fallbackWarned = false;
  }, 300_000).unref?.();
}

async function localRetrieve(
  query: string,
  opts: UnifiedRetrieveOptions,
): Promise<Retrieved[]> {
  const { retrieve } = await import("./retrieve");
  return retrieve(query, {
    topK: opts.topK,
    minScore: opts.minScore ?? config.ragMinScore,
    documents: opts.documents,
  });
}
