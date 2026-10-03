import Link from "next/link";

export const metadata = {
  title: "Foydalanish shartlari — UzLegal-AI",
  description: "Xizmatdan foydalanish qoidalari, chegaralar va javobgarlik.",
};

/**
 * Foydalanish shartlari.
 *
 * MUHIM: bu matn **yurist tasdigʻidan oʻtmagan**. U mahsulotning
 * haqiqiy xatti-harakati asosida yozilgan (nima saqlanadi, nima
 * saqlanmaydi, qanday chegaralar bor) va yopiq sinov uchun yetarli.
 * Ommaviy ishga tushirishdan oldin yurist koʻrib chiqishi shart —
 * bu sahifaning oxirida ochiq aytilgan.
 *
 * YOZISH QOIDASI: har band nimani ANIQ anglatishini aytadi. «Xizmat
 * «boricha» taqdim etiladi» kabi shablon ibora oʻrniga — nima
 * kafolatlanmasligi va NEGA kafolatlanmasligi yoziladi. Huquqiy
 * mahsulotda foydalanuvchi aynan shu chegarani bilishi kerak.
 */
export default function ShartlarSahifasi() {
  return (
    <>
      <h1>Foydalanish shartlari</h1>
      <p className="lede">
        Oxirgi tahrir: 2026-yil 25-avgust. Xizmatdan foydalanish shu
        shartlarni qabul qilishni anglatadi.
      </p>

      <section className="hujjat">
        <h2>1. Xizmat nima qiladi</h2>
        <p>
          UzLegal-AI — Oʻzbekiston Respublikasi qonunchiligi boʻyicha{" "}
          <strong>tadqiqot vositasi</strong>. U savolingizga tegishli boʻlishi
          mumkin boʻlgan normalarni topadi va ularning matnini koʻrsatadi.
        </p>
        <p>
          Bilim bazasi <a href="https://lex.uz" target="_blank" rel="noreferrer">lex.uz</a>{" "}
          da eʼlon qilingan ochiq hujjatlardan yigʻilgan. Har bir natija
          manbaga havola bilan beriladi — koʻrsatilgan matnni asl hujjatda
          tekshirish mumkin va tavsiya etiladi.
        </p>

        <h2>2. Xizmat nima qilmaydi</h2>
        <p>
          <strong>Bu yuridik maslahat emas.</strong> Xizmat advokat yoki
          yuristning oʻrnini bosmaydi va bosa olmaydi. Sizning holatingizga
          qaysi norma qanday qoʻllanishini aniqlash — huquqiy talqin, va u
          malakali mutaxassisning ishi.
        </p>
        <p>Xizmat quyidagilarni bajarmaydi:</p>
        <ul>
          <li>Sizning ishingiz boʻyicha xulosa yoki tavsiya bermaydi</li>
          <li>Hujjatlarni sizning nomingizdan imzolamaydi yoki topshirmaydi</li>
          <li>Sud amaliyotini bashorat qilmaydi</li>
          <li>Boshqa davlatlar qonunchiligini qamramaydi</li>
        </ul>

        <h2>3. Aniqlik va chegaralar</h2>
        <p>
          Biz aniqlik uchun harakat qilamiz, lekin <strong>uni
          kafolatlamaymiz</strong>. Aniq bilingan chegaralar:
        </p>
        <ul>
          <li>
            Bilim bazasi <strong>toʻliq emas</strong> — u Oʻzbekiston
            qonunchiligining bir qismini qamraydi
          </li>
          <li>
            Hujjat holati (<em>bekor qilingan / bekor qilinmagan</em>) hujjat
            matnidagi belgilar asosida aniqlanadi, alohida reestr boʻyicha
            tasdiqlanmaydi
          </li>
          <li>
            Baza davriy yangilanadi; eng soʻnggi tahrirlar hali tushmagan
            boʻlishi mumkin
          </li>
          <li>Qidiruv tegishli normani topmasligi ham mumkin</li>
        </ul>
        <p>
          Shuning uchun: <strong>muhim qarordan oldin normani asl manbada
          tekshiring va yurist bilan maslahatlashing.</strong>
        </p>

        <h2>4. Javobgarlik</h2>
        <p>
          Xizmat maʼlumot beradi, qaror qabul qilmaydi. Xizmatdan olingan
          maʼlumot asosida koʻrilgan choralar va ularning oqibatlari uchun
          javobgarlik <strong>foydalanuvchi zimmasida</strong>.
        </p>
        <p>
          Xizmat uzluksiz ishlashi kafolatlanmaydi: texnik ishlar, yangilanish
          yoki nosozlik tufayli u vaqtincha mavjud boʻlmasligi mumkin.
        </p>

        <h2>5. Foydalanish qoidalari</h2>
        <p>Xizmatdan foydalanganda quyidagilar taqiqlanadi:</p>
        <ul>
          <li>
            Avtomatlashtirilgan ommaviy soʻrovlar orqali xizmatni ortiqcha
            yuklash
          </li>
          <li>
            Xizmat javoblarini <strong>yuridik maslahat sifatida</strong>{" "}
            uchinchi shaxslarga qayta sotish yoki taqdim etish
          </li>
          <li>Xavfsizlik chegaralarini aylanib oʻtishga urinish</li>
          <li>Qonunga zid maqsadda foydalanish</li>
        </ul>

        <h2>6. Mualliflik</h2>
        <p>
          Qonun matnlari — davlat hujjatlari va mualliflik huquqi obyekti
          emas. Xizmatning oʻzi (dastur kodi, tuzilma, interfeys) muallifga
          tegishli.
        </p>

        <h2>7. Shartlarning oʻzgarishi</h2>
        <p>
          Shartlar oʻzgarishi mumkin. Muhim oʻzgarishlar shu sahifada
          tahrir sanasi bilan koʻrsatiladi.
        </p>

        <h2>8. Bogʻlanish</h2>
        <p>
          Savol yoki eʼtiroz boʻlsa: <a href="https://t.me/ceoNeuron" target="_blank" rel="noreferrer">@ceoNeuron</a>
        </p>

        <p className="hujjat-ogoh">
          <strong>Ushbu matn hali yurist tomonidan tasdiqlanmagan.</strong> U
          xizmatning haqiqiy xatti-harakati asosida yozilgan va yopiq sinov
          davri uchun moʻljallangan. Ommaviy foydalanishdan oldin huquqiy
          ekspertizadan oʻtkaziladi.
        </p>

        <p className="hujjat-havola">
          Shuningdek: <Link href="/maxfiylik">Maxfiylik siyosati</Link>
        </p>
      </section>
    </>
  );
}
