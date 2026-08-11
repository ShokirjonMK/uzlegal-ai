"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Copy, Download } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Nusxa olish.
 *
 * `navigator.clipboard` faqat xavfsiz kontekstda (HTTPS yoki localhost)
 * ishlaydi. Ishlab chiqarishda sayt HTTP orqali ochilsa tugma jim o'lib
 * qolmasligi uchun eski `execCommand` zaxira yo'li qoldirilgan.
 */
async function nusxaOl(matn: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(matn);
      return true;
    }
  } catch {
    // Zaxira yo'liga o'tamiz.
  }

  try {
    const el = document.createElement("textarea");
    el.value = matn;
    el.setAttribute("readonly", "");
    el.style.position = "fixed";
    el.style.opacity = "0";
    document.body.appendChild(el);
    el.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(el);
    return ok;
  } catch {
    return false;
  }
}

export function NusxaTugma({
  matn,
  nom = "Nusxa olish",
}: {
  matn: string;
  nom?: string;
}) {
  const [holat, setHolat] = useState<"tinch" | "boldi" | "xato">("tinch");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  async function bos() {
    const ok = await nusxaOl(matn);
    setHolat(ok ? "boldi" : "xato");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setHolat("tinch"), 2200);
  }

  return (
    <>
      <Button variant="ghost" size="sm" onClick={() => void bos()} disabled={!matn}>
        {holat === "boldi" ? <Check /> : <Copy />}
        {nom}
      </Button>
      {/* Natija ovoz bilan ham bildiriladi — faqat rang bilan emas. */}
      <span role="status" aria-live="polite" className={holat === "boldi" ? "done" : "sr-only"}>
        {holat === "boldi"
          ? "Nusxa olindi"
          : holat === "xato"
            ? "Nusxa olinmadi — matnni qoʻlda belgilang."
            : ""}
      </span>
    </>
  );
}

/** Matnni fayl sifatida yuklab olish. Brauzerdan chiqmaydi — server kerak emas. */
export function YuklabOlishTugma({
  matn,
  fayl,
  nom = "Yuklab olish",
  turi = "text/markdown;charset=utf-8",
}: {
  matn: string;
  fayl: string;
  nom?: string;
  turi?: string;
}) {
  function bos() {
    const blob = new Blob([matn], { type: turi });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fayl;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    // Darhol bo'shatilsa Safari yuklab ulgurmaydi.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <Button variant="ghost" size="sm" onClick={bos} disabled={!matn}>
      <Download />
      {nom}
    </Button>
  );
}
