"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { NusxaTugma } from "@/components/ui/nusxa";
import { apiJson, humanError } from "@/lib/ui/fetch";

interface PublicUser {
  id: string;
  telegramId?: number;
  username?: string;
  firstName?: string;
  email?: string;
  createdAt: string;
}

interface Yozuv {
  id: string;
  tur: string;
  yuza: string;
  savol: string;
  javob: string;
  sana: string;
  xato?: string;
}

interface Tarix {
  sahifa: number;
  jami: number;
  sahifaHajmi: number;
  yozuvlar: Yozuv[];
}

const TUR_NOMI: Record<string, string> = {
  ask: "Savol-javob",
  analyze: "Hujjat tahlili",
  review: "Tekshiruv",
  generate: "Hujjat tayyorlash",
  search: "Qidiruv",
};

export function Kabinet({ user }: { user: PublicUser }) {
  const router = useRouter();
  const [sahifa, setSahifa] = useState(1);
  const [tarix, setTarix] = useState<Tarix | null>(null);
  const [xato, setXato] = useState("");
  const [band, setBand] = useState(false);

  const yukla = useCallback(async () => {
    setBand(true);
    setXato("");
    try {
      setTarix(await apiJson<Tarix>(`/api/kabinet/tarix?sahifa=${sahifa}`));
    } catch (err) {
      setXato(humanError(err));
    } finally {
      setBand(false);
    }
  }, [sahifa]);

  useEffect(() => {
    void yukla();
  }, [yukla]);

  async function chiqish() {
    await fetch("/api/auth/men", { method: "DELETE" });
    router.refresh();
  }

  const ism = user.firstName ?? user.username ?? user.email ?? "Foydalanuvchi";
  const oxirgiSahifa = tarix ? Math.max(1, Math.ceil(tarix.jami / tarix.sahifaHajmi)) : 1;

  return (
    <>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1>Shaxsiy kabinet</h1>
          <p className="lede mb-4">Salom, {ism}!</p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => void chiqish()}>
          <LogOut />
          Chiqish
        </Button>
      </div>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle>Hisob</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="kv">
            {user.email && (
              <>
                <dt>Pochta</dt>
                <dd>{user.email}</dd>
              </>
            )}
            {user.username && (
              <>
                <dt>Telegram</dt>
                <dd>@{user.username}</dd>
              </>
            )}
            <dt>Roʻyxatdan oʻtgan</dt>
            <dd>{new Date(user.createdAt).toLocaleDateString("uz-UZ")}</dd>
          </dl>
        </CardContent>
      </Card>

      <h2>Savollar tarixi</h2>

      {xato && (
        <div className="alert" role="alert">
          {xato}
        </div>
      )}

      {!tarix && !xato && (
        <div aria-busy="true" aria-live="polite">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="skeleton mb-3" style={{ height: 88 }} />
          ))}
        </div>
      )}

      {tarix && tarix.yozuvlar.length === 0 && (
        <p className="dim">
          Hozircha tarix boʻsh. Savol bering — bu yerda saqlanadi.
        </p>
      )}

      {tarix?.yozuvlar.map((y) => (
        <Card key={y.id} className="mb-3">
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 flex-wrap mb-2">
              <Badge tone={y.xato ? "danger" : "accent"}>
                {TUR_NOMI[y.tur] ?? y.tur}
              </Badge>
              <span className="text-[12.5px] text-faint">
                {y.yuza === "telegram" ? "Telegram" : "Sayt"} ·{" "}
                {new Date(y.sana).toLocaleString("uz-UZ")}
              </span>
            </div>

            <p className="m-0 font-medium">{qisqart(y.savol, 220)}</p>

            <details className="mt-2">
              <summary className="cursor-pointer text-[13px] text-muted-foreground font-medium">
                Javobni koʻrish
              </summary>
              <div className="log mt-2">{y.javob}</div>
              <div className="actions">
                <NusxaTugma matn={y.javob} />
              </div>
            </details>
          </CardContent>
        </Card>
      ))}

      {tarix && tarix.jami > tarix.sahifaHajmi && (
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
          <span className="text-[13px] text-faint">
            {sahifa}/{oxirgiSahifa}
          </span>
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
      )}
    </>
  );
}

function qisqart(text: string, limit: number): string {
  return text.length <= limit ? text : `${text.slice(0, limit)}…`;
}
