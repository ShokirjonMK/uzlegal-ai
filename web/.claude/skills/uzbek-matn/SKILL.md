---
name: uzbek-matn
description: Oʻzbek matni bilan ishlash — apostrof (U+02BB / U+02BC), lotin/kirill yozuvi, til aniqlash, yuridik atamalar lugʻati, `src/lib/uz/` moduli. Use when writing or editing any user-facing Uzbek text, system prompts, error messages, UI strings, or when touching src/lib/uz/, lint-uz, glossary, transliteration, script detection, or when `npm run lint:uz` fails.
---

# Oʻzbek matni

`CLAUDE.md` apostrof qoidasini aytadi. Bu skill — uni **amalda** qanday
qoʻllash va qayerda tuzoq borligi.

## Ikkita belgi, ikkita vazifa

| Belgi | Kod | Qayerda | Misol |
|---|---|---|---|
| `ʻ` | U+02BB | faqat `o` va `g` dan keyin — harf qismi | `oʻzbek`, `gʻalaba`, `Oʻzbekiston` |
| `ʼ` | U+02BC | tutuq belgisi — qolgan hamma joyda | `maʼno`, `sanʼat`, `taʼsir`, `sunʼiy` |

ASCII `'`, `'`, `` ` `` — **hech qachon**. `npm run lint:uz` tutadi.

Qoʻlda yozmang — `fixApostrophes()` bor:

```ts
import { fixApostrophes } from "@/lib/uz/orthography";
fixApostrophes(text);                                // oʻzbekcha matn
fixApostrophes(text, { skipLatinContractions: true }); // ichida ingliz boʻlsa
```

`skipLatinContractions` `don't`, `it's` kabi qisqartmalarni buzmaydi.

## ⚠️ Eng katta tuzoq: `detect.ts` lugʻati ASCII apostrof ishlatadi

`src/lib/uz/detect.ts` ichidagi soʻz lugʻati **ataylab** oddiy `'` bilan
yozilgan. Sababi: qidiruvdan oldin matn `foldForSearch()` dan oʻtadi va u
`ʻ ʼ ' ' \`` — hammasini ASCII `'` ga keltiradi.

**Agar u yerga `ʻ` yozsangiz, taqqoslash hech qachon mos kelmaydi va til
aniqlash jimgina buziladi** — xato bermaydi, shunchaki notoʻgʻri til qaytaradi.

Shu bois `detect.ts` da linter `// lint-uz-ignore` bilan chetlab oʻtiladi.
Boshqa faylda bunday istisno qilmang.

Qoida: **koʻrsatiladigan matn** → U+02BB/U+02BC. **Taqqoslanadigan matn** →
`foldForSearch()` dan oʻtkazing, ASCII qoldiring.

## Yozuv (skript) va til

```ts
import { detectLang, resolveLang } from "@/lib/uz/detect";
import { detectScript, foldForSearch } from "@/lib/uz/orthography";
```

- Qoʻllab-quvvatlanadi: `uz` (lotin/kirill), `ru`, `en`.
- Aniqlanmasa yoki matn qisqa boʻlsa — **oʻzbek lotin** (loyihaning asosiy tili).
- Sozlamada majburiy til boʻlsa, `resolveLang()` ni ishlating: `auto` boʻlsa
  aniqlangani, aks holda majburiy qiymat gʻalaba qiladi.
- Foydalanuvchi kirillda yozgan boʻlsa — javob ham kirillda. Yozuvni
  oʻzgartirmang.

## Tizim promptiga qoʻshish

Uslub qoidalari va atamalar lugʻati kodda tayyor — promptga qoʻlda yozmang:

```ts
import { styleRules } from "@/lib/uz/style";
import { glossaryBlock } from "@/lib/uz/glossary";

const system = [
  styleRules(lang, script),   // til + yozuvga mos uslub bloki
  glossaryBlock(),            // yuridik atamalar
].join("\n\n");
```

`glossary.ts` maqsadi — model ruscha kalka (`dogovor`, `isk`, `zayavleniye`)
oʻrniga rasmiy oʻzbek atamasini ishlatsin. Yangi chalkash atama uchrasa
`LEGAL_TERMS` ga qoʻshing; lugʻat promptga siqiq koʻrinishda tushadi, shuning
uchun faqat **haqiqatan chalkashadigan** atamalar kiritiladi.

## Aralash yozuv

Bitta soʻz ichida lotin va kirill boʻlmasligi kerak. Linter tutadi.
Bu koʻpincha nusxa-koʻchirishdan kelib chiqadi va koʻzga koʻrinmaydi.

## Oqim (streaming) bilan

`src/lib/uz/stream-polish.ts` — model chiqishini oqim davomida tozalaydi.
Toʻliq javobni kutib turib `fixApostrophes()` chaqirmang; oqimda boʻlak
chegarasi soʻz oʻrtasiga tushishi mumkin, stream-polish shuni hisobga oladi.

## Tekshirish

```bash
npm run lint:uz     # faqat matn linteri
npm run check       # typecheck + lint:uz — QA minimumi
```

Linter xato bersa, avval `fixApostrophes()` ni oʻylang. `lint-uz-ignore` —
faqat `detect.ts` kabi ataylab ASCII kerak boʻlgan joyda yoki hujjatdagi
"yomon misol" uchun.
