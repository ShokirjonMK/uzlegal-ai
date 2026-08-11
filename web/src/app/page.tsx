"use client";

import { useEffect, useRef, useState } from "react";
import { readSse } from "@/lib/util/sse";
import { apiStream, humanError } from "@/lib/ui/fetch";
import { NusxaTugma, YuklabOlishTugma } from "@/components/ui/nusxa";
import type { Citation, ChatMessage } from "@/lib/types";

interface Turn extends ChatMessage {
  citations?: Citation[];
}

const EXAMPLES = [
  "Ish beruvchi meni ogohlantirmasdan ishdan boʻshata oladimi?",
  "Ijara shartnomasini muddatidan oldin bekor qilish mumkinmi?",
  "Daʼvo muddati qancha va qachondan boshlab hisoblanadi?",
];

export default function ChatPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns, status]);

  async function send(question: string) {
    const q = question.trim();
    if (!q || busy) return;

    setError("");
    setInput("");
    setBusy(true);
    setStatus("Yuborilmoqda…");

    const history = turns.map(({ role, content }) => ({ role, content }));
    setTurns((t) => [
      ...t,
      { role: "user", content: q },
      { role: "assistant", content: "" },
    ]);

    try {
      const res = await apiStream("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: q, history }),
      });

      for await (const event of readSse(res)) {
        switch (event.type) {
          case "status":
            setStatus(event.message);
            break;
          case "citations":
            setTurns((t) => {
              const next = [...t];
              const last = next.at(-1);
              if (last) last.citations = event.citations;
              return next;
            });
            break;
          case "delta":
            setStatus("");
            setTurns((t) => {
              const next = [...t];
              const last = next.at(-1);
              if (last) last.content += event.text;
              return next;
            });
            break;
          case "error":
            setError(event.message);
            break;
          case "done":
            setStatus("");
            break;
        }
      }
    } catch (err) {
      setError(humanError(err));
    } finally {
      setBusy(false);
      setStatus("");
    }
  }

  return (
    <>
      <h1>Huquqiy savol-javob</h1>
      <p className="lede">
        Oʻzbekiston qonunchiligi boʻyicha savolingizni bering. Javobda qonun
        bazasidan topilgan moddalarga havola beriladi. Oʻzbek, rus va ingliz
        tillarini tushunadi.
      </p>

      {turns.length === 0 && (
        <div className="card">
          <h3>Namuna savollar</h3>
          <ul className="tight">
            {/* Havola emas, tugma: klaviatura va ekran oʻqiguch uchun toʻgʻri. */}
            {EXAMPLES.map((e) => (
              <li key={e}>
                <button
                  type="button"
                  className="namuna"
                  disabled={busy}
                  onClick={() => void send(e)}
                >
                  {e}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="messages">
        {turns.map((turn, i) => (
          <div key={i} className={`msg ${turn.role}`}>
            <div className="who">{turn.role === "user" ? "Siz" : "AI Lawyer"}</div>
            {turn.citations && turn.citations.length > 0 && (
              <Sources citations={turn.citations} />
            )}
            <div className="body">
              {turn.content || (turn.role === "assistant" && !status ? "…" : "")}
            </div>
            {/* Javob tugagach — nusxalash va yuklab olish. */}
            {turn.role === "assistant" && turn.content && !busy && (
              <div className="actions">
                <NusxaTugma matn={turn.content} />
                <YuklabOlishTugma
                  matn={turn.content}
                  fayl={`javob-${i + 1}.md`}
                />
              </div>
            )}
          </div>
        ))}
        {/* Holat ekran oʻqiguchga ham aytiladi. */}
        <div className="status" role="status" aria-live="polite">
          {status}
        </div>
        <div ref={endRef} />
      </div>

      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}

      <div className="composer">
        <textarea
          rows={3}
          value={input}
          placeholder="Savolingizni yozing…"
          disabled={busy}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              void send(input);
            }
          }}
        />
        <div className="row" style={{ marginTop: 8 }}>
          <button onClick={() => void send(input)} disabled={busy || !input.trim()}>
            {busy ? "Javob tayyorlanmoqda…" : "Yuborish"}
          </button>
          {turns.length > 0 && (
            <button
              className="ghost"
              onClick={() => {
                setTurns([]);
                setError("");
              }}
              disabled={busy}
            >
              Tozalash
            </button>
          )}
          <span className="dim" style={{ fontSize: 12.5 }}>
            Ctrl/⌘ + Enter — yuborish
          </span>
        </div>
      </div>

      <p className="disclaimer">
        ⚠️ AI Lawyer advokat emas. Javoblar maʼlumot uchun beriladi va yuridik
        maslahat hisoblanmaydi. Aniq ish boʻyicha advokatga murojaat qiling.
      </p>
    </>
  );
}

function Sources({ citations }: { citations: Citation[] }) {
  return (
    <details className="sources">
      <summary>Manbalar ({citations.length})</summary>
      {citations.map((c, i) => (
        <div key={i} className="source-item">
          <div className="source-head">
            [{i + 1}] {c.document}
            {c.article ? ` · ${c.article}-modda` : ""}
            {c.heading ? ` · ${c.heading}` : ""}
          </div>
          <div className="source-text">{c.snippet}</div>
          {c.url && (
            <a href={c.url} target="_blank" rel="noopener noreferrer">
              Manba
            </a>
          )}
        </div>
      ))}
    </details>
  );
}
