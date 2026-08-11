/**
 * uzlegal-ai yadrosi bilan gaplashadigan mijoz (`POST /v1/consult`).
 *
 * NEGA BU QATLAM BOR. Ilgari web qobig'i Claude SDK ni TO'G'RIDAN-TO'G'RI
 * chaqirardi: o'zi qidirar, o'zi prompt yig'ar, o'zi javobni tekshirardi.
 * Birlashtirishdan keyin bu ish yadroga o'tadi — qidiruv, agentlar,
 * groundedness gate va iqtiboslar o'sha yerda. Qobiq faqat savolni uzatadi
 * va javobni ko'rsatadi.
 *
 * MUHIM FARQ: `/v1/consult/stream` TOKEN oqimi emas, BOSQICH oqimi.
 * Yakuniy javob oqim oxirida bir marta keladi, chunki gate uni to'liq matn
 * ustida tekshiradi — bo'lak-bo'lak yuborish tasdiqlanmagan matnni
 * ko'rsatish bo'lardi. Shuning uchun qobiqda "yozilmoqda" effekti yo'q,
 * uning o'rniga bosqich nomlari ko'rsatiladi.
 */

import { config } from "../config";
import type { Citation } from "../types";

// ── Yadro shakllari (uzlegal/core.py dagi model bilan bir xil) ─────────────

export interface ConsultRequest {
  question: string;
  mode?: "auto" | "simple" | "standard" | "complex";
  agents?: string[];
  as_of?: string;
  lang?: "uz" | "ru" | "en";
  client_position?: string;
  max_tokens?: number;
  trace?: boolean;
}

export interface ConsultCitation {
  tag: string;
  doc_id: string;
  doc_title?: string | null;
  doc_type?: string | null;
  article: string;
  part?: string | null;
  version?: string | null;
  status?: "in_force" | "superseded" | "repealed";
  url?: string | null;
  excerpt?: string | null;
}

export interface ConsultResult {
  trace_id: string;
  answer: string;
  citations: ConsultCitation[];
  confidence: number;
  caveats: string[];
  mode_used: string;
  latency_ms: number;
  kb_version: string;
  disclaimer: string;
}

/** Oqim hodisasi. `step` — bosqich, `answer` — yakuniy natija. */
export type ConsultStreamEvent =
  | { type: "step"; node: string; ms: number }
  | { type: "answer"; result: ConsultResult }
  | { type: "error"; message: string }
  | { type: "done" };

// ── Xatolar ────────────────────────────────────────────────────────────────

export class UzlegalError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "UzlegalError";
  }
}

/** Foydalanuvchiga ko'rsatiladigan o'zbekcha xato matni. */
export function uzlegalHumanError(err: unknown): string {
  if (err instanceof UzlegalError) {
    if (err.status === undefined) {
      return (
        `Yuridik yadro (${config.uzlegalApiUrl}) javob bermadi. ` +
        `Server ishga tushganini tekshiring.`
      );
    }
    if (err.status === 401 || err.status === 403) {
      return "Yadroga kirish rad etildi — UZLEGAL_API_KEY notoʻgʻri yoki yoʻq.";
    }
    if (err.status === 400 || err.status === 422) {
      return `Savol qabul qilinmadi: ${err.message}`;
    }
    if (err.status === 429) {
      return "Soʻrovlar chegarasi oshdi. Bir necha daqiqadan keyin urinib koʻring.";
    }
    return `Yadroda xato (${err.status}): ${err.message}`;
  }
  return "Kutilmagan xato yuz berdi. Birozdan keyin qayta urinib koʻring.";
}

// ── So'rov ────────────────────────────────────────────────────────────────

function headers(stream: boolean): Record<string, string> {
  const h: Record<string, string> = { "content-type": "application/json" };
  if (stream) h["accept"] = "text/event-stream";
  if (config.uzlegalApiKey) h["authorization"] = `Bearer ${config.uzlegalApiKey}`;
  return h;
}

async function post(path: string, body: ConsultRequest, stream: boolean): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`${config.uzlegalApiUrl}${path}`, {
      method: "POST",
      headers: headers(stream),
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(config.uzlegalTimeoutMs),
    });
  } catch (err) {
    // Ulanmadi, DNS topilmadi yoki vaqt tugadi — status yo'q.
    throw new UzlegalError(err instanceof Error ? err.message : String(err));
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new UzlegalError(errorDetail(text) || res.statusText, res.status);
  }
  return res;
}

/** FastAPI xatosidan tushunarli matn ajratadi. */
function errorDetail(raw: string): string {
  try {
    const j = JSON.parse(raw) as { detail?: unknown; error?: { message?: string } };
    if (j.error?.message) return j.error.message;
    if (typeof j.detail === "string") return j.detail;
    if (Array.isArray(j.detail)) {
      // Pydantic validatsiya xatosi.
      return j.detail
        .map((d) => (d as { msg?: string }).msg ?? "")
        .filter(Boolean)
        .join("; ");
    }
  } catch {
    // JSON emas — xom matnni qaytaramiz.
  }
  return raw.slice(0, 200);
}

/** Streamingsiz maslahat. */
export async function consult(req: ConsultRequest): Promise<ConsultResult> {
  const res = await post("/v1/consult", req, false);
  return (await res.json()) as ConsultResult;
}

/**
 * Oqimli maslahat. Har bosqich tugagach hodisa keladi, javob esa oxirida.
 */
export async function* consultStream(
  req: ConsultRequest,
): AsyncGenerator<ConsultStreamEvent, void, unknown> {
  // Bosqichlar izdan o'qiladi, shuning uchun iz majburiy.
  const res = await post("/v1/consult/stream", { ...req, trace: true }, true);
  if (!res.body) {
    throw new UzlegalError("Yadro boʻsh oqim qaytardi.", res.status);
  }

  for await (const { event, data } of readSseEvents(res.body)) {
    if (event === "step") {
      const d = data as { node?: string; ms?: number };
      yield { type: "step", node: d.node ?? "", ms: d.ms ?? 0 };
    } else if (event === "answer") {
      yield { type: "answer", result: data as ConsultResult };
    } else if (event === "error") {
      const d = data as { detail?: string };
      yield { type: "error", message: d.detail ?? "Nomaʼlum xato" };
    } else if (event === "done") {
      yield { type: "done" };
    }
  }
}

/**
 * SSE oqimini hodisalarga ajratadi.
 *
 * Bo'laklar hodisa chegarasida kelishi SHART EMAS — bitta `data:` satri
 * ikkita TCP bo'lakka bo'linishi mumkin. Shuning uchun bufer saqlanadi va
 * faqat to'liq hodisa (bo'sh satr bilan tugagan) o'qiladi.
 */
async function* readSseEvents(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<{ event: string; data: unknown }, void, unknown> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);

        let event = "message";
        const dataLines: string[] = [];
        for (const line of raw.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
        }
        if (dataLines.length === 0) continue;

        try {
          yield { event, data: JSON.parse(dataLines.join("\n")) };
        } catch {
          // Buzuq JSON — hodisa tashlab yuboriladi, oqim davom etadi.
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// ── Shakllarni qobiq tiliga o'tkazish ──────────────────────────────────────

/** Yadro iqtiboslarini qobiqdagi `Citation` shakliga keltiradi. */
export function toWebCitations(citations: ConsultCitation[]): Citation[] {
  return citations.map((c) => ({
    document: c.doc_title ?? c.doc_id,
    article: c.article,
    heading: c.part ? `${c.article}-modda, ${c.part}-qism` : undefined,
    url: c.url ?? undefined,
    snippet: c.excerpt ?? "",
  }));
}

/** Bosqich nomini foydalanuvchiga ko'rsatiladigan matnga aylantiradi. */
export function stepLabel(node: string): string {
  return STEP_LABELS[node] ?? `${node} bosqichi…`;
}

/**
 * Yadro bosqichlarining o'zbekcha nomlari.
 *
 * Ro'yxatda yo'q bosqich uchun xom nom ko'rsatiladi — yadroga yangi bosqich
 * qo'shilsa qobiq buzilmasin, shunchaki tarjimasiz chiqsin.
 */
const STEP_LABELS: Record<string, string> = {
  router: "Savol turi aniqlanmoqda…",
  retrieval: "Qonun bazasidan qidirilmoqda…",
  rerank: "Topilgan manbalar saralanmoqda…",
  jurist: "Yurist javob tayyorlamoqda…",
  advocate: "Himoyachi nuqtai nazari…",
  prosecutor: "Qarshi dalillar tekshirilmoqda…",
  judge: "Yakuniy xulosa chiqarilmoqda…",
  gate: "Iqtiboslar tekshirilmoqda…",
  synthesis: "Javob yigʻilmoqda…",
};
