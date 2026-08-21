"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "Savol-javob" },
  { href: "/tahlil", label: "Hujjat tahlili" },
  { href: "/hujjat", label: "Hujjat tayyorlash" },
  { href: "/norma", label: "Norma topuvchi" },
  { href: "/qonunlar", label: "Qonun bazasi" },
  { href: "/kabinet", label: "Kabinet" },
];

/**
 * Navigatsiya tablari. Joriy sahifa `active` sinfi bilan belgilanadi va
 * `aria-current` orqali ekran oʻqiguchga ham aytiladi — ilgari `.tab.active`
 * uslubi bor edi, lekin uni hech kim qoʻymasdi.
 */
export function NavTabs() {
  const pathname = usePathname();

  return (
    <>
      {TABS.map((t) => {
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
