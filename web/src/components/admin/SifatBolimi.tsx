"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, RefreshCw, ShieldCheck, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiJson, humanError } from "@/lib/ui/fetch";

/**
 * Sifat — mahsulotning haqiqiy holati, audit jurnalidan.
 *
 * ## Nega bu boʻlim panelning eng muhimi
 *
 * Jurnalda 2 900 dan ortiq konsultatsiya yozuvi bor va u loyihadagi eng
 * boy maʼlumot. Lekin 2026-08-24 gacha uni **hech kim koʻra olmasdi** —
 * har safar alohida skript yozish kerak edi. Natijada quyidagilar
 * nomaʼlum edi:
 *
 *   · daʼvolarning 25% i darvoza tomonidan oʻchiriladi
 *   · `standard` rejimda bu 32%
 *   · haqiqiy foydalanuvchilar soni — NOL
 *
 * Uchalasi ham mahsulot qarorini oʻzgartiradi.
 *
 * ## Dizayn qoidasi: yomon xabar tepada
 *
 * Odatiy panel avval «hammasi yaxshi» degan yashil raqamlarni
 * koʻrsatadi. Bu yerda teskari: birinchi qatorda **haqiqiy
 * foydalanuvchilar** turadi, chunki u nol boʻlsa qolgan hamma raqam
 * oʻz-oʻzini sinash natijasi va shuni bilib turib oʻqilishi kerak.
 */

interface Kechikish {
  p50: number;
  p95: number;
  p99: number;
  max: number;
}

interface Rejim {
  mode: string;
  soni: number;
  claims: number;
  dropped: number;
  flagged: number;
  drop_ulush: number;
  kechikish: Kechikish;
}

interface Kun {
  kun: string;
  soni: number;
  claims: number;
  dropped: number;
  drop_ulush: number;
}

interface Sifat {
  records: number;
  window?: number;
  truncated?: boolean;
  note?: string;
  davr?: { boshi?: string; oxiri?: string };
  foydalanuvchilar?: number;
  darvoza?: {
    claims: number;
    dropped: number;
    flagged: number;
    drop_ulush: number;
    reasons: Record<string, number>;
    reasons_available: boolean;
  };
  javoblar?: {
    jami: number;
    iqtibossiz: number;
    iqtibossiz_ulush: number;
    rad_etilgan: number;
  };
  rejimlar?: Rejim[];
  tendensiya?: Kun[];
  zanjir?: { ok: boolean; records: number; buzilgan?: unknown };
}

interface Javob {
  ulandi: boolean;
  url: string;
  xato?: string;
  maslahat?: string;
  kechikish?: number;
  holat?: Sifat;
}

const son = (n: number) => n.toLocaleString("uz-UZ");
const soniya = (ms: number) => (ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`);

export function SifatBolimi() {
  const [data, setData] = useState<Javob | null>(null);
  const [band, setBand] = useState(true);
  const [xato, setXato] = useState("");

  const yukla = useCallback(async () => {
    setBand(true);
    setXato("");
    try {
      setData(await apiJson<Javob>("/api/admin/sifat"));
    } catch (err) {
      setXato(humanError(err));
    } finally {
      setBand(false);
    }
  }, []);

  useEffect(() => {
    void yukla();
  }, [yukla]);

  if (band && !data) return <div className="konsol-skelet">Jurnal oʻqilmoqda…</div>;

  if (xato) {
    return (
      <div className="konsol-uzilgan" role="alert">
        <h3>Sifat hisoboti olinmadi</h3>
        <p>{xato}</p>
      </div>
    );
  }

  if (!data?.ulandi) {
    return (
      <div className="konsol-uzilgan" role="alert">
        <h3>Yadro javob bermadi</h3>
        <p>{data?.xato ?? "Sabab nomaʼlum."}</p>
        {data?.maslahat && <p className="konsol-maslahat">{data.maslahat}</p>}
        <Button variant="ghost" size="sm" onClick={() => void yukla()}>
          <RefreshCw /> Qayta urinish
        </Button>
      </div>
    );
  }

  const s = data.holat;
  if (!s || !s.records) {
    return <div className="konsol-uzilgan">{s?.note ?? "Audit jurnali boʻsh."}</div>;
  }

  const foydalanuvchilar = s.foydalanuvchilar ?? 0;
  const darvoza = s.darvoza;
  const javoblar = s.javoblar;

  return (
    <div className="konsol">
      <div className="konsol-bosh">
        <p className="konsol-izoh">
          Manba: audit jurnali · {son(s.records)} yozuv
          {s.davr?.boshi && ` · ${s.davr.boshi.slice(0, 10)} — ${s.davr.oxiri?.slice(0, 10)}`}
        </p>
        <Button variant="ghost" size="sm" onClick={() => void yukla()} disabled={band}>
          <RefreshCw /> Yangilash
        </Button>
      </div>

      {s.truncated && (
        <p className="konsol-ogoh">
          Jurnal {son(s.window ?? 0)} yozuvdan uzun — hisobot faqat oxirgi
          {" "}{son(s.window ?? 0)} tasi boʻyicha.
        </p>
      )}

      {/* Eng muhim raqam birinchi. Nol boʻlsa — bu nuqson emas, lekin
          qolgan hamma raqamning maʼnosini oʻzgartiradi. */}
      {foydalanuvchilar === 0 ? (
        <div className="konsol-uzilgan" role="status">
          <h3>
            <AlertTriangle size={16} /> Haqiqiy foydalanuvchi yoʻq
          </h3>
          <p>
            {son(s.records)} ta konsultatsiyaning <strong>hammasi</strong> hisobsiz
            (<code>user_hash: null</code>) — yaʼni sinov soʻrovlari.
          </p>
          <p className="konsol-maslahat">
            Quyidagi barcha raqamlar mahsulotning oʻz-oʻzini sinash natijasi.
            Ular haqiqiy foydalanuvchi xatti-harakatini <strong>aks
            ettirmaydi</strong>. Yopiq sinov (A4) shu boʻshliqni yopadi.
          </p>
        </div>
      ) : (
        <div className="konsol-raqamlar">
          <Raqam nom="Haqiqiy foydalanuvchi" qiymat={son(foydalanuvchilar)} />
        </div>
      )}

      {darvoza && (
        <section className="konsol-blok">
          <h3>Iqtibos darvozasi</h3>
          <div className="konsol-raqamlar">
            <Raqam nom="Daʼvolar" qiymat={son(darvoza.claims)} />
            <Raqam
              nom="Oʻchirilgan"
              qiymat={`${darvoza.drop_ulush}%`}
              izoh={`${son(darvoza.dropped)} ta`}
              ogoh={darvoza.drop_ulush > 15}
            />
            <Raqam nom="Belgilangan" qiymat={son(darvoza.flagged)} izoh="⚠ noaniq" />
          </div>
          <p className="konsol-izoh">
            Yuqori ulush darvoza yomon ishlayotganini emas,{" "}
            <strong>generator manbaga tayanmayotganini</strong> bildiradi.
            Darvoza tasdiqlanmagan daʼvoni oʻchiradi — bu uning vazifasi.
          </p>
        </section>
      )}

      {darvoza && (
        darvoza.reasons_available ? (
          <Taqsimot nom="Oʻchirish sabablari" data={darvoza.reasons} />
        ) : (
          <section className="konsol-blok">
            <h3>Oʻchirish sabablari</h3>
            <p className="konsol-ogoh">
              Maʼlumot yoʻq. Sabablar jurnalga <strong>2026-08-26 dan</strong>{" "}
              yozila boshladi — undan oldingi yozuvlarda faqat son bor edi.
              Yangi konsultatsiyalar bu roʻyxatni toʻldiradi.
            </p>
          </section>
        )
      )}

      {javoblar && (
        <section className="konsol-blok">
          <h3>Javoblar</h3>
          <div className="konsol-raqamlar">
            <Raqam nom="Jami" qiymat={son(javoblar.jami)} />
            <Raqam
              nom="Iqtibossiz"
              qiymat={`${javoblar.iqtibossiz_ulush}%`}
              izoh={`${son(javoblar.iqtibossiz)} ta`}
              ogoh={javoblar.iqtibossiz_ulush > 10}
            />
            <Raqam nom="Rad etilgan" qiymat={son(javoblar.rad_etilgan)} />
          </div>
        </section>
      )}

      {!!s.rejimlar?.length && (
        <section className="konsol-blok">
          <h3>Rejimlar boʻyicha</h3>
          {/* Rejimlar ATAYLAB alohida. Umumiy oʻrtacha muammoning
              qayerdaligini yashiradi: `simple` 10%, `standard` 32%. */}
          <div className="konsol-aylanma">
            <table className="konsol-jadval">
              <thead>
                <tr>
                  <th>Rejim</th>
                  <th className="son">Soʻrov</th>
                  <th className="son">Oʻchirilgan</th>
                  <th className="son">p50</th>
                  <th className="son">p95</th>
                  <th className="son">eng uzun</th>
                </tr>
              </thead>
              <tbody>
                {s.rejimlar.map((m) => (
                  <tr key={m.mode}>
                    <td>{m.mode}</td>
                    <td className="son">{son(m.soni)}</td>
                    <td className={m.drop_ulush > 15 ? "son ogoh" : "son"}>
                      {m.drop_ulush}%
                    </td>
                    <td className="son">{soniya(m.kechikish.p50)}</td>
                    <td className={m.kechikish.p95 > 30_000 ? "son ogoh" : "son"}>
                      {soniya(m.kechikish.p95)}
                    </td>
                    <td className="son">{soniya(m.kechikish.max)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {!!s.tendensiya?.length && <Tendensiya kunlar={s.tendensiya} />}

      {s.zanjir && (
        <section className="konsol-blok">
          <h3>Jurnal butunligi</h3>
          <p className={s.zanjir.ok ? "konsol-yorliq" : "konsol-ogoh"}>
            {s.zanjir.ok ? <ShieldCheck size={15} /> : <ShieldAlert size={15} />}{" "}
            {s.zanjir.ok
              ? `Hash zanjiri butun — ${son(s.zanjir.records)} yozuv tekshirildi.`
              : "Zanjir buzilgan: yozuv oʻzgartirilgan yoki oʻchirilgan."}
          </p>
        </section>
      )}
    </div>
  );
}

function Raqam({
  nom,
  qiymat,
  izoh,
  ogoh,
}: {
  nom: string;
  qiymat: string;
  izoh?: string;
  ogoh?: boolean;
}) {
  return (
    <div className={ogoh ? "konsol-raqam ogoh" : "konsol-raqam"}>
      <span className="nom">{nom}</span>
      <span className="qiymat">{qiymat}</span>
      {izoh && <span className="izoh">{izoh}</span>}
    </div>
  );
}

function Taqsimot({ nom, data }: { nom: string; data: Record<string, number> }) {
  const rows = Object.entries(data);
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

/**
 * Kunlik tendensiya.
 *
 * NEGA KERAK. Bitta kesim («bugun 25%») yaxshilanish yoki yomonlashuvni
 * koʻrsatmaydi. Tuzatish ishlaganini faqat vaqt boʻyicha qator
 * isbotlaydi — aks holda har oʻzgarish «yaxshilandi shekilli» degan
 * taxminga qoladi.
 *
 * Kam soʻrovli kunlar SUSAYTIRILADI: 2 ta soʻrovdagi «53%» 300 ta
 * soʻrovdagi «27%» bilan bir xil koʻrinmasligi kerak.
 */
function Tendensiya({ kunlar }: { kunlar: Kun[] }) {
  const eng = Math.max(...kunlar.map((k) => k.drop_ulush), 1);

  return (
    <section className="konsol-blok">
      <h3>Oʻchirish ulushi — kunlar boʻyicha</h3>
      <ul className="konsol-tendensiya">
        {kunlar.map((k) => (
          <li key={k.kun} className={k.soni < 20 ? "kam" : undefined}>
            <span className="kun">{k.kun.slice(5)}</span>
            <span className="chiziq" aria-hidden>
              <i style={{ height: `${Math.max((k.drop_ulush / eng) * 100, 2)}%` }} />
            </span>
            <span className="qiymat">{k.drop_ulush}%</span>
            <span className="soni">{son(k.soni)}</span>
          </li>
        ))}
      </ul>
      <p className="konsol-izoh">
        Xira ustunlar — 20 tadan kam soʻrov boʻlgan kunlar. Ulardagi foiz
        shovqinli va xulosa uchun yaramaydi.
      </p>
    </section>
  );
}
