import Link from "next/link";

/**
 * Vaqtincha yopilgan boʻlim uchun sahifa.
 *
 * DIZAYN QOIDASI: sabab AYTILADI. «Texnik ishlar» kabi mazmunsiz xabar
 * foydalanuvchini xafa qiladi va ishonchni yoʻqotadi — ayniqsa huquqiy
 * mahsulotda, u yerda ishonch yagona sarmoya.
 *
 * Bu yerda sabab halol: boʻlim javobni iqtibos nazoratidan oʻtkazmasdi.
 * Buni aytish mahsulotni zaif koʻrsatmaydi — aksincha, nazorat borligini
 * va u jiddiy ekanini koʻrsatadi.
 */
export function YopiqYuza({ sarlavha, sabab }: { sarlavha: string; sabab: string }) {
  return (
    <>
      <h1>{sarlavha}</h1>
      <section className="yopiq" role="status">
        <p className="yopiq-sabab">{sabab}</p>
        <p className="yopiq-taklif">
          Shu vaqt ichida <Link href="/norma">Norma topuvchi</Link> dan
          foydalaning: u savolingizga tegishli moddani va uning{" "}
          <strong>aynan matnini</strong> koʻrsatadi. U model chaqirmaydi,
          shuning uchun hech narsa oʻylab topa olmaydi.
        </p>
      </section>
    </>
  );
}
