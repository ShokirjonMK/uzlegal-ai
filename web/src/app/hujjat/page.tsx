import { YopiqYuza } from "@/components/YopiqYuza";
import { yopiqSababi } from "@/lib/features";
import { HujjatMijoz } from "./HujjatMijoz";

/**
 * `/hujjat` — server komponenti.
 *
 * NEGA BU QATLAM QOʻSHILDI. Mijoz komponentida yuza ochiqligini
 * tekshirib boʻlmaydi: Next.js da `process.env` brauzerga faqat
 * `NEXT_PUBLIC_` prefiksi bilan tushadi. Qaror serverda qabul
 * qilinishi kerak, aks holda sahifa yopiq boʻlishi kerak boʻlgan
 * joyda ochilib ketardi.
 *
 * Bu — himoyaning UCHINCHI qatlami. Haqiqiy chegara API marshrutida
 * (`api/generate/route.ts`), bu yerda esa foydalanuvchiga sabab
 * tushuntiriladi.
 */
/*
 * Statik emas, DINAMIK.
 *
 * Standart holda Next.js bu sahifani build paytida oldindan chizadi va
 * bayroq qiymati oʻsha payt qotib qoladi. API marshrutlari esa har
 * soʻrovda tekshiradi. Natijada `UZLEGAL_FEATURES` oʻzgarganda sahifa
 * ochiq, marshrut yopiq (yoki teskarisi) boʻlgan yarim holat paydo
 * boʻlardi — bunday nomuvofiqlikni tushunish qiyin.
 */
export const dynamic = "force-dynamic";

export default function Sahifa() {
  const yopiq = yopiqSababi("hujjat");
  if (yopiq) return <YopiqYuza sarlavha="Hujjat tayyorlash" sabab={yopiq} />;
  return <HujjatMijoz />;
}
