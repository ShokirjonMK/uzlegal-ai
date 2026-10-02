"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiJson, humanError } from "@/lib/ui/fetch";

/**
 * Savollar — haqiqiy soʻrovlar roʻyxati.
 *
 * ## Nega bu boʻlim strategik
 *
 * Yopiq sinovning (A4) butun maqsadi — **haqiqiy foydalanuvchi
 * savollarini** yigʻish. Bugungacha tizimga berilgan 2 900 savolning
 * hammasi mening oʻz savollarim, yaʼni mahsulot mening tasavvurimga
 * qarshi sozlangan. Sinov boshlanganda haqiqiy savollar shu yerga
 * tushadi va ularni koʻrish, saralash kerak boʻladi.
 *
 * ## Dizayn qoidasi: nosozlik birinchi
 *
 * Standart filtr — «darvoza oʻchirgan». Sabab: muvaffaqiyatli
 * javoblarni varaqlashdan foyda yoʻq. Qiymat aynan buzilgan
 * holatlarda — ularda nima notoʻgʻri ketgani koʻrinadi.
 *
 * ## Maxfiylik
 *
 * Savollar jurnalda MASKALANGAN holda yotadi (`audit._mask` →
 * `ingest/redact`): pasport, JSHSHIR, telefon, pochta, manzil va
 * ismlar olib tashlangan. Javob matni esa umuman saqlanmaydi —
 * faqat uzunligi va hashi. Shuning uchun bu roʻyxatni koʻrsatish
 * maxfiylik siyosatiga zid emas.
 */

interface Gate {
  claims?: number;
  kept?: number;
  dropped?: number;
  flagged?: number;
  refused?: boolean;
  reasons?: Record<string, number>;
}

interface Yozuv {
  trace_id: string;
  timestamp: string;
  savol: string;
  mode: string;
  kb_version: string;
  latency_ms: number | null;
  confidence: number | null;
  answer_chars: number | null;
  citations: string[];
  gate: Gate;
  retrieval: { chunks?: number; citations?: number };
  user_hash: string | null;
}

interface Royxat {
  jami: number;
  offset: number;
  limit: number;
  filtr: string;
  yozuvlar: Yozuv[];
}

interface Javob {
  ulandi: boolean;
  xato?: string;
  maslahat?: string;
  holat?: Royxat;
}

const FILTRLAR: { qiymat: string; nom: string; izoh: string }[] = [
  { qiymat: "dropped", nom: "Darvoza oʻchirgan", izoh: "Daʼvo manbaga bogʻlanmagan" },
  { qiymat: "no_citations", nom: "Iqtibossiz", izoh: "Javobda bironta manba yoʻq" },
  { qiymat: "slow", nom: "Sekin", izoh: "30 soniyadan uzoq" },
  { qiymat: "refused", nom: "Rad etilgan", izoh: "Javob shakllantirilmagan" },
  { qiymat: "", nom: "Hammasi", izoh: "Filtrsiz" },
];

const SAHIFA = 25;
const son = (n: number) => n.toLocaleString("uz-UZ");
const soniya = (ms: number | null) =>
  ms == null ? "—" : ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`;

export function SavollarBolimi() {
  const [filtr, setFiltr] = useState("dropped");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<Javob | null>(null);
  const [band, setBand] = useState(true);
  const [xato, setXato] = useState("");
  const [ochiq, setOchiq] = useState<string | null>(null);

  const yukla = useCallback(async () => {
    setBand(true);
    setXato("");
    try {
      const q = new URLSearchParams({
        filtr,
        limit: String(SAHIFA),
        offset: String(offset),
      });
      setData(await apiJson<Javob>(`/api/admin/savollar?${q}`));
    } catch (err) {
      setXato(humanError(err));
    } finally {
      setBand(false);
    }
  }, [filtr, offset]);

  useEffect(() => {
    void yukla();
  }, [yukla]);

  function filtrniOzgartir(yangi: string) {
    setFiltr(yangi);
    setOffset(0); // aks holda yangi filtrda boʻsh sahifada qolib ketardi
    setOchiq(null);
  }

  const r = data?.holat;

  return (
    <div className="konsol">
      <div className="konsol-bosh">
        <p className="konsol-izoh">
          Savollar maskalangan — shaxsiy maʼlumot olib tashlangan. Javob
          matni saqlanmaydi.
        </p>
        <Button variant="ghost" size="sm" onClick={() => void yukla()} disabled={band}>
          <RefreshCw /> Yangilash
        </Button>
      </div>

      <div className="konsol-filtrlar" role="group" aria-label="Filtrlar">
        {FILTRLAR.map((f) => (
          <button
            key={f.qiymat || "hammasi"}
            type="button"
            className={filtr === f.qiymat ? "filtr faol" : "filtr"}
            onClick={() => filtrniOzgartir(f.qiymat)}
            title={f.izoh}
          >
            {f.nom}
          </button>
        ))}
      </div>

      {xato && (
        <div className="konsol-uzilgan" role="alert">
          <p>{xato}</p>
        </div>
      )}

      {data && !data.ulandi && (
        <div className="konsol-uzilgan" role="alert">
          <h3>Yadro javob bermadi</h3>
          <p>{data.xato}</p>
          {data.maslahat && <p className="konsol-maslahat">{data.maslahat}</p>}
        </div>
      )}

      {band && !r && <div className="konsol-skelet">Yuklanmoqda…</div>}

      {r && (
        <>
          <p className="konsol-izoh">
            {son(r.jami)} ta yozuv
            {r.jami > 0 && ` · ${offset + 1}–${Math.min(offset + SAHIFA, r.jami)}`}
          </p>

          {r.yozuvlar.length === 0 ? (
            <p className="konsol-yorliq">
              Bu filtr boʻyicha yozuv yoʻq — bu yaxshi xabar.
            </p>
          ) : (
            <ul className="konsol-savollar">
              {r.yozuvlar.map((y) => (
                <SavolQator
                  key={y.trace_id}
                  y={y}
                  ochiq={ochiq === y.trace_id}
                  toggle={() => setOchiq(ochiq === y.trace_id ? null : y.trace_id)}
                />
              ))}
            </ul>
          )}

          <div className="konsol-sahifa">
            <Button
              variant="ghost"
              size="sm"
              disabled={offset === 0 || band}
              onClick={() => setOffset(Math.max(0, offset - SAHIFA))}
            >
              <ChevronLeft /> Oldingi
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={offset + SAHIFA >= r.jami || band}
              onClick={() => setOffset(offset + SAHIFA)}
            >
              Keyingi <ChevronRight />
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

function SavolQator({
  y,
  ochiq,
  toggle,
}: {
  y: Yozuv;
  ochiq: boolean;
  toggle: () => void;
}) {
  const dropped = y.gate.dropped ?? 0;
  const claims = y.gate.claims ?? 0;

  return (
    <li className="savol">
      <button type="button" className="savol-bosh" onClick={toggle} aria-expanded={ochiq}>
        <span className="savol-matn">{y.savol || "(savol yozilmagan)"}</span>
        <span className="savol-belgilar">
          {dropped > 0 && (
            <span className="belgi ogoh" title="Darvoza oʻchirgan daʼvolar">
              {dropped}/{claims}
            </span>
          )}
          {!y.retrieval.citations && (
            <span className="belgi ogoh" title="Iqtibossiz">
              iqtibossiz
            </span>
          )}
          <span className="belgi">{y.mode}</span>
          <span className="belgi">{soniya(y.latency_ms)}</span>
        </span>
      </button>

      {ochiq && (
        <div className="savol-tafsilot">
          <dl>
            <dt>Vaqt</dt>
            <dd>{y.timestamp.replace("T", " ").slice(0, 19)}</dd>

            <dt>Baza versiyasi</dt>
            <dd>{y.kb_version || "—"}</dd>

            <dt>Ishonch</dt>
            <dd>{y.confidence == null ? "—" : y.confidence.toFixed(2)}</dd>

            <dt>Javob uzunligi</dt>
            <dd>{y.answer_chars == null ? "—" : `${son(y.answer_chars)} belgi`}</dd>

            <dt>Topilgan boʻlaklar</dt>
            <dd>{y.retrieval.chunks ?? 0}</dd>

            <dt>Iqtiboslar</dt>
            <dd>{y.citations.length ? y.citations.join(", ") : "yoʻq"}</dd>

            {!!Object.keys(y.gate.reasons ?? {}).length && (
              <>
                <dt>Oʻchirish sabablari</dt>
                <dd>
                  {Object.entries(y.gate.reasons ?? {})
                    .map(([k, v]) => `${k} (${v})`)
                    .join("; ")}
                </dd>
              </>
            )}

            <dt>Izlash raqami</dt>
            <dd>
              <code>{y.trace_id}</code>
            </dd>
          </dl>
          <p className="konsol-izoh">
            Toʻliq iz: <code>GET /v1/traces/{y.trace_id}</code>
          </p>
        </div>
      )}
    </li>
  );
}
