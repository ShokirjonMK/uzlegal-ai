/**
 * Qonun bazasidan tegishli bo'laklarni topish.
 *
 * Gibrid qidiruv: vektor (semantik) + kalit so'z (leksik).
 * O'zbek tilida bu ayniqsa muhim — foydalanuvchi "ishdan bo'shatish" desa,
 * matnda "mehnat shartnomasini bekor qilish" yozilgan bo'lishi mumkin
 * (vektor topadi), lekin "173-modda" deb so'rasa — aniq moslik kerak
 * (kalit so'z topadi).
 */

import { config } from "../config";
import { cosine, getEmbedder } from "./embeddings";
import { getMeta, loadAll, type StoredChunk } from "./store";
import { foldForSearch } from "../uz/orthography";
import type { Citation, Retrieved } from "../types";

/** Vektor va kalit so'z ballarining nisbati. */
const VECTOR_WEIGHT = 0.7;
const KEYWORD_WEIGHT = 0.3;

/** Qidiruvda hisobga olinmaydigan yordamchi so'zlar. */
const STOPWORDS = new Set([
  "va", "bilan", "uchun", "yoki", "ammo", "lekin", "agar", "bu", "shu", "u",
  "men", "siz", "biz", "ular", "ham", "emas", "yoq", "bor", "qanday", "nima",
  "и", "в", "не", "на", "что", "как", "для", "или", "это", "то",
  "the", "and", "is", "are", "of", "to", "in", "for", "a", "an", "on",
]);

/**
 * So'rovda hisobga olinadigan eng ko'p token soni.
 *
 * NEGA CHEGARA BOR. Ilgari tokenlar na takrorlanishdan tozalanardi, na
 * cheklanardi: 2000 bo'lak × 2000 token o'lchovda event loop ni 15.5 soniya
 * bloklagan (audit #24). Ya'ni bitta uzun so'rov butun serverni muzlatardi.
 * O'ttiz ikkita ma'noli so'z har qanday haqiqiy savol uchun yetarli.
 */
const MAX_QUERY_TOKENS = 32;

/**
 * O'zbek tili agglyutinativ: qo'shimchalar so'z OXIRIGA ketma-ket ulanadi.
 * Shuning uchun eng ko'p uchraydigan qo'shimchalar navbat bilan qirqiladi.
 *
 *     shartnomaning   → shartnoma
 *     shartnomasining → shartnomasi → shartnoma   ← ikkalasi bir xil o'zak
 *     qilinishi       → qil
 *     qilish          → qil
 *
 * Shu bilan "shartnomaning" so'rovi "shartnomasining" matnida topiladi
 * (audit #12) — ilgari topilmasdi.
 *
 * Uzunroq qo'shimcha oldin turadi, aks holda `inishi` ni `i` yeb qo'yadi.
 */
const SUFFIXES = [
  "larining", "lariga", "laridan", "larida", "larini", "larni",
  "inishi", "ilishi", "nishi", "lishi", "ishi",
  "ning", "lari", "lar", "dan", "gacha", "dagi", "ining",
  "ish", "ga", "da", "ni", "si", "i",
];

/** O'zakdan keyin qolishi shart bo'lgan eng kam belgi. */
const MIN_STEM = 3;

function stem(word: string): string {
  let w = word;
  // Ikki bosqich yetadi: `shartnomasining` → `shartnomasi` → `shartnoma`.
  for (let round = 0; round < 2; round++) {
    const before = w;
    for (const suf of SUFFIXES) {
      if (w.length - suf.length >= MIN_STEM && w.endsWith(suf)) {
        w = w.slice(0, -suf.length);
        break;
      }
    }
    if (w === before) break;
  }
  return w;
}

/** Matnni qidiruv o'zaklariga ajratadi. */
function stems(text: string): string[] {
  const out: string[] = [];
  for (const w of foldForSearch(text).split(/[^\p{L}\p{N}]+/u)) {
    if (w.length >= 3 && !STOPWORDS.has(w)) out.push(stem(w));
  }
  return out;
}

/** So'rov o'zaklari: takrorsiz va cheklangan. */
function queryStems(text: string): string[] {
  return [...new Set(stems(text))].slice(0, MAX_QUERY_TOKENS);
}

/**
 * Bo'lak o'zaklari, bo'lak obyektiga bog'lab keshlanadi.
 *
 * `chunk.folded` ustunidan FOYDALANILMAYDI: u baza yozilgan paytdagi
 * `foldForSearch` bilan hisoblangan va funksiya o'zgarsa jimgina eskiradi.
 * Matnning o'zidan hisoblash bu butun xatolar sinfini yo'q qiladi.
 */
const stemCache = new WeakMap<StoredChunk, Set<string>>();

function chunkStems(c: StoredChunk): Set<string> {
  let s = stemCache.get(c);
  if (!s) {
    s = new Set(stems(`${c.document} ${c.heading ?? ""} ${c.text}`));
    stemCache.set(c, s);
  }
  return s;
}

/** So'rovda modda raqami ko'rsatilganmi? "173-modda", "статья 173". */
function extractArticleRefs(query: string): string[] {
  const out = new Set<string>();
  const patterns = [
    /(\d+)\s*-?\s*(?:modda|модда)/gi,
    /(?:статья|ст\.)\s*(\d+)/gi,
    /(?:article|art\.)\s*(\d+)/gi,
  ];
  for (const re of patterns) {
    for (const m of query.matchAll(re)) {
      if (m[1]) out.add(m[1]);
    }
  }
  return [...out];
}

/**
 * Kalit so'z bali: so'rov o'zaklarining bo'lakda uchrashi.
 * Kamdan-kam uchraydigan o'zaklar ko'proq ball beradi (IDF ga o'xshash).
 *
 * Moslik SO'Z darajasida — ilgari `folded.includes(t)` qism satr bo'yicha
 * tekshirardi va `kor` so'rovi `bekor` ichidan, `nat` esa `mehnat` ichidan
 * topilardi (audit #52). Bu ham natijani, ham IDF ni buzardi.
 */
function keywordScore(
  qStems: string[],
  chunk: StoredChunk,
  idf: Map<string, number>,
): number {
  if (qStems.length === 0) return 0;
  const have = chunkStems(chunk);
  let score = 0;
  let maxScore = 0;
  for (const t of qStems) {
    const weight = idf.get(t) ?? 1;
    maxScore += weight;
    if (have.has(t)) score += weight;
  }
  return maxScore > 0 ? score / maxScore : 0;
}

function buildIdf(chunks: StoredChunk[], qStems: string[]): Map<string, number> {
  const idf = new Map<string, number>();
  const n = Math.max(chunks.length, 1);
  for (const t of qStems) {
    let df = 0;
    for (const c of chunks) if (chunkStems(c).has(t)) df++;
    idf.set(t, Math.log((n + 1) / (df + 1)) + 1);
  }
  return idf;
}

export interface RetrieveOptions {
  topK?: number;
  /** Shu ostidagi ballar tashlab yuboriladi. */
  minScore?: number;
  /** Faqat shu hujjatlar ichidan qidirish. */
  documents?: string[];
}

/**
 * Baza boshqa embedder bilan yozilgan bo'lsa ogohlantiradi.
 *
 * Ilgari bu holat JIMGINA sodir bo'lardi (audit #14): embedder almashsa
 * (masalan `local` → `voyage`, yoki folding o'zgarib `v2` ga o'tsa) eski
 * vektorlar 0 ball oladi, xato ham, log ham chiqmaydi — qidiruv shunchaki
 * yomonlashadi va buni hech kim sezmaydi.
 *
 * Bir marta chiqadi, keyin jim bo'ladi — har so'rovda log to'ldirmasin.
 */
let embedderMismatchWarned = false;

function warnIfStaleEmbedder(): void {
  if (embedderMismatchWarned) return;
  const stored = getMeta("embedder");
  const current = getEmbedder().name;
  if (stored && stored !== current) {
    embedderMismatchWarned = true;
    console.warn(
      `[rag] Baza "${stored}" embedderi bilan yozilgan, hozir "${current}" ` +
        `ishlatilmoqda. Vektor qidiruvi ishonchsiz. Yechim: npm run ingest`,
    );
  }
}

/** So'rovga eng mos qonun bo'laklarini qaytaradi. */
export async function retrieve(
  query: string,
  opts: RetrieveOptions = {},
): Promise<Retrieved[]> {
  const { topK = 8, minScore = config.ragMinScore, documents } = opts;

  warnIfStaleEmbedder();

  let chunks = loadAll();
  if (chunks.length === 0) return [];
  if (documents?.length) {
    const allow = new Set(documents);
    chunks = chunks.filter((c) => allow.has(c.document));
    if (chunks.length === 0) return [];
  }

  const qStems = queryStems(query);
  const idf = buildIdf(chunks, qStems);
  const articleRefs = extractArticleRefs(query);

  let queryVec: Float32Array | null = null;
  try {
    queryVec = await getEmbedder().embedQuery(query);
  } catch {
    // Embedding xizmati ishlamasa — faqat kalit so'z bo'yicha qidiramiz.
    queryVec = null;
  }

  const scored = chunks.map((c) => {
    const vec =
      queryVec && c.embedding.length === queryVec.length
        ? Math.max(0, cosine(queryVec, c.embedding))
        : 0;
    const kw = keywordScore(qStems, c, idf);

    let score = queryVec
      ? VECTOR_WEIGHT * vec + KEYWORD_WEIGHT * kw
      : kw;

    // So'rovda modda raqami aniq ko'rsatilgan bo'lsa — kuchli ustunlik.
    if (c.article && articleRefs.includes(c.article)) score += 0.5;

    return { ...c, score };
  });

  return scored
    .filter((c) => c.score >= minScore)
    .sort((a, b) => b.score - a.score)
    .slice(0, topK)
    .map(({ folded: _folded, embedding: _embedding, ...rest }) => rest);
}

/** Topilgan bo'laklardan javobda ko'rsatiladigan havolalar yasaydi. */
export function toCitations(chunks: Retrieved[], snippetChars = 240): Citation[] {
  return chunks.map((c) => ({
    document: c.document,
    article: c.article,
    heading: c.heading,
    url: c.url,
    snippet:
      c.text.length > snippetChars
        ? `${c.text.slice(0, snippetChars).trimEnd()}…`
        : c.text,
  }));
}
