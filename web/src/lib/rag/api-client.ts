/**
 * Python yadro API orqali qidiruv — `/v1/search` endpoint mijozi.
 *
 * TS dagi lokal RAG oʻrniga Python yadroni ishlatish imkonini beradi.
 * Bu konsolidatsiyaning asosiy qismi: bitta RAG implementatsiyasi (Python),
 * barcha mijozlar (web, bot, CLI) shu orqali qidiradi.
 */

import { config } from "../config";
import type { Retrieved } from "../types";

interface ApiSearchResult {
  chunk_id: string;
  document: string;
  article: string | null;
  heading: string | null;
  text: string;
  score: number;
  source: string;
  url: string | null;
}

interface ApiSearchResponse {
  results: ApiSearchResult[];
  query_kind: string;
  total_hits: number;
  latency_ms: number;
  confident: boolean;
}

interface ApiStatsResponse {
  chunks: number;
  documents: number;
  embedder: string | null;
  kb_version: string | null;
  status: string;
}

export interface ApiRetrieveOptions {
  topK?: number;
  minScore?: number;
  documents?: string[];
}

function apiUrl(path: string): string {
  return `${config.uzlegalApiUrl}${path}`;
}

function headers(): Record<string, string> {
  const h: Record<string, string> = { "content-type": "application/json" };
  if (config.uzlegalApiKey) {
    h["authorization"] = `Bearer ${config.uzlegalApiKey}`;
  }
  return h;
}

/**
 * Python yadro orqali qidiruv.
 *
 * Xato yuz bersa exception otadi — chaqiruvchi fallback qilishi mumkin.
 */
export async function apiRetrieve(
  query: string,
  opts: ApiRetrieveOptions = {},
): Promise<Retrieved[]> {
  const { topK = 8, minScore, documents } = opts;

  const res = await fetch(apiUrl("/v1/search"), {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      query,
      top_k: topK,
      min_score: minScore ?? undefined,
      documents: documents ?? undefined,
    }),
    signal: AbortSignal.timeout(10_000),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Yadro qidiruv xatosi (${res.status}): ${body.slice(0, 300)}`);
  }

  const data = (await res.json()) as ApiSearchResponse;

  return data.results.map((r) => ({
    id: r.chunk_id,
    document: r.document,
    article: r.article ?? undefined,
    heading: r.heading ?? undefined,
    text: r.text,
    score: r.score,
    url: r.url ?? undefined,
    lang: "uz" as const,
    script: "latn" as const,
  }));
}

export async function apiStats(): Promise<ApiStatsResponse> {
  const res = await fetch(apiUrl("/v1/search/stats"), {
    headers: headers(),
    signal: AbortSignal.timeout(5_000),
  });

  if (!res.ok) {
    throw new Error(`Yadro statistika xatosi (${res.status})`);
  }

  return (await res.json()) as ApiStatsResponse;
}

/**
 * Yadro API mavjudligini tekshiradi.
 * Xato yuz bersa `false` qaytaradi — lokal RAG ga tushish kerak.
 */
export async function isApiAvailable(): Promise<boolean> {
  try {
    const res = await fetch(apiUrl("/v1/health"), {
      signal: AbortSignal.timeout(2_000),
    });
    return res.ok;
  } catch {
    return false;
  }
}
