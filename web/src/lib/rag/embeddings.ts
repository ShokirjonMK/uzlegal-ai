/**
 * Matnni vektorga aylantirish (embedding).
 *
 * Ikki provayder:
 *  - `voyage` — Voyage AI (Anthropic tavsiya qiladi). Sifatli, kalit kerak.
 *  - `local`  — tashqi xizmatsiz zaxira. Belgi n-grammalarini xeshlaydi.
 *               Sifati pastroq, lekin o'zbekcha morfologiyaga (qo'shimchalar
 *               ko'p o'zgaradi) n-gramma yondashuvi yomon emas.
 */

import { config } from "../config";
import { foldForSearch } from "../uz/orthography";

/** Lokal embedding o'lchami. */
const LOCAL_DIM = 512;

export interface Embedder {
  readonly name: string;
  readonly dim: number;
  /** Hujjat bo'laklarini vektorlashtirish. */
  embedDocuments(texts: string[]): Promise<Float32Array[]>;
  /** Qidiruv so'rovini vektorlashtirish. */
  embedQuery(text: string): Promise<Float32Array>;
}

// ── Voyage AI ──────────────────────────────────────────────────────────────

interface VoyageResponse {
  data: Array<{ embedding: number[]; index: number }>;
}

class VoyageEmbedder implements Embedder {
  readonly name: string;
  /** Voyage o'lchamni javobda qaytaradi; birinchi chaqiruvda aniqlanadi. */
  dim = 0;

  constructor(
    private readonly apiKey: string,
    private readonly model: string,
  ) {
    this.name = `voyage:${model}`;
  }

  private async call(
    texts: string[],
    inputType: "document" | "query",
  ): Promise<Float32Array[]> {
    const res = await fetch("https://api.voyageai.com/v1/embeddings", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        input: texts,
        model: this.model,
        input_type: inputType,
      }),
    });

    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(
        `Voyage AI xatoligi (${res.status}): ${body.slice(0, 300)}`,
      );
    }

    const json = (await res.json()) as VoyageResponse;
    const sorted = [...json.data].sort((a, b) => a.index - b.index);
    const vectors = sorted.map((d) => normalize(Float32Array.from(d.embedding)));
    if (vectors.length > 0 && this.dim === 0) {
      this.dim = vectors[0]!.length;
    }
    return vectors;
  }

  async embedDocuments(texts: string[]): Promise<Float32Array[]> {
    const out: Float32Array[] = [];
    // Voyage bir so'rovda cheklangan miqdorni qabul qiladi — bo'lib yuboramiz.
    const BATCH = 64;
    for (let i = 0; i < texts.length; i += BATCH) {
      out.push(...(await this.call(texts.slice(i, i + BATCH), "document")));
    }
    return out;
  }

  async embedQuery(text: string): Promise<Float32Array> {
    const [v] = await this.call([text], "query");
    if (!v) throw new Error("Voyage AI boʻsh javob qaytardi.");
    return v;
  }
}

// ── Lokal (offline) zaxira ─────────────────────────────────────────────────

/**
 * Belgi n-grammalarini xeshlab vektorga soladi.
 * Tashqi xizmatsiz ishlaydi; semantik emas, leksik o'xshashlikni topadi.
 */
class LocalEmbedder implements Embedder {
  // v2 — `foldForSearch` apostrofni olib tashlaydigan bo'ldi, ya'ni
  // n-grammalar ham o'zgardi. Nom o'zgarganda `getMeta("embedder")` eski
  // bazani sezadi va qayta yuklash kerakligi ma'lum bo'ladi.
  readonly name = "local:hashed-ngrams-v2";
  readonly dim = LOCAL_DIM;

  private embedOne(text: string): Float32Array {
    const v = new Float32Array(LOCAL_DIM);
    const s = ` ${foldForSearch(text).replace(/[^\p{L}\p{N}]+/gu, " ").trim()} `;

    // 3–5 belgili n-grammalar.
    for (let n = 3; n <= 5; n++) {
      for (let i = 0; i + n <= s.length; i++) {
        const gram = s.slice(i, i + n);
        if (gram.trim().length === 0) continue;
        const h = fnv1a(gram) % LOCAL_DIM;
        // Ishorani ham xeshdan olamiz — to'qnashuvlar bir-birini yo'qotsin.
        v[h] = (v[h] ?? 0) + ((fnv1a(gram + "#") & 1) === 0 ? 1 : -1);
      }
    }
    return normalize(v);
  }

  async embedDocuments(texts: string[]): Promise<Float32Array[]> {
    return texts.map((t) => this.embedOne(t));
  }

  async embedQuery(text: string): Promise<Float32Array> {
    return this.embedOne(text);
  }
}

function fnv1a(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

// ── Umumiy ─────────────────────────────────────────────────────────────────

/** Vektorni birlik uzunlikka keltiradi (kosinus o'xshashlik uchun). */
export function normalize(v: Float32Array): Float32Array {
  let sum = 0;
  for (let i = 0; i < v.length; i++) sum += v[i]! * v[i]!;
  const norm = Math.sqrt(sum);
  if (norm === 0) return v;
  for (let i = 0; i < v.length; i++) v[i] = v[i]! / norm;
  return v;
}

/** Ikki normallashtirilgan vektor orasidagi kosinus o'xshashlik. */
export function cosine(a: Float32Array, b: Float32Array): number {
  const n = Math.min(a.length, b.length);
  let dot = 0;
  for (let i = 0; i < n; i++) dot += a[i]! * b[i]!;
  return dot;
}

let cached: Embedder | null = null;

/** Sozlamaga mos embedder. */
export function getEmbedder(): Embedder {
  if (cached) return cached;

  if (config.embeddingProvider === "voyage") {
    const key = config.voyageApiKey;
    if (!key) {
      throw new Error(
        "EMBEDDING_PROVIDER=voyage, lekin VOYAGE_API_KEY sozlanmagan. " +
          "Kalitni qoʻshing yoki EMBEDDING_PROVIDER=local qiling.",
      );
    }
    cached = new VoyageEmbedder(key, config.voyageModel);
  } else {
    cached = new LocalEmbedder();
  }
  return cached;
}

/** Testlar uchun keshni tozalash. */
export function resetEmbedder(): void {
  cached = null;
}
