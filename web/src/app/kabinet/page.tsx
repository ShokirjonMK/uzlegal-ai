import { cookies } from "next/headers";
import { USER_COOKIE } from "@/lib/auth/cookie";
import { userByToken } from "@/lib/auth/session";
import { toPublicUser } from "@/lib/auth/users";
import { botUsername } from "@/lib/auth/telegram-login";
import { isMongoConfigured } from "@/lib/db/mongo";
import { KabinetKirish } from "@/components/kabinet/KabinetKirish";
import { Kabinet } from "@/components/kabinet/Kabinet";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Shaxsiy kabinet — AI Lawyer",
};

export default async function KabinetPage() {
  if (!isMongoConfigured()) {
    return (
      <>
        <h1>Shaxsiy kabinet</h1>
        <div className="notice">
          Kabinet hozircha ishga tushirilmagan — maʼlumotlar bazasi sozlanmagan.
          Savol-javob, hujjat tahlili va qonun bazasi odatdagidek ishlayveradi.
        </div>
      </>
    );
  }

  const store = await cookies();
  const token = store.get(USER_COOKIE)?.value;
  const user = token ? await userByToken(token) : null;

  if (!user) {
    return (
      <KabinetKirish
        bot={botUsername()}
        telegramYoqilgan={Boolean(process.env.TELEGRAM_BOT_TOKEN)}
      />
    );
  }

  return <Kabinet user={toPublicUser(user)} />;
}
