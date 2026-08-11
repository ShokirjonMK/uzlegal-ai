import { cookies } from "next/headers";
import { ADMIN_COOKIE } from "@/lib/auth/cookie";
import { adminSetup, isAdminCookie } from "@/lib/auth/admin";
import { AdminLogin } from "@/components/admin/AdminLogin";
import { AdminPanel } from "@/components/admin/AdminPanel";

export const runtime = "nodejs";
/** Cookie o'qiladi — sahifa hech qachon oldindan tayyorlanmaydi. */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Admin panel — AI Lawyer",
  robots: { index: false, follow: false },
};

/**
 * Panel SERVER tomonda qorovullanadi: sessiya cookie'si bo'lmasa panel
 * belgilash tili (HTML) umuman yuborilmaydi — faqat kirish formasi.
 * Ya'ni himoya mijoz tomonidagi shartga tayanmaydi.
 */
export default async function AdminPage() {
  const store = await cookies();
  const authorized = isAdminCookie(store.get(ADMIN_COOKIE)?.value);
  const setup = adminSetup();

  if (!authorized) {
    return <AdminLogin setup={setup} />;
  }

  return <AdminPanel />;
}
