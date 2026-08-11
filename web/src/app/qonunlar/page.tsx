"use client";

import { useEffect, useState } from "react";
import { apiJson, humanError } from "@/lib/ui/fetch";

interface SearchResult {
  score: number;
  document: string;
  article?: string;
  heading?: string;
  url?: string;
  text: string;
}

interface SearchResponse {
  query: string;
  count: number;
  corpus: {
    chunks: number;
    documents: Array<{ document: string; chunks: number }>;
    embedder?: string;
  };
  results: SearchResult[];
}

export default function CorpusPage() {
  const [query, setQuery] = useState("");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [corpus, setCorpus] = useState<SearchResponse["corpus"] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Sahifa ochilganda baza holatini olamiz.
  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((h: { corpus?: SearchResponse["corpus"] }) => {
        if (h.corpus) setCorpus(h.corpus);
      })
      .catch(() => {});
  }, []);

  async function search() {
    const q = query.trim();
    if (!q || busy) return;
    setBusy(true);
    setError("");
    try {
      const body = await apiJson<SearchResponse>(
        `/api/search?q=${encodeURIComponent(q)}&k=10`,
      );
      setData(body);
      setCorpus(body.corpus);
    } catch (err) {
      setError(humanError(err));
    } finally {
      setBusy(false);
    }
  }

  const empty = corpus && corpus.chunks === 0;

  return (
    <>
      <h1>Qonun bazasi</h1>
      <p className="lede">
        Bazadan toʻgʻridan-toʻgʻri qidirish. Modelga murojaat qilinmaydi — faqat
        matn qidiruvi, shuning uchun tez va bepul.
      </p>

      {empty && (
        <div className="notice">
          <b>Baza boʻsh.</b> Qonun matnlarini <span className="mono">data/corpus/</span>{" "}
          papkasiga joylang va terminalda <span className="mono">npm run ingest</span>{" "}
          buyrugʻini bajaring. Matnlarni{" "}
          <a href="https://lex.uz" target="_blank" rel="noopener noreferrer">
            lex.uz
          </a>{" "}
          saytidan olishingiz mumkin.
        </div>
      )}

      <div className="row">
        <input
          type="text"
          value={query}
          placeholder="masalan: sinov muddati, ishdan boʻshatish, 173-modda"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void search();
          }}
        />
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        <button onClick={() => void search()} disabled={busy || !query.trim()}>
          {busy ? "Qidirilmoqda…" : "Qidirish"}
        </button>
      </div>

      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}

      {busy && (
        <div aria-busy="true" aria-live="polite" style={{ marginTop: 18 }}>
          <span className="sr-only">Qidirilmoqda…</span>
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="skeleton" style={{ height: 96, marginBottom: 12 }} />
          ))}
        </div>
      )}

      {corpus && corpus.chunks > 0 && !busy && (
        <div className="card" style={{ marginTop: 18 }}>
          <h3>Bazadagi hujjatlar</h3>
          <dl className="kv">
            {corpus.documents.map((d) => (
              <div key={d.document} style={{ display: "contents" }}>
                <dt>{d.document}</dt>
                <dd>{d.chunks} boʻlak</dd>
              </div>
            ))}
          </dl>
          <p className="dim" style={{ fontSize: 13, marginTop: 8, marginBottom: 0 }}>
            Jami: {corpus.chunks} boʻlak · Embedder: {corpus.embedder ?? "—"}
          </p>
        </div>
      )}

      {data && !busy && (
        <>
          <h2>Natijalar ({data.count})</h2>
          {data.count === 0 && (
            <p className="dim">
              Hech narsa topilmadi. Boshqa soʻz bilan urinib koʻring — masalan
              modda raqami yoki qonun nomi bilan.
            </p>
          )}
          {data.results.map((r, i) => (
            <div key={i} className="card">
              <div className="row" style={{ justifyContent: "space-between" }}>
                <h3 style={{ margin: 0 }}>
                  {r.document}
                  {r.article ? ` · ${r.article}-modda` : ""}
                </h3>
                <span className="dim mono">{r.score.toFixed(3)}</span>
              </div>
              {r.heading && <p className="dim" style={{ margin: "4px 0 0" }}>{r.heading}</p>}
              <p style={{ margin: "8px 0 0", whiteSpace: "pre-wrap" }}>{r.text}</p>
              {r.url && (
                <a href={r.url} target="_blank" rel="noopener noreferrer">
                  Manba
                </a>
              )}
            </div>
          ))}
        </>
      )}
    </>
  );
}
