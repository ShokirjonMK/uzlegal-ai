import Link from "next/link";
import { config } from "@/lib/config";

export const metadata = {
  title: "Maxfiylik siyosati — UzLegal-AI",
  description: "Qanday maʼlumot yigʻiladi, nima uchun va qancha saqlanadi.",
};

/**
 * Maxfiylik siyosati.
 *
 * YOZISH QOIDASI: bu matn kodning HAQIQIY xatti-harakatidan olingan,
 * namunadan koʻchirilmagan. Har band tekshirildi:
 *
 * | Daʼvo | Manba |
 * |---|---|
 * | Savol maskalanadi | `audit.py:_mask` → `ingest/redact.py` |
 * | Maskalanmasa yozilmaydi | `audit.py` — `[MASKALANMADI]` qaytadi |
 * | Nima maskalanadi | `redact.py` naqshlari roʻyxati |
 * | Javob matni saqlanmaydi | `record_consult` faqat `answer_hash` yozadi |
 * | Zanjir buzilmaydi | `audit.py` — har yozuvda oldingi hash |
 *
 * Agar kod oʻzgarsa — bu sahifa ham oʻzgarishi SHART. Maxfiylik siyosati
 * kodga mos kelmasa, u hujjat emas, yolgʻon.
 */
export default function MaxfiylikSahifasi() {
  return (
    <>
      <h1>Maxfiylik siyosati</h1>
      <p className="lede">
        Oxirgi tahrir: 2026-yil 25-avgust. Quyida — qanday maʼlumot
        yigʻilishi, nima uchun va qancha saqlanishi.
      </p>

      <section className="hujjat">
        <h2>1. Qisqacha</h2>
        <p>
          Savolingiz <strong>shaxsiy maʼlumot maskalanganidan keyin</strong>{" "}
          xizmat sifatini oʻlchash uchun saqlanadi. Javob matni saqlanmaydi —
          faqat uning nazorat yigʻindisi. Hisob ochmasangiz, yozuvlar hech
          qanday shaxsga bogʻlanmaydi.
        </p>

        <h2>2. Nima saqlanadi</h2>
        <p>Har bir soʻrov uchun quyidagilar yoziladi:</p>
        <ul>
          <li><strong>Maskalangan savol</strong> — pastda tushuntirilgan</li>
          <li>Vaqt, soʻrov identifikatori va bilim bazasi versiyasi</li>
          <li>Qaysi normalar topilgani va iqtibos nazorati natijasi</li>
          <li>Javob uzunligi va uning <strong>hash</strong> qiymati</li>
          <li>Bajarilish vaqti</li>
        </ul>
        <p>
          <strong>Javobning matni saqlanmaydi.</strong> Hash — javob
          oʻzgarmaganini tekshirish uchun; undan matnni tiklab boʻlmaydi.
        </p>

        <h2>3. Maskalash qanday ishlaydi</h2>
        <p>
          Savol saqlanishdan <strong>oldin</strong> avtomatik tozalanadi.
          Quyidagilar aniqlanadi va olib tashlanadi:
        </p>
        <ul>
          <li>Pasport raqami, JSHSHIR, STIR</li>
          <li>Bank hisobi va karta raqamlari</li>
          <li>Telefon raqami va elektron pochta</li>
          <li>Manzil (koʻcha, uy, xonadon)</li>
          <li>Shaxs ismlari va tashkilot nomlari</li>
        </ul>
        <p>
          Maskalash biron sababga koʻra bajarilmasa,{" "}
          <strong>savol umuman yozilmaydi</strong> — uning oʻrniga belgi
          qoʻyiladi. Yaʼni maskalanmagan savol jurnalga tushmaydi.
        </p>
        <p className="hujjat-izoh">
          Maskalash — avtomatik naqsh tanish. U koʻp narsani tutadi, lekin{" "}
          <strong>mukammal emas</strong>. Shuning uchun eng ishonchli himoya
          oddiy: savolda haqiqiy ism, raqam va manzil yozmang — ular javob
          uchun kerak emas.
        </p>

        <h2>4. Hisob ochsangiz</h2>
        <p>
          Hisob ochish ixtiyoriy. Ochsangiz qoʻshimcha ravishda saqlanadi:
        </p>
        <ul>
          <li>Kirish maʼlumotlari (Telegram identifikatori yoki pochta)</li>
          <li>Yozishmalar tarixi — uni oʻzingiz koʻrishingiz uchun</li>
          <li>Foydalanish hisobi (chegaralarni qoʻllash uchun)</li>
        </ul>
        <p>
          Hisobsiz foydalansangiz jurnaldagi yozuvlar sizga bogʻlanmaydi.
        </p>

        <h2>5. Kim koʻradi</h2>
        <p>
          Maʼlumot <strong>uchinchi shaxslarga berilmaydi va sotilmaydi</strong>.
          Reklama tarmoqlariga uzatilmaydi.
        </p>
        {/*
          Bu band SOZLAMADAN oʻqiladi, qoʻlda yozilmaydi.

          Sabab: «model bizning serverimizda» degan daʼvo faqat
          `uzlegal`/`ollama` provayderida rost. Kod `anthropic` ni ham
          qoʻllab-quvvatlaydi va u tanlansa savol tashqi xizmatga
          ketadi. Qoʻlda yozilgan matn oʻsha kuni jimgina yolgʻonga
          aylanardi — va buni hech kim sezmasdi.
        */}
        {config.provider === "anthropic" ? (
          <p>
            Javob yozish uchun <strong>tashqi til modeli xizmati</strong>{" "}
            ishlatiladi. Yaʼni savolingiz qayta ishlash uchun oʻsha xizmatga
            uzatiladi. Bu sozlama joriy holatda yoqilgan.
          </p>
        ) : (
          <p>
            Xizmat oʻz serverimizda ishlaydi va til modeli ham shu yerda —
            savolingiz tashqi model xizmatlariga yuborilmaydi.
          </p>
        )}
        <p>
          Qonun talab qilgan hollarda vakolatli organga maʼlumot berilishi
          mumkin. Bunday holatda ham berish mumkin boʻlgani —{" "}
          <strong>maskalangan</strong> yozuv.
        </p>

        <h2>6. Qancha saqlanadi</h2>
        <ul>
          <li>
            <strong>Soʻrovlar jurnali</strong> — muddatsiz. U xizmat
            sifatini vaqt boʻyicha oʻlchash uchun kerak va shaxsiy maʼlumot
            saqlamaydi
          </li>
          <li>
            <strong>Hisob va yozishmalar</strong> — hisob oʻchirilgunga qadar
          </li>
        </ul>

        <h2>7. Sizning huquqlaringiz</h2>
        <p>Hisobingiz boʻlsa, murojaat qilib quyidagilarni soʻrashingiz mumkin:</p>
        <ul>
          <li>Sizga tegishli maʼlumotni koʻrish</li>
          <li>Yozishmalar tarixini oʻchirish</li>
          <li>Hisobni butunlay oʻchirish</li>
        </ul>
        <p className="hujjat-izoh">
          Maskalangan jurnal yozuvlari sizga bogʻlanmagani uchun ularni alohida
          topib oʻchirish texnik jihatdan mumkin emas — aynan shu sabab ular
          shaxsiy maʼlumot hisoblanmaydi.
        </p>

        <h2>8. Kuki</h2>
        <p>
          Faqat zarur kuki ishlatiladi — kirgan holatni saqlash uchun.
          Kuzatuv va reklama kukilari yoʻq.
        </p>

        <h2>9. Bogʻlanish</h2>
        <p>
          Maxfiylik boʻyicha savol:{" "}
          <a href="https://t.me/ceoNeuron" target="_blank" rel="noreferrer">@ceoNeuron</a>
        </p>

        <p className="hujjat-ogoh">
          <strong>Ushbu matn hali yurist tomonidan tasdiqlanmagan.</strong> U
          tizimning haqiqiy xatti-harakatidan olingan va yopiq sinov davri
          uchun moʻljallangan. Ommaviy foydalanishdan oldin huquqiy
          ekspertizadan oʻtkaziladi.
        </p>

        <p className="hujjat-havola">
          Shuningdek: <Link href="/shartlar">Foydalanish shartlari</Link>
        </p>
      </section>
    </>
  );
}
