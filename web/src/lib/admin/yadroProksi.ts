import { config } from "@/lib/config";

/**
 * Yadro endpointiga proksi — barcha admin marshrutlari uchun bitta joy.
 *
 * NEGA UMUMIY FUNKSIYA. `api/admin/yadro/route.ts` da bu mantiq
 * qoʻlda yozilgan edi. Sifat va savollar boʻlimlari qoʻshilganda uni
 * ikki marta koʻchirish kerak boʻlardi — va uchta nusxa uchta xil
 * xato boshqaruviga aylanardi.
 *
 * NEGA XATO YUTILMAYDI VA 200 QAYTADI. Yadro oʻchiq boʻlsa panel buni
 * **aytishi** kerak. Agar bu marshrut 502 qaytarsa, mijoz kodi uni
 * oddiy tarmoq xatosi deb koʻrsatardi («soʻrov bajarilmadi») va
 * foydalanuvchi nima qilishni bilmasdi. `{ulandi: false, maslahat}`
 * esa aniq yoʻl koʻrsatadi.
 *
 * Boʻsh boʻlim eng yomon variant boʻlardi: u «hammasi yaxshi» degan
 * taassurot qoldiradi, holbuki aynan shu holatda panelga qarash kerak.
 */
export interface YadroJavobi<T> {
  ulandi: boolean;
  url: string;
  kechikish: number;
  xato?: string;
  maslahat?: string;
  holat?: T;
}

export async function yadrodanOl<T>(
  yol: string,
  timeoutMs = 20_000,
): Promise<Response> {
  const url = `${config.uzlegalApiUrl}${yol}`;
  const headers: Record<string, string> = { accept: "application/json" };
  if (config.uzlegalApiKey) headers.authorization = `Bearer ${config.uzlegalApiKey}`;

  const started = Date.now();
  try {
    const res = await fetch(url, {
      headers,
      signal: AbortSignal.timeout(timeoutMs),
      cache: "no-store",
    });
    if (!res.ok) {
      return Response.json({
        ulandi: false,
        url,
        xato: `Yadro ${res.status} qaytardi`,
        kechikish: Date.now() - started,
      });
    }
    return Response.json({
      ulandi: true,
      url,
      kechikish: Date.now() - started,
      holat: (await res.json()) as unknown,
    });
  } catch (err) {
    return Response.json({
      ulandi: false,
      url,
      xato: err instanceof Error ? err.message : "nomaʼlum xatolik",
      maslahat: "Yadroni ishga tushiring: uzlegal serve",
      kechikish: Date.now() - started,
    });
  }
}
