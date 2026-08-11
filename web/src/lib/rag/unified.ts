/**
 * Yagona qidiruv interfeysi — API yoki lokal RAG.
 *
 * Strategiya:
 * 1. Agar `UZLEGAL_RAG=api` — faqat Python yadro API
 * 2. Agar `UZLEGAL_RAG=local` — faqat lokal TS RAG
 * 3. Standart (`auto`) — API mavjud boʻlsa uni ishlatadi, aks holda lokal
 *
 * Bu modul `retrieve()` ni eksport qiladi — xuddi eski `./retrieve` dek.
 * Servislar import ni `../rag/retrieve` dan `../rag/unified` ga almashtiriladi.
 */

import { config } from "../config";
import type { Retrieved } from "../types";
import { apiRetrieve, isApiAvailable, type ApiRetrieveOptions } from "./api-client";

type RagMode = "api" | "local" | "auto";

function ragMode(): RagMode {
  const v = process.env["UZLEGAL_RAG"]?.trim().toLowerCase();
  if (v === "api" || v === "local") return v;
  return "auto";
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

  // auto: API mavjud bo'lsa — shu, aks holda lokal
  if (await checkApi()) {
    try {
      return await apiRetrieve(query, opts as ApiRetrieveOptions);
    } catch {
      // API xato berdi — lokal ga tushish
      apiChecked = false;
    }
  }

  return localRetrieve(query, opts);
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
