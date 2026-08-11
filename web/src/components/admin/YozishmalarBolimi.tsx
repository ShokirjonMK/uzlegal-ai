"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input, Select } from "@/components/ui/input";
import { apiJson, humanError } from "@/lib/ui/fetch";

interface Yozuv {
  id: string;
  tur: string;
  yuza: string;
  model: string;
  kirish: string;
  chiqish: string;
  inputTokens?: number;
  outputTokens?: number;
  davomiylik?: number;
  xato?: string;
  telegramId?: number;
  sana: string;
}

interface Javob {
  sahifa: number;
  jami: number;
  sahifaHajmi: number;
  yozuvlar: Yozuv[];
}

const TURLAR = [
  { q: "", n: "Barchasi" },
  { q: "ask", n: "Savol-javob" },
  { q: "analyze", n: "Hujjat tahlili" },
  { q: "review", n: "Tekshiruv" },
  { q: "generate", n: "Hujjat yaratish" },
];

/** Modelga qilingan murojaatlar — to'liq matni bilan. */
export function YozishmalarBolimi() {
  const [sahifa, setSahifa] = useState(1);
  const [tur, setTur] = useState("");
  const [qidiruv, setQidiruv] = useState("");
  const [soragan, setSoragan] = useState("");
  const [data, setData] = useState<Javob | null>(null);
  const [xato, setXato] = useState("");
  const [band, setBand] = useState(false);

  const yukla = useCallback(async () => {
    setBand(true);
    setXato("");
    try {
      const p = new URLSearchParams({ sahifa: String(sahifa) });
      if (tur) p.set("tur", tur);
      if (soragan) p.set("q", soragan);
      setData(await apiJson<Javob>(`/api/admin/yozishmalar?${p}`));
    } catch (err) {
      setXato(humanError(err));
      setData(null);
    } finally {
      setBand(false);
    }
  }, [sahifa, tur, soragan]);

  useEffect(() => {
    void yukla();
  }, [yukla]);

  const oxirgiSahifa = data ? Math.max(1, Math.ceil(data.jami / data.sahifaHajmi)) : 1;

  return (
    <>
      <form
        className="flex gap-2 flex-wrap items-center mb-3"
        onSubmit={(e) => {
          e.preventDefault();
          setSahifa(1);
          setSoragan(qidiruv.trim());
        }}
      >
        <Select
          className="w-auto"
          value={tur}
          aria-label="Murojaat turi"
          onChange={(e) => {
            setTur(e.target.value);
            setSahifa(1);
          }}
        >
          {TURLAR.map((t) => (
            <option key={t.q} value={t.q}>
              {t.n}
            </option>
          ))}
        </Select>
        <Input
          className="w-auto flex-1 min-w-[180px]"
          value={qidiruv}
          placeholder="Matn boʻyicha qidirish…"
          aria-label="Matn boʻyicha qidirish"
          onChange={(e) => setQidiruv(e.target.value)}
        />
        <Button type="submit" variant="ghost" disabled={band}>
          <Search />
          Qidirish
        </Button>
      </form>

      {xato && (
        <div className="alert" role="alert">
          {xato}
        </div>
      )}

      {!data && !xato && (
        <div aria-busy="true" aria-live="polite">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="skeleton mb-3" style={{ height: 96 }} />
          ))}
        </div>
      )}

      {data && (
        <>
          <p className="text-[13px] text-faint mt-0">
            Jami {data.jami} ta yozuv · {sahifa}/{oxirgiSahifa}-sahifa
          </p>

          {data.yozuvlar.length === 0 && (
            <p className="dim">Yozuv topilmadi.</p>
          )}

          {data.yozuvlar.map((y) => (
            <Card key={y.id} className="mb-3">
              <CardContent className="pt-4">
                <div className="flex items-center gap-2 flex-wrap mb-2">
                  <Badge tone={y.xato ? "danger" : "accent"}>{y.tur}</Badge>
                  <Badge>{y.yuza}</Badge>
                  <span className="text-[12.5px] text-faint">
                    {new Date(y.sana).toLocaleString("uz-UZ")}
                  </span>
                  {y.davomiylik != null && (
                    <span className="text-[12.5px] text-faint">
                      {(y.davomiylik / 1000).toFixed(1)} s
                    </span>
                  )}
                  {(y.inputTokens ?? y.outputTokens) != null && (
                    <span className="text-[12.5px] text-faint">
                      {y.inputTokens ?? 0} / {y.outputTokens ?? 0} token
                    </span>
                  )}
                </div>

                {y.xato && <div className="alert mt-0">{y.xato}</div>}

                <details>
                  <summary className="cursor-pointer text-[13px] text-muted-foreground font-medium">
                    Savol va javob matni
                  </summary>
                  <p className="text-[12.5px] text-faint mt-2 mb-1">Kirish:</p>
                  <div className="log">{y.kirish}</div>
                  <p className="text-[12.5px] text-faint mt-2 mb-1">Chiqish:</p>
                  <div className="log">{y.chiqish}</div>
                </details>
              </CardContent>
            </Card>
          ))}

          <div className="actions">
            <Button
              variant="ghost"
              size="sm"
              disabled={band || sahifa <= 1}
              onClick={() => setSahifa((s) => Math.max(1, s - 1))}
            >
              <ChevronLeft />
              Oldingi
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={band || sahifa >= oxirgiSahifa}
              onClick={() => setSahifa((s) => s + 1)}
            >
              Keyingi
              <ChevronRight />
            </Button>
          </div>
        </>
      )}
    </>
  );
}
