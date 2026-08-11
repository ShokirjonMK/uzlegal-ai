"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, Send, TestTube2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { apiJson, humanError } from "@/lib/ui/fetch";

interface Qabul {
  qabulQiluvchilar: number;
  adminlar: number;
  botSozlangan: boolean;
}

interface Natija {
  ok: boolean;
  xabar?: string;
  yuborildi?: number;
  yuborilmadi?: number;
}

const MAX = 3500;

/**
 * Ommaviy xabar — ikki bosqichli, ataylab qiyinlashtirilgan.
 *
 * 1) Sinov: xabar faqat adminning o'ziga boradi, ko'rinishini tekshirasiz.
 * 2) Haqiqiy yuborish: qabul qiluvchilar sonini QO'LDA yozib kiritish kerak.
 *    Bir marta bosish bilan hammaga xabar ketib qolishi mumkin emas.
 */
export function XabarBolimi() {
  const [qabul, setQabul] = useState<Qabul | null>(null);
  const [matn, setMatn] = useState("");
  const [tasdiq, setTasdiq] = useState("");
  const [amal, setAmal] = useState<"" | "sinov" | "yuborish">("");
  const [xato, setXato] = useState("");
  const [natija, setNatija] = useState("");
  const [sinovOtdi, setSinovOtdi] = useState(false);

  const yukla = useCallback(async () => {
    try {
      setQabul(await apiJson<Qabul>("/api/admin/xabar"));
    } catch (err) {
      setXato(humanError(err));
    }
  }, []);

  useEffect(() => {
    void yukla();
  }, [yukla]);

  async function yubor(sinov: boolean) {
    setAmal(sinov ? "sinov" : "yuborish");
    setXato("");
    setNatija("");
    try {
      const javob = await apiJson<Natija>("/api/admin/xabar", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(
          sinov ? { matn, sinov: true } : { matn, tasdiq: Number(tasdiq) },
        ),
      });
      setNatija(javob.xabar ?? "Bajarildi.");
      if (sinov) setSinovOtdi(true);
      else {
        setMatn("");
        setTasdiq("");
        setSinovOtdi(false);
        void yukla();
      }
    } catch (err) {
      setXato(humanError(err));
    } finally {
      setAmal("");
    }
  }

  const band = amal !== "";
  const soni = qabul?.qabulQiluvchilar ?? 0;
  const tasdiqTogri = Number(tasdiq) === soni && soni > 0;

  if (qabul && !qabul.botSozlangan) {
    return (
      <div className="notice">
        Telegram bot sozlanmagan. Ommaviy xabar yuborish uchun{" "}
        <span className="mono">TELEGRAM_BOT_TOKEN</span> kerak.
      </div>
    );
  }

  return (
    <>
      <Card className="mb-3">
        <CardHeader>
          <CardTitle>Ommaviy xabar</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-[14px] text-muted-foreground mt-0">
            Xabar botdagi barcha foydalanuvchilarga boradi. Yuborilgan xabarni
            qaytarib boʻlmaydi, shuning uchun avval sinov qiling.
          </p>

          <Label htmlFor="matn">Xabar matni</Label>
          <Textarea
            id="matn"
            rows={7}
            value={matn}
            maxLength={MAX}
            disabled={band}
            placeholder="Assalomu alaykum! Yangilik: …"
            onChange={(e) => {
              setMatn(e.target.value);
              // Matn o'zgardi — avvalgi sinov endi haqiqiy emas.
              setSinovOtdi(false);
            }}
          />
          <p className="text-[12.5px] text-faint mt-1 mb-0">
            {matn.length} / {MAX} belgi · Qabul qiluvchilar: <b>{soni}</b>
          </p>

          <div className="actions">
            <Button
              variant="ghost"
              disabled={band || !matn.trim()}
              onClick={() => void yubor(true)}
            >
              {amal === "sinov" ? <Loader2 className="animate-spin" /> : <TestTube2 />}
              1-qadam: sinov yuborish
            </Button>
            {sinovOtdi && <span className="done">Sinov yuborildi ✓</span>}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2-qadam: haqiqiy yuborish</CardTitle>
        </CardHeader>
        <CardContent>
          <Label htmlFor="tasdiq">
            Tasdiqlash uchun qabul qiluvchilar sonini yozing — {soni}
          </Label>
          <Input
            id="tasdiq"
            inputMode="numeric"
            value={tasdiq}
            disabled={band || !matn.trim()}
            placeholder={String(soni)}
            onChange={(e) => setTasdiq(e.target.value.replace(/\D/g, ""))}
          />

          <div className="actions">
            <Button
              variant="destructive"
              disabled={band || !matn.trim() || !tasdiqTogri}
              onClick={() => void yubor(false)}
            >
              {amal === "yuborish" ? <Loader2 className="animate-spin" /> : <Send />}
              {soni} ta foydalanuvchiga yuborish
            </Button>
          </div>

          {!sinovOtdi && matn.trim() && (
            <p className="text-[13px] text-warn mt-2 mb-0">
              Avval sinov yuborib, xabar qanday koʻrinishini tekshirish tavsiya etiladi.
            </p>
          )}
        </CardContent>
      </Card>

      {xato && (
        <div className="alert" role="alert">
          {xato}
        </div>
      )}
      {natija && (
        <div className="notice" role="status">
          {natija}
        </div>
      )}
    </>
  );
}
