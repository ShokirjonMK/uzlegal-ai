/**
 * Mijoz tomonidagi so'rovlar uchun yagona qatlam.
 *
 * Maqsad — foydalanuvchiga «Server xatosi (500)» kabi xom xabar
 * ko'rsatmaslik. Har bir holat uchun nima bo'lgani va nima qilish kerakligi
 * o'zbek tilida aytiladi.
 */

/** Server qaytargan xato shakli — barcha marshrutlarda bir xil. */
interface ErrorBody {
  error?: string;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** HTTP holat kodini tushunarli jumlaga aylantiradi. */
export function statusMessage(status: number): string {
  switch (status) {
    case 401:
      return "Ruxsat yoʻq. Qaytadan kiring.";
    case 403:
      return "Bu amalga ruxsatingiz yoʻq.";
    case 404:
      return "Soʻralgan narsa topilmadi.";
    case 409:
      return "Amal tasdiqlanmadi.";
    case 413:
      return "Fayl yoki matn juda katta.";
    case 429:
      return "Soʻrovlar juda tez-tez. Biroz kutib, qayta urinib koʻring.";
    case 502:
    case 503:
    case 504:
      return "Xizmat vaqtincha ishlamayapti. Bir necha daqiqadan keyin urinib koʻring.";
    default:
      return status >= 500
        ? "Serverda kutilmagan xatolik yuz berdi."
        : `Soʻrov bajarilmadi (${status}).`;
  }
}

/**
 * Har qanday xatoni foydalanuvchiga koʻrsatiladigan matnga aylantiradi.
 * Tarmoq uzilishi alohida ajratiladi — bu eng koʻp uchraydigan holat.
 */
export function humanError(err: unknown): string {
  if (err instanceof ApiError) return err.message;

  if (err instanceof DOMException && err.name === "AbortError") {
    return "Soʻrov bekor qilindi.";
  }

  if (err instanceof TypeError) {
    // `fetch` tarmoqqa chiqa olmaganda aynan shu turdagi xato beradi.
    return typeof navigator !== "undefined" && navigator.onLine === false
      ? "Internetga ulanish yoʻq. Ulanishni tekshiring."
      : "Serverga ulanib boʻlmadi. Ulanishni tekshirib, qayta urinib koʻring.";
  }

  if (err instanceof Error && err.message) return err.message;
  return "Nomaʼlum xatolik yuz berdi.";
}

/** JSON so'rov. Xato bo'lsa `ApiError` tashlaydi. */
export async function apiJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);

  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as ErrorBody | null;
    throw new ApiError(body?.error ?? statusMessage(res.status), res.status);
  }

  return (await res.json()) as T;
}

/** Oqim (SSE) so'rovi uchun javobni tekshiradi. */
export async function apiStream(url: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as ErrorBody | null;
    throw new ApiError(body?.error ?? statusMessage(res.status), res.status);
  }
  return res;
}
