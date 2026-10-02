import { adminGuard } from "@/lib/auth/admin";
import { yadrodanOl } from "@/lib/admin/yadroProksi";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Ruxsat etilgan filtrlar — yadro qabul qiladiganlar bilan bir xil. */
const FILTRLAR = new Set(["", "dropped", "no_citations", "slow", "refused"]);

/**
 * GET /api/admin/savollar — maskalangan savollar roʻyxati.
 *
 * NEGA BU BOʻLIM STRATEGIK. A4 (yopiq sinov) ning butun maqsadi —
 * haqiqiy foydalanuvchi savollarini yigʻish. Ular kelganda ularni
 * koʻrish va saralash kerak boʻladi; bu roʻyxat oʻsha asbob.
 *
 * NEGA FILTR OQ ROʻYXAT BILAN. Nomaʼlum qiymat yadroga oʻtkazilsa u
 * jimgina «hammasi» ga aylanardi va foydalanuvchi filtr ishladi deb
 * oʻylardi. Bu yerda notoʻgʻri filtr — aniq xato.
 */
export async function GET(request: Request): Promise<Response> {
  const denied = adminGuard(request);
  if (denied) return denied;

  const url = new URL(request.url);
  const filtr = url.searchParams.get("filtr") ?? "";
  if (!FILTRLAR.has(filtr)) {
    return Response.json({ error: `Nomaʼlum filtr: ${filtr}` }, { status: 400 });
  }

  const limit = Number(url.searchParams.get("limit") ?? 50);
  const offset = Number(url.searchParams.get("offset") ?? 0);

  const q = new URLSearchParams({
    limit: String(Number.isFinite(limit) ? Math.min(Math.max(1, limit), 200) : 50),
    offset: String(Number.isFinite(offset) ? Math.max(0, offset) : 0),
    filtr,
  });
  return yadrodanOl(`/v1/admin/questions?${q}`);
}
