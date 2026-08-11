"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Mail, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiJson, humanError } from "@/lib/ui/fetch";

interface BotBoshlash {
  code: string;
  attemptId: string;
}

/**
 * Uch xil kirish usuli bitta joyda: Telegram widget, Telegram bot kodi va
 * pochta + parol. Uchalasi ham bitta hisobga olib keladi.
 */
export function KabinetKirish({
  bot,
  telegramYoqilgan,
}: {
  bot?: string;
  telegramYoqilgan: boolean;
}) {
  return (
    <>
      <h1>Shaxsiy kabinet</h1>
      <p className="lede">
        Kiring — savollaringiz tarixi bir joyda saqlanadi. Telegram bilan kirsangiz,
        botdagi savollaringiz ham shu yerda koʻrinadi.
      </p>

      <div className="max-w-[460px]">
        <Tabs defaultValue={telegramYoqilgan ? "bot" : "pochta"}>
          <TabsList>
            {telegramYoqilgan && <TabsTrigger value="bot">Telegram bot</TabsTrigger>}
            {telegramYoqilgan && bot && (
              <TabsTrigger value="widget">Telegram tugmasi</TabsTrigger>
            )}
            <TabsTrigger value="pochta">Pochta va parol</TabsTrigger>
          </TabsList>

          {telegramYoqilgan && (
            <TabsContent value="bot">
              <BotOrqali />
            </TabsContent>
          )}
          {telegramYoqilgan && bot && (
            <TabsContent value="widget">
              <WidgetOrqali bot={bot} />
            </TabsContent>
          )}
          <TabsContent value="pochta">
            <PochtaOrqali />
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
}

// ── 1-usul: bot orqali kod ─────────────────────────────────────────────────

function BotOrqali() {
  const router = useRouter();
  const [holat, setHolat] = useState<"boshlanmagan" | "kutilmoqda">("boshlanmagan");
  const [kod, setKod] = useState("");
  const [botNomi, setBotNomi] = useState<string>();
  const [xato, setXato] = useState("");
  const [band, setBand] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Kutish tugaganda yoki sahifadan chiqilganda so'rovni to'xtatamiz.
  useEffect(() => () => {
    if (timerRef.current) clearInterval(timerRef.current);
  }, []);

  const kuzat = useCallback(
    (attemptId: string) => {
      let urinish = 0;
      timerRef.current = setInterval(() => {
        urinish += 1;
        // 10 daqiqa — kodning amal qilish muddati.
        if (urinish > 200) {
          if (timerRef.current) clearInterval(timerRef.current);
          setHolat("boshlanmagan");
          setXato("Kod muddati tugadi. Qaytadan boshlang.");
          return;
        }
        void fetch(`/api/auth/bot?id=${encodeURIComponent(attemptId)}`)
          .then((r) => r.json())
          .then((j: { ok?: boolean }) => {
            if (j.ok) {
              if (timerRef.current) clearInterval(timerRef.current);
              router.refresh();
            }
          })
          .catch(() => {});
      }, 3000);
    },
    [router],
  );

  async function boshla() {
    setBand(true);
    setXato("");
    try {
      const javob = await apiJson<BotBoshlash & { bot?: string }>("/api/auth/bot", {
        method: "POST",
      });
      setKod(javob.code);
      setBotNomi(javob.bot);
      setHolat("kutilmoqda");
      kuzat(javob.attemptId);
    } catch (err) {
      setXato(humanError(err));
    } finally {
      setBand(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Telegram bot orqali</CardTitle>
      </CardHeader>
      <CardContent>
        {holat === "boshlanmagan" ? (
          <>
            <p className="text-[14px] text-muted-foreground mt-0">
              Parol kerak emas. Tugmani bosing — sizga kod beriladi, uni botga
              yuborasiz.
            </p>
            <Button disabled={band} onClick={() => void boshla()}>
              {band ? <Loader2 className="animate-spin" /> : <Send />}
              Kod olish
            </Button>
          </>
        ) : (
          <>
            <p className="text-[14px] text-muted-foreground mt-0">
              Botga quyidagini yuboring:
            </p>
            <div className="log text-center text-[19px] tracking-[0.18em] font-semibold">
              /kirish {kod}
            </div>
            {botNomi && (
              <p className="text-[13px] mt-2 mb-0">
                <a
                  href={`https://t.me/${botNomi}?start=kirish`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Botni ochish → @{botNomi}
                </a>
              </p>
            )}
            <p className="status mt-2" aria-live="polite">
              <Loader2 className="inline size-3.5 mr-1.5 align-[-2px] animate-spin" />
              Tasdiqlash kutilmoqda…
            </p>
          </>
        )}

        {xato && (
          <p className="alert" role="alert">
            {xato}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// ── 2-usul: Telegram Login Widget ──────────────────────────────────────────

function WidgetOrqali({ bot }: { bot: string }) {
  const router = useRouter();
  const box = useRef<HTMLDivElement>(null);
  const [xato, setXato] = useState("");

  useEffect(() => {
    // Telegram widget global funksiyani chaqiradi — shuning uchun `window` ga
    // yoziladi. Komponent yopilganda tozalanadi.
    const w = window as unknown as {
      onTelegramAuth?: (u: Record<string, unknown>) => void;
    };

    w.onTelegramAuth = (data) => {
      void apiJson("/api/auth/telegram", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(data),
      })
        .then(() => router.refresh())
        .catch((err: unknown) => setXato(humanError(err)));
    };

    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", bot);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-radius", "10");
    script.setAttribute("data-onauth", "onTelegramAuth(user)");
    script.setAttribute("data-request-access", "write");
    box.current?.appendChild(script);

    return () => {
      delete w.onTelegramAuth;
    };
  }, [bot, router]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Telegram tugmasi bilan</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-[14px] text-muted-foreground mt-0">
          Bir bosishda kirasiz. Telegram faqat ismingiz va foydalanuvchi nomingizni
          beradi.
        </p>
        <div ref={box} />
        <p className="text-[12.5px] text-faint mt-3 mb-0">
          Tugma koʻrinmasa — bot sozlamalarida sayt manzili koʻrsatilmagan
          (BotFather → <span className="mono">/setdomain</span>).
        </p>
        {xato && (
          <p className="alert" role="alert">
            {xato}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// ── 3-usul: pochta va parol ────────────────────────────────────────────────

function PochtaOrqali() {
  const router = useRouter();
  const [royxat, setRoyxat] = useState(false);
  const [email, setEmail] = useState("");
  const [parol, setParol] = useState("");
  const [ism, setIsm] = useState("");
  const [xato, setXato] = useState("");
  const [band, setBand] = useState(false);

  async function yubor(event: React.FormEvent) {
    event.preventDefault();
    if (band) return;
    setBand(true);
    setXato("");
    try {
      await apiJson("/api/auth/kirish", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, parol, ism: ism || undefined, royxat }),
      });
      router.refresh();
    } catch (err) {
      setXato(humanError(err));
    } finally {
      setBand(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{royxat ? "Roʻyxatdan oʻtish" : "Kirish"}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={yubor} noValidate>
          {royxat && (
            <>
              <Label htmlFor="ism">Ism (ixtiyoriy)</Label>
              <Input
                id="ism"
                value={ism}
                disabled={band}
                autoComplete="given-name"
                onChange={(e) => setIsm(e.target.value)}
              />
            </>
          )}

          <Label htmlFor="email" className="mt-3">
            Elektron pochta
          </Label>
          <Input
            id="email"
            type="email"
            value={email}
            disabled={band}
            autoComplete="email"
            onChange={(e) => setEmail(e.target.value)}
          />

          <Label htmlFor="parol" className="mt-3">
            Parol
          </Label>
          <Input
            id="parol"
            type="password"
            value={parol}
            disabled={band}
            autoComplete={royxat ? "new-password" : "current-password"}
            onChange={(e) => setParol(e.target.value)}
          />
          {royxat && (
            <p className="text-[12.5px] text-faint mt-1 mb-0">
              Kamida 8 belgi, harf va raqam boʻlsin.
            </p>
          )}

          {xato && (
            <p className="alert" role="alert">
              {xato}
            </p>
          )}

          <Button type="submit" className="w-full mt-4" disabled={band || !email || !parol}>
            {band ? <Loader2 className="animate-spin" /> : <Mail />}
            {royxat ? "Roʻyxatdan oʻtish" : "Kirish"}
          </Button>

          <Button
            type="button"
            variant="plain"
            size="sm"
            className="w-full mt-2"
            disabled={band}
            onClick={() => {
              setRoyxat((v) => !v);
              setXato("");
            }}
          >
            {royxat ? "Hisobim bor — kirish" : "Hisobim yoʻq — roʻyxatdan oʻtish"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
