import { adminGuard } from "@/lib/auth/admin";
import { yadrodanOl } from "@/lib/admin/yadroProksi";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * GET /api/admin/sifat — sifat hisoboti (`GET /v1/admin/quality`).
 *
 * Manba: audit jurnali. Bu — panelning eng qimmatli boʻlimi, chunki
 * u yagona joyda mahsulotning HAQIQIY sifatini koʻrsatadi:
 * darvoza nechta daʼvoni oʻchiryapti, kechikish qanday, haqiqiy
 * foydalanuvchi bormi.
 */
export async function GET(request: Request): Promise<Response> {
  const denied = adminGuard(request);
  if (denied) return denied;

  // Jurnal oʻqish 2 903 yozuvda ~1 s. Standart 20 s yetarli zaxira.
  return yadrodanOl("/v1/admin/quality");
}
