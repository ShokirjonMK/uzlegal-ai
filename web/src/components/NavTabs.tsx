"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Feature } from "@/lib/features";

const TABS: { href: string; label: string; feature: Feature }[] = [
  { href: "/", label: "Savol-javob", feature: "savol" },
  { href: "/norma", label: "Norma topuvchi", feature: "norma" },
  { href: "/tahlil", label: "Hujjat tahlili", feature: "tahlil" },
  { href: "/hujjat", label: "Hujjat tayyorlash", feature: "hujjat" },
  { href: "/qonunlar", label: "Qonun bazasi", feature: "qonunlar" },
  { href: "/kabinet", label: "Kabinet", feature: "kabinet" },
];

/**
 * Navigatsiya tablari. Joriy sahifa `active` sinfi bilan belgilanadi va
 * `aria-current` orqali ekran oʻqiguchga ham aytiladi — ilgari `.tab.active`
 * uslubi bor edi, lekin uni hech kim qoʻymasdi.
 *
 * Yopiq yuzalar roʻyxatga TUSHMAYDI (`lib/features.ts`). Tartib ham
 * oʻzgardi: «Norma topuvchi» yuqoriga koʻtarildi, chunki u hozir
 * mahsulotning ishlaydigan oʻzagi.
 *
 * NEGA `ochiq` PROP, NEGA `ochiqmi()` SHU YERDA CHAQIRILMAYDI. Bu —
 * mijoz komponenti. Next.js da `process.env` mijoz kodiga faqat
 * `NEXT_PUBLIC_` prefiksi bilan tushadi, qolgani `undefined` boʻladi.
 * Ya'ni bu yerda chaqirilsa `UZLEGAL_FEATURES` va Mongo sozlamasi
 * KO'RINMASDI va roʻyxat serverdagidan farq qilardi — sahifa ochiq,
 * tab esa yoʻq. Qaror serverda qabul qilinadi, bu yerga natija keladi.
 */
export function NavTabs({ ochiq }: { ochiq: Feature[] }) {
  const pathname = usePathname();

  return (
    <>
      {TABS.filter((t) => ochiq.includes(t.feature)).map((t) => {
        const active = t.href === "/" ? pathname === "/" : pathname.startsWith(t.href);
        return (
          <Link
            key={t.href}
            href={t.href}
            className={active ? "tab active" : "tab"}
            aria-current={active ? "page" : undefined}
          >
            {t.label}
          </Link>
        );
      })}
    </>
  );
}
