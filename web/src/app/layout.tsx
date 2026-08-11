import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { AuroraBackground } from "@/components/AuroraBackground";
import { NavTabs } from "@/components/NavTabs";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Lawyer — Oʻzbekiston qonunchiligi boʻyicha yordamchi",
  description:
    "Huquqiy savol-javob, qonun bazasidan qidiruv, hujjat tahlili va hujjat tayyorlash. Oʻzbek, rus va ingliz tillarida.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="uz">
      <body>
        <AuroraBackground />
        {/* Klaviatura bilan yuruvchilar uchun: Tab bosilganda birinchi
            koʻrinadigan element — navigatsiyani oʻtkazib yuborish havolasi. */}
        <a href="#asosiy" className="skip-link">
          Asosiy qismga oʻtish
        </a>
        <nav className="nav" aria-label="Asosiy navigatsiya">
          <div className="nav-inner">
            <Link href="/" className="brand">
              AI <span>Lawyer</span>
            </Link>
            <NavTabs />
          </div>
        </nav>
        <main className="shell" id="asosiy">
          {children}
        </main>
      </body>
    </html>
  );
}
