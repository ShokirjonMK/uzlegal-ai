/**
 * Qaysi mahsulot yuzasi ochiq — bitta joyda.
 *
 * ## Nima uchun bu fayl kerak boʻldi
 *
 * 2026-08-24 dagi taftish shuni koʻrsatdi: toʻrtta veb funksiyadan
 * **uchtasi** yadroning iqtibos darvozasini chetlab oʻtar ekan.
 *
 * | Sahifa | Yoʻl | Darvoza |
 * |---|---|---|
 * | Savol-javob | `/v1/consult` | ✓ toʻliq |
 * | `/norma` | `/v1/search` | ✓ qamrov |
 * | `/tahlil` | `/v1/generate` | ✗ yoʻq |
 * | `/hujjat` | `/v1/generate` | ✗ yoʻq |
 *
 * `/v1/generate` — bu `backend.generate(prompt)` dan boshqa hech narsa
 * emas. Yaʼni **qonun oʻylab topa oladigan yagona sahifalar** aynan
 * maslahatga eng oʻxshaydiganlari edi.
 *
 * ## Nima uchun sahifalar oʻchirilmadi
 *
 * Kod yomon emas — u **erta** yozilgan. Iqtibos darvozasi hujjat
 * tahliliga moslashtirilgandan keyin ular qaytadi. Shuning uchun kod
 * joyida qoladi, faqat yuzasi yopiladi va sababi ochiq aytiladi.
 *
 * ## Nima uchun uch qatlamda
 *
 * Navigatsiyadan olib tashlash **yetarli emas**: havolani qoʻlda kiritish
 * yoki eski xatcho'p sahifani baribir ochardi. Shuning uchun:
 *
 *   1. `NavTabs` — koʻrinmaydi
 *   2. Sahifa — sababni tushuntiradi
 *   3. API marshruti — 503 qaytaradi  ← eng muhimi
 *
 * Uchinchisi hal qiluvchi: faqat u haqiqiy himoya, qolgan ikkitasi
 * xushmuomalalik.
 */

import { config } from "./config";

export type Feature = "savol" | "norma" | "qonunlar" | "tahlil" | "hujjat" | "kabinet";

/**
 * Yopiq yuzalar va sababi. Sabab foydalanuvchiga koʻrsatiladi —
 * «texnik ishlar» kabi mazmunsiz xabar ishonchni yoʻqotadi.
 */
const YOPIQ: Partial<Record<Feature, string>> = {
  tahlil:
    "Hujjat tahlili vaqtincha yopilgan. Bu sahifa javobni iqtibos nazoratidan " +
    "oʻtkazmasdan chiqarardi — yaʼni tekshirilmagan huquqiy xulosa berishi mumkin edi. " +
    "Nazorat hujjat tahliliga moslashtirilgach qaytadi.",
  hujjat:
    "Hujjat tayyorlash vaqtincha yopilgan. Bu sahifa matnni iqtibos nazoratidan " +
    "oʻtkazmasdan yozardi — yaʼni hujjatga tekshirilmagan norma havolasi tushishi " +
    "mumkin edi. Nazorat qoʻshilgach qaytadi.",
};

/**
 * Muhit orqali qayta yoqish: `UZLEGAL_FEATURES=tahlil,hujjat`.
 *
 * Ishlab chiqish uchun kerak — aks holda men bu sahifalarni tuzatayotganda
 * ularni koʻra olmasdim. Ishga tushirishda **boʻsh qoldiriladi**.
 */
function majburanYoqilgan(): Set<string> {
  const raw = process.env["UZLEGAL_FEATURES"]?.trim();
  if (!raw) return new Set();
  return new Set(raw.split(",").map((s) => s.trim().toLowerCase()));
}

export function ochiqmi(feature: Feature): boolean {
  // Kabinet Mongo ga bogʻliq. Mongo sozlanmagan boʻlsa sahifa ochiladi,
  // lekin boʻsh koʻrinadi — bu nosozlikka oʻxshaydi. Yashirgan maʼqul.
  if (feature === "kabinet") return config.mongoEnabled;

  if (!(feature in YOPIQ)) return true;
  return majburanYoqilgan().has(feature);
}

/** Yopiq boʻlsa — sababi, aks holda `null`. */
export function yopiqSababi(feature: Feature): string | null {
  if (ochiqmi(feature)) return null;
  return YOPIQ[feature] ?? "Bu boʻlim vaqtincha mavjud emas.";
}

/** Ochiq yuzalar roʻyxati — serverda hisoblanadi, mijozga prop sifatida uzatiladi. */
export function ochiqYuzalar(): Feature[] {
  const hammasi: Feature[] = ["savol", "norma", "qonunlar", "tahlil", "hujjat", "kabinet"];
  return hammasi.filter(ochiqmi);
}
