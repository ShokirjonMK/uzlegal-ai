---
name: yuridik-hujjat
description: Hujjat generatsiyasi va tahlili — shablonlar (shartnoma, daʼvo arizasi, ishonchnoma), {{ORIN}} toʻldirish joylari, Markdown → .docx, fayldan matn ajratish (pdf/docx/html). Use when touching src/lib/services/generate.ts, analyze.ts, review.ts, src/lib/util/docx.ts, extract.ts, the /hujjat or /tahlil pages, or when adding a document template.
---

# Yuridik hujjat

Oqim: `GenerateRequest` → RAG dan manbalar → model → Markdown →
`GenerateResult` → `.docx`.

## Hujjat Markdown boʻlib chiqadi, HTML emas

Model **Markdown** qaytaradi. `.docx` shundan yasaladi, ekranda ham shu
koʻrsatiladi. Modelni HTML yoki tayyor docx XML chiqarishga majburlamang —
`markdownToDocx()` faqat Markdown tushunadi (`#`–`####` sarlavhalar,
paragraflar).

## `{{ORIN}}` — oʻylab topilgan maʼlumot oʻrniga

Foydalanuvchi bermagan har qanday maʼlumot uchun model `{{TOMON_NOMI}}`,
`{{SANA}}` kabi oʻrin qoldiradi. `extractPlaceholders()` ularni yigʻib,
`GenerateResult.placeholders` ga soladi va UI foydalanuvchiga roʻyxat
koʻrsatadi.

**Bu qoidani buzmang.** Model INN, manzil, sana yoki summani oʻzi toʻqib
yozsa — hujjat ishlatishga yaroqsiz va foydalanuvchi buni sezmasligi mumkin.
Naqsh: `/\{\{\s*([^}]+?)\s*\}\}/g`.

## Shablonlar

`src/lib/prompts.ts` → `TEMPLATE_NAMES`:

```
mehnat-shartnomasi · ijara-shartnomasi · oldi-sotdi-shartnomasi
xizmat-korsatish-shartnomasi · pudrat-shartnomasi
davo-arizasi · ishonchnoma · tilxat · ariza · pretenziya · erkin
```

Yangi shablon qoʻshish — uch joyda:

1. `DocTemplateId` (`src/lib/types.ts`)
2. `TEMPLATE_NAMES` (`src/lib/prompts.ts`) — nomi oʻzbekcha, U+02BB/U+02BC bilan
3. UI roʻyxati `TEMPLATE_LIST` dan avtomatik keladi — qoʻlda qoʻshmang

`erkin` alohida yoʻl: shablon nomi emas, foydalanuvchi tavsifi ishlatiladi.

## Shartnoma toʻliq boʻlishi shart

`generateSystemStable()` majburiy boʻlimlarni sanaydi: sarlavha, tomonlar,
predmet, huquq va majburiyatlar, narx va toʻlov tartibi, muddat, javobgarlik,
fors-major, nizolarni hal qilish, yakuniy qoidalar, rekvizitlar, imzolar.

Boʻlimni tashlab ketish — nuqson. Promptni qisqartirishdan oldin oʻylang.

## Fayldan matn ajratish

```ts
import { isSupported, SUPPORTED_EXTENSIONS } from "@/lib/util/extract";
```

`.txt .md .pdf .docx .html .htm` — `unpdf` (pdf) va `mammoth` (docx).
**Faqat server tomonda** (Node runtime) ishlaydi; client komponentdan
import qilmang.

Ajratilgan matn darhol `fixApostrophes()` dan oʻtadi — Word va PDF dan
kelgan matnda apostroflar deyarli har doim notoʻgʻri.

## `.docx` yasash

```ts
import { resultToDocx, safeFilename } from "@/lib/util/docx";

const buf = await resultToDocx(result);
const name = safeFilename(result.title, "docx");
```

`docx` kutubxonasi **dinamik import** qilinadi (`await import("docx")`) —
server bundlega kirmasin uchun. Yangi kod yozsangiz shu naqshni saqlang.

`safeFilename()` ni oʻtkazib yubormang: sarlavhada `/`, `:` va oʻzbekcha
belgilar boʻladi.

## Til va apostrof

`resolveLang()` bilan til aniqlanadi, chiqish `polishUzbek()` /
`UzbekStreamPolisher` dan oʻtadi. Oqimda `UzbekStreamPolisher` ishlatiladi —
toʻliq matnni kutib turib tozalamang. Batafsil: `uzbek-matn` skili.

## Tekshirish

QA majburiy — API oʻzgargan boʻlsa haqiqiy soʻrov:

```bash
npm run check
npm run dev
curl -s -X POST localhost:3000/api/generate \
  -H 'content-type: application/json' \
  -d '{"template":"ijara-shartnomasi","details":"Toshkentda 2 xonali kvartira, oyiga 4 mln soʻm"}' | head -40
```

Natijada koʻring: barcha boʻlimlar bormi, `{{...}}` oʻrinlar qoldirilganmi,
apostroflar toʻgʻrimi. `.docx` ni haqiqatan Word/Pages da ochib koʻring —
buzuq fayl `curl` da bilinmaydi.
