"use client";

import { useState } from "react";
import { readSse } from "@/lib/util/sse";
import { apiStream, humanError } from "@/lib/ui/fetch";
import { NusxaTugma, YuklabOlishTugma } from "@/components/ui/nusxa";
import type { DocTemplateId } from "@/lib/types";

const TEMPLATES: Array<{ id: DocTemplateId; name: string; hint: string }> = [
  {
    id: "mehnat-shartnomasi",
    name: "Mehnat shartnomasi",
    hint: "Lavozim, ish haqi, ish vaqti, sinov muddati, tomonlar",
  },
  {
    id: "ijara-shartnomasi",
    name: "Ijara shartnomasi",
    hint: "Obyekt manzili, ijara haqi, muddat, kommunal toʻlovlar",
  },
  {
    id: "oldi-sotdi-shartnomasi",
    name: "Oldi-sotdi shartnomasi",
    hint: "Mol nomi, narxi, toʻlov va topshirish tartibi",
  },
  {
    id: "xizmat-korsatish-shartnomasi",
    name: "Xizmat koʻrsatish shartnomasi",
    hint: "Xizmat turi, hajmi, narxi, muddatlari",
  },
  {
    id: "pudrat-shartnomasi",
    name: "Pudrat shartnomasi",
    hint: "Ish turi, hajmi, smeta, bajarilish muddati",
  },
  {
    id: "davo-arizasi",
    name: "Daʼvo arizasi",
    hint: "Sud nomi, tomonlar, daʼvo predmeti, summa, dalillar",
  },
  { id: "ishonchnoma", name: "Ishonchnoma", hint: "Kim, kimga, qanday vakolat, muddat" },
  { id: "tilxat", name: "Tilxat", hint: "Kim kimdan, qancha, qachon qaytaradi" },
  { id: "ariza", name: "Ariza", hint: "Kimga, nima soʻralmoqda, asos" },
  {
    id: "pretenziya",
    name: "Pretenziya",
    hint: "Kimga, qaysi shartnoma buzilgan, talab, muddat",
  },
  { id: "erkin", name: "Erkin shakl", hint: "Qanday hujjat kerakligini tasvirlang" },
];

export default function GeneratePage() {
  const [template, setTemplate] = useState<DocTemplateId>("ijara-shartnomasi");
  const [details, setDetails] = useState("");
  const [markdown, setMarkdown] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const active = TEMPLATES.find((t) => t.id === template);
  const placeholders = [...new Set([...markdown.matchAll(/\{\{\s*([^}]+?)\s*\}\}/g)].map((m) => m[1]!.trim()))];

  async function run() {
    if (busy || !details.trim()) return;

    setBusy(true);
    setError("");
    setMarkdown("");
    setStatus("Boshlanmoqda…");

    try {
      const res = await apiStream("/api/generate?format=sse", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ template, details }),
      });

      for await (const event of readSse(res)) {
        if (event.type === "status") setStatus(event.message);
        else if (event.type === "delta") {
          setStatus("");
          setMarkdown((m) => m + event.text);
        } else if (event.type === "error") setError(event.message);
        else if (event.type === "done") setStatus("");
      }
    } catch (err) {
      setError(humanError(err));
    } finally {
      setBusy(false);
      setStatus("");
    }
  }

  async function downloadDocx() {
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/generate?format=docx", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ template, details }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { error?: string } | null;
        throw new Error(body?.error ?? "Faylni tayyorlab boʻlmadi.");
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${active?.name ?? "hujjat"}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(humanError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Hujjat tayyorlash</h1>
      <p className="lede">
        Hujjat turini tanlang va tafsilotlarni yozing. Berilmagan maʼlumotlar
        oʻrniga <span className="mono">{"{{...}}"}</span> shaklida toʻldirish
        joylari qoldiriladi — hech narsa oʻylab topilmaydi.
      </p>

      <label htmlFor="tpl">Hujjat turi</label>
      <select
        id="tpl"
        value={template}
        disabled={busy}
        onChange={(e) => setTemplate(e.target.value as DocTemplateId)}
      >
        {TEMPLATES.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
          </option>
        ))}
      </select>

      <label htmlFor="details">
        Tafsilotlar {active && <span className="dim">— {active.hint}</span>}
      </label>
      <textarea
        id="details"
        rows={6}
        value={details}
        disabled={busy}
        placeholder="Masalan: Toshkent shahri, Yunusobod tumani, 2 xonali kvartira. Ijara haqi oyiga 5 000 000 soʻm. Muddat 1 yil. Kommunal toʻlovlar ijarachi zimmasida."
        onChange={(e) => setDetails(e.target.value)}
      />

      <div className="row" style={{ marginTop: 12 }}>
        <button onClick={() => void run()} disabled={busy || !details.trim()}>
          {busy ? "Tayyorlanmoqda…" : "Tayyorlash"}
        </button>
        {markdown && !busy && (
          <>
            <button className="ghost" onClick={() => void downloadDocx()}>
              .docx yuklab olish
            </button>
            <NusxaTugma matn={markdown} />
            <YuklabOlishTugma
              matn={markdown}
              fayl={`${active?.name ?? "hujjat"}.md`}
              nom=".md yuklab olish"
            />
          </>
        )}
      </div>

      <p className="status" role="status" aria-live="polite">
        {status}
      </p>
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}

      {busy && !markdown && (
        <div aria-busy="true" style={{ marginTop: 16 }}>
          {Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="skeleton skeleton-line" style={{ width: `${95 - i * 9}%` }} />
          ))}
        </div>
      )}

      {placeholders.length > 0 && !busy && (
        <div className="notice">
          <b>Toʻldirilishi kerak:</b> {placeholders.join(", ")}
        </div>
      )}

      {markdown && (
        <>
          <h2>Hujjat loyihasi</h2>
          <div className="doc">{markdown}</div>
        </>
      )}

      <p className="disclaimer">
        ⚠️ Bu — hujjat loyihasi, tayyor yuridik hujjat emas. Imzolashdan oldin
        yurist yoki advokatga koʻrsating.
      </p>
    </>
  );
}
