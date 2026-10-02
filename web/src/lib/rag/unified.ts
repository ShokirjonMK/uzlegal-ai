/**
 * Yagona qidiruv interfeysi — yadro API yoki lokal RAG.
 *
 * ## Ikki rejim
 *
 * | `UZLEGAL_RAG` | Xatti-harakat |
 * |---|---|
 * | `api` *(standart)* | Faqat Python yadro. Yadro ishlamasa — xato |
 * | `local` | Faqat lokal TS RAG. Ishlab chiqish uchun, ATAYLAB tanlanadi |
 *
 * ## `auto` OLIB TASHLANDI (2026-08-25)
 *
 * Uchinchi rejim bor edi: yadro ishlamasa lokal bazaga tushish.
 * Ogohlantirish yozilardi — lekin KONSOLGA, yaʼni foydalanuvchi uni
 * hech qachon koʻrmasdi.
 *
 * Ikkala baza bir xil emas va farq oʻlchandi:
 *
 *     yadro:  808 hujjat · 48 932 boʻlak — HAQIQIY qonun
 *     lokal:  `web/data/corpus.db` — 4 KB, yaʼni BOʻSH
 *
 * Yaʼni `auto` hech qanday zaxira bermasdi. U faqat bitta narsa
 * qilardi: yadro oʻchganda **xatoni «natija topilmadi» ga
 * aylantirardi**. Huquqiy mahsulotda bu eng yomon almashtirish —
 * foydalanuvchi «bunday norma yoʻq» deb tushunadi, holbuki qidiruv
 * umuman ishlamagan.
 *
 * Endi yadro oʻchsa xato qaytadi va sababi aytiladi.
 */

import { config } from "../config";
import type { Retrieved } from "../types";
import { apiRetrieve, type ApiRetrieveOptions } from "./api-client";

type RagMode = "api" | "local";

/**
 * `auto` rejimi OLIB TASHLANDI (2026-08-25).
 *
 * U yadro ishlamasa lokal korpusga tushardi. Ogohlantirish yozilardi,
 * lekin u KONSOLGA chiqardi — foydalanuvchi uni hech qachon koʻrmasdi.
 *
 * Oʻlchandi: `web/data/corpus.db` — **4 KB, yaʼni boʻsh**. Yaʼni `auto`
 * hech qanday zaxira bermasdi; u faqat bitta narsa qilardi — yadro
 * oʻchganda xatoni «natija topilmadi» ga aylantirardi. Huquqiy
 * mahsulotda bu eng yomon almashtirish: foydalanuvchi «bunday norma
 * yoʻq» deb tushunadi, holbuki qidiruv umuman ishlamagan.
 *
 * Endi yadro oʻchsa — xato qaytadi va sabab aytiladi.
 */
function ragMode(): RagMode {
  const v = process.env["UZLEGAL_RAG"]?.trim().toLowerCase();
  if (v === "local") return "local";
  if (v === "auto") {
    console.warn(
      "[rag] UZLEGAL_RAG=auto endi qoʻllab-quvvatlanmaydi — `api` ishlatiladi. " +
        "Lokal korpus uchun UZLEGAL_RAG=local deb ATAYLAB tanlang.",
    );
  }
  return "api";
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
    warnLocal();
    return localRetrieve(query, opts);
  }

  return apiRetrieve(query, opts as ApiRetrieveOptions);
}

/** Lokal korpus ATAYLAB tanlanganda ogohlantiradi.
 *
 * Ilgari bu funksiya boshqa narsa uchun ishlatilardi: yadro oʻchganda
 * lokal korpusga JIMGINA tushish. U olib tashlandi — sababi
 * `ragMode()` izohida.
 */
let localWarned = false;

function warnLocal(): void {
  if (localWarned) return;
  localWarned = true;
  console.warn(
    [
      `[rag] LOKAL KORPUS tanlangan (UZLEGAL_RAG=local).`,
      `[rag] DIQQAT: bu baza yadronikidan BOSHQA va standart holda boʻsh.`,
      `      Javoblar haqiqiy qonunchilikni aks ettirmaydi.`,
      `[rag] Ishga tushirishda bu rejim ishlatilmaydi.`,
    ].join("\n"),
  );
  setTimeout(() => {
    localWarned = false;
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
