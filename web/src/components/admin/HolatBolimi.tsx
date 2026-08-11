"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/input";
import { apiJson, humanError } from "@/lib/ui/fetch";

interface Holat {
  soat: number;
  tizim: {
    provider: "anthropic" | "ollama";
    model: string;
    ollama: { ok: boolean; error?: string; url: string } | null;
    effort: string;
    lang: string;
    script: string;
    anthropicKey: boolean;
    telegram: boolean;
    apiProtected: boolean;
    embedding: { provider: string; model: string };
    admin: { twoFactor: boolean };
    mongo: { sozlangan: boolean; ok: boolean; error?: string };
  };
  korpus: { chunks?: number; documents?: Array<{ document: string }>; xato?: string };
  statistika: {
    totalEvents?: number;
    uniqueUsers?: number;
    newUsers?: number;
    errors?: number;
    inputTokens?: number;
    outputTokens?: number;
    avgDurationMs?: number;
    users?: number;
    events?: number;
    xato?: string;
  };
  baza: { foydalanuvchi: number; yozishma: number } | null;
}

const DAVRLAR = [
  { qiymat: 24, nom: "24 soat" },
  { qiymat: 24 * 7, nom: "7 kun" },
  { qiymat: 24 * 30, nom: "30 kun" },
  { qiymat: 24 * 365, nom: "1 yil" },
];

export function HolatBolimi() {
  const [soat, setSoat] = useState(24);
  const [data, setData] = useState<Holat | null>(null);
  const [xato, setXato] = useState("");
  const [band, setBand] = useState(false);

  const yukla = useCallback(async (hours: number) => {
    setBand(true);
    setXato("");
    try {
      setData(await apiJson<Holat>(`/api/admin/holat?soat=${hours}`));
    } catch (err) {
      setXato(humanError(err));
    } finally {
      setBand(false);
    }
  }, []);

  useEffect(() => {
    void yukla(soat);
  }, [soat, yukla]);

  if (xato) {
    return (
      <>
        <div className="alert" role="alert">
          {xato}
        </div>
        <Button variant="ghost" size="sm" onClick={() => void yukla(soat)}>
          <RefreshCw />
          Qayta urinish
        </Button>
      </>
    );
  }

  if (!data) return <Skelet />;

  const s = data.statistika;
  const t = data.tizim;

  return (
    <>
      <div className="flex items-center gap-2 flex-wrap mb-3">
        <label htmlFor="davr" className="text-[13px] text-muted-foreground m-0">
          Davr:
        </label>
        <Select
          id="davr"
          className="w-auto"
          value={soat}
          onChange={(e) => setSoat(Number(e.target.value))}
        >
          {DAVRLAR.map((d) => (
            <option key={d.qiymat} value={d.qiymat}>
              {d.nom}
            </option>
          ))}
        </Select>
        <Button variant="ghost" size="sm" onClick={() => void yukla(soat)} disabled={band}>
          <RefreshCw className={band ? "animate-spin" : ""} />
          Yangilash
        </Button>
      </div>

      <div className="admin-grid">
        <Stat n={s.totalEvents} t="Soʻrov" />
        <Stat n={s.uniqueUsers} t="Foydalanuvchi" />
        <Stat n={s.newUsers} t="Yangi" />
        <Stat n={s.errors} t="Xatolik" />
        <Stat
          n={s.avgDurationMs ? `${(s.avgDurationMs / 1000).toFixed(1)} s` : "—"}
          t="Oʻrtacha vaqt"
        />
        <Stat n={data.korpus.chunks} t="Qonun boʻlagi" />
      </div>

      <Card className="mb-3">
        <CardHeader>
          <CardTitle>Tizim holati</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="kv">
            <dt>Provayder</dt>
            <dd>
              <Badge tone={t.provider === "anthropic" ? "accent" : "warn"}>
                {t.provider === "anthropic" ? "Anthropic (bulut)" : "Ollama (lokal)"}
              </Badge>
            </dd>
            <dt>Model</dt>
            <dd className="mono">{t.model}</dd>
            {t.ollama && (
              <>
                <dt>Lokal model holati</dt>
                <dd>
                  <Badge tone={t.ollama.ok ? "ok" : "danger"}>
                    {t.ollama.ok ? "tayyor" : "tayyor emas"}
                  </Badge>
                  <span className="dim text-[12.5px] block mt-1">
                    {t.ollama.url}
                    {t.ollama.error ? ` · ${t.ollama.error}` : ""}
                  </span>
                </dd>
              </>
            )}
            <dt>Chuqurlik</dt>
            <dd className="mono">
              {t.provider === "ollama" ? "— (lokal modelda yoʻq)" : t.effort}
            </dd>
            <dt>Embedding</dt>
            <dd className="mono">
              {t.embedding.provider} · {t.embedding.model}
            </dd>
            <dt>Anthropic kaliti</dt>
            <dd>
              <Bor v={t.anthropicKey} />
            </dd>
            <dt>Telegram bot</dt>
            <dd>
              <Bor v={t.telegram} />
            </dd>
            <dt>API himoyasi</dt>
            <dd>
              <Bor v={t.apiProtected} />
            </dd>
            <dt>Telegram tasdigʻi</dt>
            <dd>
              <Bor v={t.admin.twoFactor} ha="yoqilgan" yoq="oʻchiq" />
            </dd>
            <dt>MongoDB</dt>
            <dd>
              {!t.mongo.sozlangan ? (
                <Badge tone="warn">sozlanmagan</Badge>
              ) : t.mongo.ok ? (
                <Badge tone="ok">ulandi</Badge>
              ) : (
                <Badge tone="danger">ulanmadi</Badge>
              )}
              {t.mongo.error && (
                <span className="dim text-[12.5px] block mt-1">{t.mongo.error}</span>
              )}
            </dd>
          </dl>
        </CardContent>
      </Card>

      {data.baza && (
        <Card>
          <CardHeader>
            <CardTitle>Bazadagi hajm</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="kv">
              <dt>Hisoblar</dt>
              <dd>{data.baza.foydalanuvchi}</dd>
              <dt>Saqlangan yozishma</dt>
              <dd>{data.baza.yozishma}</dd>
            </dl>
          </CardContent>
        </Card>
      )}
    </>
  );
}

function Stat({ n, t }: { n: number | string | undefined; t: string }) {
  return (
    <div className="stat">
      <div className="n">{n ?? "—"}</div>
      <div className="t">{t}</div>
    </div>
  );
}

function Bor({ v, ha = "bor", yoq = "yoʻq" }: { v: boolean; ha?: string; yoq?: string }) {
  return <Badge tone={v ? "ok" : "neutral"}>{v ? ha : yoq}</Badge>;
}

function Skelet() {
  return (
    <div aria-busy="true" aria-live="polite">
      <span className="sr-only">Yuklanmoqda…</span>
      <div className="admin-grid">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="stat">
            <div className="skeleton" style={{ height: 26, width: "60%" }} />
            <div className="skeleton skeleton-line" style={{ width: "80%" }} />
          </div>
        ))}
      </div>
      <div className="skeleton" style={{ height: 180 }} />
    </div>
  );
}
