"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiJson, humanError } from "@/lib/ui/fetch";

/**
 * Yadro holati — mahsulotning haqiqiy ko'rsatkichlari.
 *
 * NEGA ALOHIDA BO'LIM. «Umumiy holat» veb ilovaning o'z holatini
 * ko'rsatadi: qaysi model tanlangan, Mongo ulanganmi, nechta so'rov
 * bo'ldi. Bular kerak, lekin ular MAHSULOT qanday holatda ekanini
 * aytmaydi.
 *
 * Bu bo'lim yadrodan o'lchangan raqamlarni oladi: korpusda nima bor,
 * indeks sog'lommi, qamrov darvozasi nimalarni to'sadi, trening
 * to'plami qanday. Har raqam yadroda O'LCHANADI, metafayldan
 * ko'chirilmaydi.
 */

interface Korpus {
  tayyor: boolean;
  sabab?: string;
  hujjat?: number;
  bolak?: number;
  meta_bolak?: number;
  takror_satr?: number;
  kb_versiya?: string;
  turlari?: Record<string, number>;
  birlik?: Record<string, number>;
  sanali_ulush?: number;
  bekor_qilingan?: number;
  noaniq_raqamli_hujjat?: number;
  noaniq_raqam?: number;
  xato?: string;
}

interface ManbaTuri {
  nom: string;
  hujjat: number;
  chegara: number;
  qoplangan: boolean;
}

interface Yadro {
  ulandi: boolean;
  url: string;
  xato?: string;
  maslahat?: string;
  kechikish?: number;
  holat?: {
    korpus?: Korpus;
    qamrov?: { tayyor?: boolean; manba_turlari?: ManbaTuri[]; xato?: string };
    trening?: { toplam?: number; rollar?: Record<string, Record<string, unknown>> };
    sinxronizatsiya?: {
      holat?: string;
      versiya?: string;
      yosh_kun?: number;
      eskirgan?: boolean;
      avtomatik?: boolean;
      oraliq_kun?: number;
      xato?: string;
    };
  };
}

const son = (n: number | undefined): string =>
  n === undefined ? "—" : n.toLocaleString("uz-UZ").replace(/,/g, " ");

export function YadroBolimi() {
  const [data, setData] = useState<Yadro | null>(null);
  const [xato, setXato] = useState("");
  const [band, setBand] = useState(false);

  const yukla = useCallback(async () => {
    setBand(true);
    setXato("");
    try {
      setData(await apiJson<Yadro>("/api/admin/yadro"));
    } catch (err) {
      setXato(humanError(err));
    } finally {
      setBand(false);
    }
  }, []);

  useEffect(() => {
    void yukla();
  }, [yukla]);

  if (xato) {
    return (
      <>
        <div className="alert" role="alert">
          {xato}
        </div>
        <Button variant="ghost" size="sm" onClick={() => void yukla()}>
          <RefreshCw />
          Qayta urinish
        </Button>
      </>
    );
  }

  if (!data) return <div className="konsol-skelet" aria-busy="true" />;

  if (!data.ulandi) {
    return (
      <div className="konsol-uzilgan" role="alert">
        <XCircle className="size-5" aria-hidden />
        <div>
          <h3>Yadro javob bermadi</h3>
          <p>
            <code>{data.url}</code> — {data.xato}
          </p>
          {data.maslahat && (
            <p className="konsol-maslahat">
              {data.maslahat}
            </p>
          )}
        </div>
        <Button variant="ghost" size="sm" onClick={() => void yukla()} disabled={band}>
          <RefreshCw />
        </Button>
      </div>
    );
  }

  const k: Korpus = data.holat?.korpus ?? { tayyor: false };
  const q = data.holat?.qamrov;
  const sync = data.holat?.sinxronizatsiya;
  // Metadagi raqam bilan o'lchangan raqam farq qilsa — bu signal.
  // `docs/23` da aynan shu farq 12 819 bo'lakni yashirgan edi.
  const nomuvofiq = k.tayyor && k.bolak !== undefined && k.bolak !== k.meta_bolak;

  return (
    <div className="konsol">
      <div className="konsol-bosh">
        <span className="konsol-yorliq">
          Yadro · {data.kechikish} ms · {k.kb_versiya || "versiya yoʻq"}
        </span>
        <Button variant="ghost" size="sm" onClick={() => void yukla()} disabled={band}>
          <RefreshCw />
          Yangilash
        </Button>
      </div>

      {k.tayyor ? (
        <>
          <div className="konsol-raqamlar">
            <Raqam nom="Hujjat" qiymat={son(k.hujjat)} />
            <Raqam nom="Boʻlak" qiymat={son(k.bolak)} />
            <Raqam
              nom="Takror satr"
              qiymat={son(k.takror_satr)}
              holat={k.takror_satr ? "xato" : "yaxshi"}
            />
            <Raqam
              nom="Sanali boʻlak"
              qiymat={`${Math.round((k.sanali_ulush ?? 0) * 100)}%`}
              holat={(k.sanali_ulush ?? 0) > 0.95 ? "yaxshi" : "ogoh"}
            />
            <Raqam nom="Bekor qilingan" qiymat={son(k.bekor_qilingan)} />
            <Raqam
              nom="Noaniq modda raqami"
              qiymat={son(k.noaniq_raqam)}
              izoh={`${son(k.noaniq_raqamli_hujjat)} hujjatda`}
              holat="ogoh"
            />
          </div>

          {nomuvofiq && (
            <div className="konsol-ogoh" role="alert">
              <AlertTriangle className="size-4" aria-hidden />
              <span>
                Metadagi raqam ({son(k.meta_bolak)}) oʻlchangan raqamdan ({son(k.bolak)})
                farq qiladi — indeks qayta qurilishi kerak.
              </span>
            </div>
          )}

          <div className="konsol-jadval-juft">
            <Taqsimot nom="Hujjat turlari" data={k.turlari} />
            <Taqsimot nom="Strukturaviy birlik" data={k.birlik} />
          </div>
        </>
      ) : (
        <div className="konsol-ogoh" role="alert">
          <AlertTriangle className="size-4" aria-hidden />
          <span>Indeks tayyor emas: {k.sabab ?? k.xato ?? "sabab noma'lum"}</span>
        </div>
      )}

      {q?.manba_turlari && (
        <section className="konsol-blok">
          <h3>Qamrov darvozasi</h3>
          <p className="konsol-izoh">
            Qoplanmagan manba turi haqidagi savol <strong>rad etiladi</strong> — tizim
            yaqin narsani taxmin qilib bermaydi.
          </p>
          <table className="konsol-jadval">
            <thead>
              <tr>
                <th>Manba turi</th>
                <th className="son">Hujjat</th>
                <th className="son">Chegara</th>
                <th>Holat</th>
              </tr>
            </thead>
            <tbody>
              {q.manba_turlari.map((m) => (
                <tr key={m.nom}>
                  <td>{m.nom}</td>
                  <td className="son">{son(m.hujjat)}</td>
                  <td className="son">{son(m.chegara)}</td>
                  <td>
                    {m.qoplangan ? (
                      <span className="belgi yaxshi">
                        <CheckCircle2 className="size-3.5" aria-hidden /> qoplangan
                      </span>
                    ) : (
                      <span className="belgi ogoh">rad etiladi</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {sync && !sync.xato && (
        <section className="konsol-blok">
          <h3>Sinxronizatsiya</h3>
          <div className="konsol-raqamlar">
            <Raqam nom="Holat" qiymat={sync.holat ?? "—"} />
            <Raqam
              nom="Yoshi"
              qiymat={sync.yosh_kun !== undefined ? `${sync.yosh_kun.toFixed(1)} kun` : "—"}
              holat={sync.eskirgan ? "ogoh" : "yaxshi"}
            />
            <Raqam nom="Oraliq" qiymat={`${sync.oraliq_kun ?? "—"} kun`} />
            <Raqam
              nom="Avtomatik"
              qiymat={sync.avtomatik ? "yoqilgan" : "oʻchiq"}
              holat={sync.avtomatik ? "yaxshi" : "ogoh"}
            />
          </div>
        </section>
      )}
    </div>
  );
}

function Raqam({
  nom,
  qiymat,
  izoh,
  holat,
}: {
  nom: string;
  qiymat: string;
  izoh?: string;
  holat?: "yaxshi" | "ogoh" | "xato";
}) {
  return (
    <div className={`konsol-raqam${holat ? ` ${holat}` : ""}`}>
      <span className="nom">{nom}</span>
      <span className="qiymat">{qiymat}</span>
      {izoh && <span className="izoh">{izoh}</span>}
    </div>
  );
}

function Taqsimot({ nom, data }: { nom: string; data?: Record<string, number> }) {
  const rows = Object.entries(data ?? {});
  if (!rows.length) return null;
  const jami = rows.reduce((a, [, v]) => a + v, 0) || 1;

  return (
    <section className="konsol-blok">
      <h3>{nom}</h3>
      <ul className="konsol-ulush">
        {rows.map(([kalit, qiymat]) => (
          <li key={kalit}>
            <span className="kalit">{kalit}</span>
            <span className="chiziq" aria-hidden>
              <i style={{ width: `${(qiymat / jami) * 100}%` }} />
            </span>
            <span className="qiymat">{son(qiymat)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
