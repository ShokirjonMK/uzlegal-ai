/**
 * Streaming paytida o'zbekcha matnni tuzatish.
 *
 * Muammo: apostrof bo'laklar chegarasida ikkiga bo'linib qolishi mumkin —
 * bir bo'lak "...bo" bilan tugab, keyingisi "'lim..." bilan boshlanadi.
 * Har bir bo'lakni alohida tuzatsak, "o" dan keyingi apostrof noto'g'ri
 * belgiga (ʼ o'rniga ʻ kerak) aylanadi.
 *
 * Yechim: bo'lak oxiridagi `o`/`g` harfini ushlab qolamiz va keyingi
 * bo'lak bilan birga qayta ishlaymiz.
 */

import { fixApostrophes } from "./orthography";

export class UzbekStreamPolisher {
  private carry = "";

  /** Navbatdagi bo'lakni tuzatib qaytaradi (bir qism ushlab qolinishi mumkin). */
  push(chunk: string): string {
    const text = this.carry + chunk;
    this.carry = "";
    if (!text) return "";

    // Oxirgi belgi `o`/`g` bo'lsa — keyingi bo'lakda apostrof kelishi mumkin.
    const last = text.at(-1) ?? "";
    if (/[oOgG]/.test(last)) {
      this.carry = last;
      return fixApostrophes(text.slice(0, -1));
    }

    return fixApostrophes(text);
  }

  /** Oqim tugagach ushlab qolingan qismni chiqaradi. */
  flush(): string {
    const rest = this.carry;
    this.carry = "";
    return rest ? fixApostrophes(rest) : "";
  }
}
