import { adminGuard } from "@/lib/auth/admin";
import { yadrodanOl } from "@/lib/admin/yadroProksi";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * GET /api/admin/yadro — yadroning to'liq holati (`GET /v1/status`).
 *
 * Proksi mantiqi `lib/admin/yadroProksi.ts` da — u yerda nima uchun
 * xato yutilib 200 qaytishi ham tushuntirilgan.
 */
export async function GET(request: Request): Promise<Response> {
  const denied = adminGuard(request);
  if (denied) return denied;
  return yadrodanOl("/v1/status");
}
