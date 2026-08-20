"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { KeyRound, ShieldCheck, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { apiJson, humanError } from "@/lib/ui/fetch";

interface Setup {
  ready: boolean;
  missing: string[];
  twoFactor: boolean;
}

interface KirishJavobi {
  ok: boolean;
  bosqich: "kod" | "kirdi";
  urinish?: string;
  izoh?: string;
  ogohlantirish?: string;
}

/**
 * Kirish formasi. Ikki bosqich bir komponentda: parol → kod.
 * Panel sozlanmagan bo'lsa forma umuman ko'rsatilmaydi — nima yetishmayotgani
 * aytiladi, chunki parolsiz panel ochilmasligi kerak.
 */
export function AdminLogin({ setup }: { setup: Setup }) {
  const router = useRouter();
  const [bosqich, setBosqich] = useState<"parol" | "kod">("parol");
  const [foydalanuvchi, setFoydalanuvchi] = useState("");
  const [parol, setParol] = useState("");
  const [kod, setKod] = useState("");
  const [urinish, setUrinish] = useState("");
  const [izoh, setIzoh] = useState("");
  const [xato, setXato] = useState("");
  const [band, setBand] = useState(false);

  if (!setup.ready) {
    return (
      <div className="login-box">
        <Card>
          <CardHeader>
            <CardTitle>Admin panel sozlanmagan</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-[14px] text-muted-foreground mt-0">
              Panel himoyasiz ochilmaydi. Ishga tushirish uchun{" "}
              <code className="mono">.env.local</code> ga quyidagilarni qoʻshing:
            </p>
            <ul className="tight text-[14px]">
              {setup.missing.map((m) => (
                <li key={m}>
                  <code className="mono">{m}</code>
                </li>
              ))}
            </ul>
            <p className="text-[13px] text-faint mb-0">
              Sirni tasodifiy va uzun qilib tanlang. Soʻng serverni qayta ishga
              tushiring.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  async function yubor(event: React.FormEvent) {
    event.preventDefault();
    if (band) return;

    setBand(true);
    setXato("");

    try {
      const tana =
        bosqich === "parol"
          ? { foydalanuvchi: foydalanuvchi.trim(), parol }
          : { urinish, kod: kod.trim() };

      const javob = await apiJson<KirishJavobi>("/api/admin/kirish", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(tana),
      });

      if (javob.bosqich === "kod" && javob.urinish) {
        setUrinish(javob.urinish);
        setBosqich("kod");
        setIzoh(javob.izoh ?? "");
        setParol("");
      } else {
        // Sahifani server qayta hisoblaydi va panelni qaytaradi.
        router.refresh();
      }
    } catch (err) {
      setXato(humanError(err));
    } finally {
      setBand(false);
    }
  }

  return (
    <div className="login-box">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {bosqich === "parol" ? (
              <KeyRound className="size-4 text-muted-foreground" />
            ) : (
              <ShieldCheck className="size-4 text-muted-foreground" />
            )}
            {bosqich === "parol" ? "Admin panel" : "Tasdiqlash kodi"}
          </CardTitle>
        </CardHeader>

        <CardContent>
          <form onSubmit={yubor} noValidate>
            {bosqich === "parol" ? (
              <>
                <Label htmlFor="foydalanuvchi">Foydalanuvchi nomi</Label>
                <Input
                  id="foydalanuvchi"
                  type="text"
                  autoComplete="username"
                  autoFocus
                  spellCheck={false}
                  value={foydalanuvchi}
                  disabled={band}
                  onChange={(e) => setFoydalanuvchi(e.target.value)}
                />
                <Label htmlFor="parol" className="mt-3">
                  Parol
                </Label>
                <Input
                  id="parol"
                  type="password"
                  autoComplete="current-password"
                  value={parol}
                  disabled={band}
                  onChange={(e) => setParol(e.target.value)}
                />
                {setup.twoFactor && (
                  <p className="text-[13px] text-faint mt-2 mb-0">
                    Parol toʻgʻri boʻlsa, Telegramga 6 xonali kod yuboriladi.
                  </p>
                )}
              </>
            ) : (
              <>
                <Label htmlFor="kod">Telegramga yuborilgan kod</Label>
                <Input
                  id="kod"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  autoFocus
                  maxLength={6}
                  placeholder="123456"
                  value={kod}
                  disabled={band}
                  onChange={(e) => setKod(e.target.value.replace(/\D/g, ""))}
                />
                {izoh && (
                  <p className="text-[13px] text-faint mt-2 mb-0">{izoh}</p>
                )}
              </>
            )}

            {xato && (
              <p className="alert" role="alert">
                {xato}
              </p>
            )}

            <Button
              type="submit"
              className="w-full mt-4"
              disabled={
                band ||
                (bosqich === "parol" ? !parol || !foydalanuvchi.trim() : kod.length < 6)
              }
            >
              {band && <Loader2 className="animate-spin" />}
              {band ? "Tekshirilmoqda…" : bosqich === "parol" ? "Kirish" : "Tasdiqlash"}
            </Button>

            {bosqich === "kod" && (
              <Button
                type="button"
                variant="plain"
                size="sm"
                className="w-full mt-2"
                disabled={band}
                onClick={() => {
                  setBosqich("parol");
                  setKod("");
                  setXato("");
                }}
              >
                Orqaga
              </Button>
            )}
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
