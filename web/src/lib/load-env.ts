/**
 * `.env.local` va `.env` fayllarini yuklaydi.
 *
 * Next.js buni o'zi qiladi, lekin CLI va skriptlar `tsx` orqali to'g'ridan-to'g'ri
 * ishga tushadi — ular uchun qo'lda yuklash kerak.
 */

import { existsSync } from "node:fs";
import { resolve } from "node:path";

let loaded = false;

/** Muhit fayllarini yuklaydi (bir marta). Avvalgi qiymatlar ustiga yozilmaydi. */
export function loadEnv(cwd: string = process.cwd()): void {
  if (loaded) return;
  loaded = true;

  // Kechroq turgani ustunroq bo'lishi uchun teskari tartibda yuklaymiz:
  // process.loadEnvFile mavjud qiymatlarni ustiga yozmaydi.
  for (const name of [".env.local", ".env"]) {
    const path = resolve(cwd, name);
    if (!existsSync(path)) continue;
    try {
      process.loadEnvFile(path);
    } catch (err) {
      console.warn(
        `Ogohlantirish: ${name} faylini oʻqib boʻlmadi:`,
        err instanceof Error ? err.message : err,
      );
    }
  }
}
