"use client";

import { useState } from "react";
import { apiJson, humanError } from "@/lib/ui/fetch";

/**
 * Norma topuvchi.
 *
 * NEGA BU SAHIFA «SAVOL-JAVOB» DAN ALOHIDA. Savol-javob modeldan javob
 * yozishni soʻraydi. Bu sahifa esa **hech narsa yozmaydi** — u faqat
 * tegishli normani va uning aynan matnini koʻrsatadi.
 *
 * Farq oʻlchangan: 2026-08-21 da sakkiz savoldan model ikkitasiga foydali
 * javob berdi, qidiruv esa sakkizalasida ham toʻgʻri moddani topdi.
 * Shuning uchun ishlaydigan qatlam alohida mahsulot sifatida ochiladi.
 *
 * DIZAYN QOIDASI. «Bu javob emas, bu norma» degani KOʻRINISHDA boʻlishi
 * kerak — matn ostidagi mayda izohda emas. Foydalanuvchi izohni
 * oʻqimasligi mumkin, lekin sahifaning shaklini koʻrmasligi mumkin emas.
 */

interface Natija {
  chunk_id: string;
  document: string;
  article?: string | null;
  citation?: string | null;
  unit?: string;
  heading?: string | null;
  text: string;
  score: number;
  url?: string | null;
  valid_from?: string | null;
  valid_to?: string | null;
  status?: string;
}

interface Qamrov {
  kind: string;
  subject: string;
  detail: string;
}

interface Javob {
  results: Natija[];
  coverage?: Qamrov | null;
  total_hits: number;
  latency_ms: number;
  confident: boolean;
}

const NAMUNA = [
  "Nikohga kirish uchun eng kam yosh qancha",
  "Mulkimni qonunsiz egallagan shaxsdan qaytarib olsam boʻladimi",
  "Sinov muddatida mehnat shartnomasi bekor qilinishi mumkinmi",
];

export default function NormaSahifasi() {
  const [savol, setSavol] = useState("");
  const [javob, setJavob] = useState<Javob | null>(null);
  const [band, setBand] = useState(false);
  const [xato, setXato] = useState("");

  async function qidir(matn: string) {
    const q = matn.trim();
    if (!q) return;
    setBand(true);
    setXato("");
    setJavob(null);
    try {
      setJavob(await apiJson<Javob>(`/api/norma?q=${encodeURIComponent(q)}&k=8`));
    } catch (err) {
      setXato(humanError(err));
    } finally {
      setBand(false);
    }
  }

  return (
    <>
      <h1>Norma topuvchi</h1>
      <p className="lede">
        Savolingizni oddiy tilda yozing — tizim tegishli moddani va uning{" "}
        <strong>aynan matnini</strong> koʻrsatadi. Bu sahifa javob yozmaydi va
        talqin qilmaydi: siz qonunning oʻzini oʻqiysiz.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void qidir(savol);
        }}
      >
        <label htmlFor="savol">Savol</label>
        <textarea
          id="savol"
          rows={2}
          value={savol}
          disabled={band}
          placeholder="Masalan: nikohga kirish uchun eng kam yosh qancha"
          onChange={(e) => setSavol(e.target.value)}
        />
        <div className="norma-amallar">
          <button type="submit" disabled={band || !savol.trim()}>
            {band ? "Qidirilmoqda…" : "Normani topish"}
          </button>
          {!javob && !band && (
            <span className="norma-namuna">
              Namuna:{" "}
              {NAMUNA.map((n, i) => (
                <button
                  key={n}
                  type="button"
                  className="ghost norma-namuna-tugma"
                  onClick={() => {
                    setSavol(n);
                    void qidir(n);
                  }}
                >
                  {i + 1}
                </button>
              ))}
            </span>
          )}
        </div>
      </form>

      {xato && (
        <div className="alert" role="alert">
          {xato}
        </div>
      )}

      {javob?.coverage && (
        <section className="norma-qamrov" role="status">
          <h2>Bu savol qamrovdan tashqarida</h2>
          <p>{javob.coverage.detail}</p>
          <p className="norma-qamrov-izoh">
            Yaqin mavzudagi normalarni koʻrsatmadik — ular soʻralgan savolga
            javob <strong>emas</strong>.
          </p>
        </section>
      )}

      {javob && !javob.coverage && javob.results.length === 0 && (
        <div className="alert" role="status">
          Hech narsa topilmadi. Savolni boshqacha yozib koʻring.
        </div>
      )}

      {javob && javob.results.length > 0 && (
        <>
          <p className="norma-hisob">
            {javob.results.length} ta norma · {javob.latency_ms} ms
            {!javob.confident && " · natijalar ishonchsiz, savolni aniqlashtiring"}
          </p>
          <ol className="norma-royxat">
            {javob.results.map((r) => (
              <li key={r.chunk_id} className="norma">
                <div className="norma-bosh">
                  <h2>{r.citation || `${r.document}, ${r.article}-${r.unit || "modda"}`}</h2>
                  {r.status !== "in_force" && (
                    <span className="norma-holat bekor">bekor qilingan</span>
                  )}
                  {r.status === "in_force" && <span className="norma-holat">amalda</span>}
                </div>
                {r.valid_from && (
                  <p className="norma-sana">Kuchga kirgan: {r.valid_from}</p>
                )}
                <p className="norma-matn">{r.text}</p>
                {r.url && (
                  <a href={r.url} target="_blank" rel="noreferrer" className="norma-havola">
                    lex.uz da ochish
                  </a>
                )}
              </li>
            ))}
          </ol>
          <p className="norma-ogoh">
            Yuqoridagi matn qonunning oʻzi. Uni <strong>talqin qilish</strong> —
            yuristning ishi. Tizim sizga qaysi normani oʻqish kerakligini
            koʻrsatadi, uning maʼnosini tushuntirmaydi.
          </p>
        </>
      )}
    </>
  );
}
