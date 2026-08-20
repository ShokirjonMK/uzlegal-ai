import { adminGuard } from "@/lib/auth/admin";
import { config } from "@/lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * GET /api/admin/yadro — yadroning to'liq holati (`GET /v1/status`).
 *
 * NEGA PROKSI. Yadro brauzerdan to'g'ridan-to'g'ri chaqirilmaydi: u
 * boshqa portda turadi, kaliti bo'lishi mumkin va u ommaviy internetga
 * chiqarilmaydi. Panel esa yadro bilan bir tarmoqda — server tomonida
 * so'rash to'g'ri joy.
 *
 * NEGA XATO YUTILMAYDI. Yadro o'chiq bo'lsa panel buni AYTISHI kerak.
 * Bo'sh bo'lim «hammasi yaxshi» degan taassurot qoldiradi va bu eng
 * yomon variant — aynan shu holatda panelga qarash kerak bo'ladi.
 */
export async function GET(request: Request): Promise<Response> {
  const denied = adminGuard(request);
  if (denied) return denied;

  const url = `${config.uzlegalApiUrl}/v1/status`;
  const headers: Record<string, string> = { accept: "application/json" };
  if (config.uzlegalApiKey) headers.authorization = `Bearer ${config.uzlegalApiKey}`;

  const started = Date.now();
  try {
    const res = await fetch(url, {
      headers,
      signal: AbortSignal.timeout(20_000),
      cache: "no-store",
    });
    if (!res.ok) {
      return Response.json(
        { ulandi: false, url, xato: `Yadro ${res.status} qaytardi`, kechikish: Date.now() - started },
        { status: 200 },
      );
    }
    const holat = (await res.json()) as Record<string, unknown>;
    return Response.json({ ulandi: true, url, kechikish: Date.now() - started, holat });
  } catch (err) {
    const xato = err instanceof Error ? err.message : "noma'lum xatolik";
    return Response.json(
      {
        ulandi: false,
        url,
        xato,
        maslahat: "Yadroni ishga tushiring: uzlegal serve",
        kechikish: Date.now() - started,
      },
      { status: 200 },
    );
  }
}
