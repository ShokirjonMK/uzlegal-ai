"use client";

import { useState } from "react";
import { apiJson, humanError } from "@/lib/ui/fetch";
import { NusxaTugma, YuklabOlishTugma } from "@/components/ui/nusxa";
import type { AnalyzeResult, ReviewResult } from "@/lib/types";

type Mode = "tahlil" | "tekshiruv";

function faylTanasi(file: File, perspective: string): FormData {
  const form = new FormData();
  form.append("file", file);
  if (perspective.trim()) form.append("perspective", perspective.trim());
  return form;
}

/** Natijani nusxalash va yuklab olish uchun oʻqiladigan matnga aylantiradi. */
function tahlilMatni(r: AnalyzeResult): string {
  const lines = [
    `# ${r.documentType}`,
    "",
    r.summary,
    "",
    `## Xavflar (${r.risks.length})`,
  ];
  r.risks.forEach((risk, i) => {
    lines.push(
      "",
      `### ${i + 1}. ${risk.title} — ${risk.level}`,
      risk.location ? `Joyi: ${risk.location}` : "",
      risk.explanation,
      `Tavsiya: ${risk.recommendation}`,
      risk.legalBasis ? `Asos: ${risk.legalBasis}` : "",
    );
  });
  if (r.missingClauses.length) {
    lines.push("", "## Yetishmayotgan shartlar", ...r.missingClauses.map((m) => `- ${m}`));
  }
  lines.push("", "## Xulosa", r.conclusion);
  return lines.filter((l) => l !== "").join("\n");
}

function tekshiruvMatni(r: ReviewResult): string {
  const lines = [`# Tekshiruv natijasi — ${r.score}/100`, ""];
  for (const c of r.checks) {
    lines.push(`## ${c.title} — ${c.status}`, c.detail);
    if (c.legalBasis) lines.push(`Asos: ${c.legalBasis}`);
    lines.push("");
  }
  lines.push("## Xulosa", r.summary);
  return lines.join("\n");
}

export default function AnalyzePage() {
  const [mode, setMode] = useState<Mode>("tahlil");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [perspective, setPerspective] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [analysis, setAnalysis] = useState<AnalyzeResult | null>(null);
  const [reviewResult, setReviewResult] = useState<ReviewResult | null>(null);

  async function run() {
    if (busy) return;
    if (!file && !text.trim()) {
      setError("Fayl yuklang yoki hujjat matnini kiriting.");
      return;
    }

    setBusy(true);
    setError("");
    setAnalysis(null);
    setReviewResult(null);

    try {
      const endpoint = mode === "tahlil" ? "/api/analyze" : "/api/review";

      const init: RequestInit = file
        ? { method: "POST", body: faylTanasi(file, perspective) }
        : {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({
              text,
              perspective: perspective.trim() || undefined,
            }),
          };

      const body = await apiJson<AnalyzeResult | ReviewResult>(endpoint, init);

      if (mode === "tahlil") setAnalysis(body as AnalyzeResult);
      else setReviewResult(body as ReviewResult);
    } catch (err) {
      setError(humanError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Hujjat tahlili</h1>
      <p className="lede">
        Shartnoma yoki boshqa hujjatni yuklang. <b>Tahlil</b> — xavflarni va
        yetishmayotgan shartlarni topadi. <b>Tekshiruv</b> — majburiy talablar
        boʻyicha nuqta-ma-nuqta baholaydi.
      </p>

      <div className="row" style={{ marginBottom: 14 }}>
        <button
          className={mode === "tahlil" ? "" : "ghost"}
          aria-pressed={mode === "tahlil"}
          onClick={() => setMode("tahlil")}
          disabled={busy}
        >
          Tahlil
        </button>
        <button
          className={mode === "tekshiruv" ? "" : "ghost"}
          aria-pressed={mode === "tekshiruv"}
          onClick={() => setMode("tekshiruv")}
          disabled={busy}
        >
          Tekshiruv
        </button>
      </div>

      <label htmlFor="file">Fayl (PDF, DOCX, TXT, MD, HTML — 25 MB gacha)</label>
      <input
        id="file"
        type="file"
        accept=".pdf,.docx,.txt,.md,.html,.htm"
        disabled={busy}
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />

      <label htmlFor="text">…yoki matnni shu yerga qoʻying</label>
      <textarea
        id="text"
        rows={7}
        value={text}
        disabled={busy || Boolean(file)}
        placeholder={file ? "Fayl tanlangan" : "Hujjat matni…"}
        onChange={(e) => setText(e.target.value)}
      />

      {mode === "tahlil" && (
        <>
          <label htmlFor="persp">Kim nuqtai nazaridan? (ixtiyoriy)</label>
          <input
            id="persp"
            type="text"
            value={perspective}
            disabled={busy}
            placeholder="masalan: ijarachi, ishchi, buyurtmachi"
            onChange={(e) => setPerspective(e.target.value)}
          />
        </>
      )}

      <div className="row" style={{ marginTop: 14 }}>
        <button onClick={() => void run()} disabled={busy}>
          {busy
            ? "Tahlil qilinmoqda… (1–2 daqiqa)"
            : mode === "tahlil"
              ? "Tahlil qilish"
              : "Tekshirish"}
        </button>
        {(file || text) && (
          <button
            className="ghost"
            disabled={busy}
            onClick={() => {
              setFile(null);
              setText("");
              setAnalysis(null);
              setReviewResult(null);
              setError("");
            }}
          >
            Tozalash
          </button>
        )}
      </div>

      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}

      {/* Uzoq kutishda boʻsh ekran qolmasligi uchun skelet koʻrsatiladi. */}
      {busy && (
        <section style={{ marginTop: 26 }} aria-busy="true" aria-live="polite">
          <p className="status">
            {mode === "tahlil" ? "Hujjat tahlil qilinmoqda" : "Hujjat tekshirilmoqda"}
            … Odatda 1–2 daqiqa oladi.
          </p>
          <div className="skeleton" style={{ height: 22, width: "45%", marginBottom: 14 }} />
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="skeleton" style={{ height: 104, marginBottom: 12 }} />
          ))}
        </section>
      )}

      {analysis && !busy && (
        <>
          <div className="actions" style={{ marginTop: 20 }}>
            <NusxaTugma matn={tahlilMatni(analysis)} nom="Natijani nusxalash" />
            <YuklabOlishTugma matn={tahlilMatni(analysis)} fayl="hujjat-tahlili.md" />
          </div>
          <AnalysisView r={analysis} />
        </>
      )}

      {reviewResult && !busy && (
        <>
          <div className="actions" style={{ marginTop: 20 }}>
            <NusxaTugma matn={tekshiruvMatni(reviewResult)} nom="Natijani nusxalash" />
            <YuklabOlishTugma matn={tekshiruvMatni(reviewResult)} fayl="tekshiruv.md" />
          </div>
          <ReviewView r={reviewResult} />
        </>
      )}

      <p className="disclaimer">
        ⚠️ Bu — avtomatik tahlil, yuridik maslahat emas. Muhim hujjatlarni
        imzolashdan oldin advokatga koʻrsating.
      </p>
    </>
  );
}

function AnalysisView({ r }: { r: AnalyzeResult }) {
  return (
    <section style={{ marginTop: 26 }}>
      <h2>{r.documentType}</h2>
      <p>{r.summary}</p>

      {r.parties.length > 0 && (
        <div className="card">
          <h3>Tomonlar</h3>
          <dl className="kv">
            {r.parties.map((p, i) => (
              <div key={i} style={{ display: "contents" }}>
                <dt>{p.role}</dt>
                <dd>{p.name}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {r.keyTerms.length > 0 && (
        <div className="card">
          <h3>Muhim shartlar</h3>
          <dl className="kv">
            {r.keyTerms.map((k, i) => (
              <div key={i} style={{ display: "contents" }}>
                <dt>{k.label}</dt>
                <dd>{k.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      <h2>Xavflar ({r.risks.length})</h2>
      {r.risks.length === 0 && <p className="dim">Jiddiy xavf aniqlanmadi.</p>}
      {r.risks.map((risk, i) => (
        <div key={i} className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0 }}>
              {i + 1}. {risk.title}
            </h3>
            <span className={`badge ${risk.level === "oʻrta" ? "orta" : risk.level}`}>
              {risk.level}
            </span>
          </div>
          {risk.location && (
            <p className="dim" style={{ fontSize: 13, margin: "6px 0 0" }}>
              Joyi: {risk.location}
            </p>
          )}
          <p style={{ margin: "8px 0 0" }}>{risk.explanation}</p>
          <p style={{ margin: "8px 0 0" }}>
            <b>Tavsiya:</b> {risk.recommendation}
          </p>
          {risk.legalBasis && (
            <p className="dim" style={{ fontSize: 13, margin: "6px 0 0" }}>
              📖 {risk.legalBasis}
            </p>
          )}
        </div>
      ))}

      {r.missingClauses.length > 0 && (
        <>
          <h2>Yetishmayotgan shartlar</h2>
          <ul className="tight">
            {r.missingClauses.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </>
      )}

      <h2>Xulosa</h2>
      <p>{r.conclusion}</p>
    </section>
  );
}

function ReviewView({ r }: { r: ReviewResult }) {
  const cls = (s: string) =>
    s === "oʻtdi" ? "otdi" : s === "oʻtmadi" ? "otmadi" : s;

  return (
    <section style={{ marginTop: 26 }}>
      <h2>Umumiy baho: {r.score}/100</h2>
      {r.checks.map((c) => (
        <div key={c.id} className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0 }}>{c.title}</h3>
            <span className={`badge ${cls(c.status)}`}>{c.status}</span>
          </div>
          <p style={{ margin: "8px 0 0" }}>{c.detail}</p>
          {c.legalBasis && (
            <p className="dim" style={{ fontSize: 13, margin: "6px 0 0" }}>
              📖 {c.legalBasis}
            </p>
          )}
        </div>
      ))}
      <h2>Xulosa</h2>
      <p>{r.summary}</p>
    </section>
  );
}
