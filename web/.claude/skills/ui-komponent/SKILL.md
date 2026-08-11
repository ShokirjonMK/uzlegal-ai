---
name: ui-komponent
description: Loyihaning UI uslub tizimi — `globals.css` dagi `--` tokenlar, global sinflar (.shell, .nav, .tab, .lede), tugma/forma/karta koʻrinishi, light va dark rejim. Use when adding or changing any page, component, CSS, layout, button, form, or visual styling in src/app/. Tailwind YOʻQ — sof CSS.
---

# UI uslub tizimi

Loyihada **Tailwind yoʻq, CSS module yoʻq**. Bitta `src/app/globals.css`,
global sinflar va `--` oʻzgaruvchilar. Shu tizim ichida qoling.

## Token — yagona rang manbai

Rangni **hech qachon** toʻgʻridan-toʻgʻri yozmang (`#1e5f9e`, `rgb(...)`).
Faqat token:

| Guruh | Tokenlar |
|---|---|
| Fon | `--bg`, `--bg-soft`, `--bg-raised` |
| Chegara | `--border`, `--border-strong` |
| Matn | `--text`, `--text-dim`, `--text-faint` |
| Urgʻu | `--accent`, `--accent-soft` |
| Holat | `--danger`/`--danger-soft`, `--warn`/`--warn-soft`, `--ok`/`--ok-soft` |
| Shakl | `--radius`, `--shadow` |

Dark rejim `@media (prefers-color-scheme: dark)` da **faqat shu tokenlarni**
qayta belgilaydi. Shuning uchun tokendan foydalansangiz — dark rejim oʻzi
ishlaydi, qoʻshimcha ish yoʻq. Toʻgʻridan-toʻgʻri rang yozsangiz — dark rejimda
buziladi va buni faqat qoʻlda sinab koʻrganda sezasiz.

Yangi rang kerak boʻlsa: avval mavjud token yetadimi deb qarang. Yetmasa —
`:root` ga **va** dark blokiga qoʻshing, ikkalasiga.

## Tayyor global sinflar

Yangisini yasashdan oldin borini qidiring:

| Sinf | Vazifasi |
|---|---|
| `.shell` | Sahifa konteyneri — `max-width: 880px`, markazda |
| `.nav` / `.nav-inner` | Yopishqoq yuqori panel, `backdrop-filter: blur(8px)` |
| `.brand` | Logotip matni; ichidagi `<span>` urgʻu rangida |
| `.tab` / `.tab.active` | Navigatsiya havolalari (dumaloq, `999px`) |
| `.lede` | Sarlavha ostidagi izoh matni |
| `button` / `button.ghost` | Asosiy va ikkilamchi tugma |

`textarea`, `input[type=text]`, `select`, `label`, `h1`, `h2`, `a` — element
selektori bilan allaqachon uslublangan. Ularga sinf qoʻshish shart emas.

## Fokus — buzmang

```css
outline: 2px solid var(--accent);
outline-offset: -1px;
```

`outline: none` yozish taqiqlanadi. Klaviatura bilan yuradigan foydalanuvchi
uchun bu yagona koʻrsatkich. Yangi interaktiv element qoʻshsangiz, shu naqshni
takrorlang.

## Oʻlchamlar

- Asosiy matn `15px`, `line-height: 1.6`.
- `h1` — `22px`, `h2` — `16px`. Sahifada bitta `h1`.
- Ichki boʻshliq: `10px 12px` (forma), `9px 16px` (tugma).
- Radius — har doim `var(--radius)`, `999px` faqat dumaloq tablar uchun.

## Sahifa qoʻshish

Marshrutlar oʻzbekcha nomlanadi: `src/app/tahlil/`, `src/app/hujjat/`,
`src/app/qonunlar/`. Yangi sahifa ham shunday.

Tuzilma:

```tsx
export default function Sahifa() {
  return (
    <main className="shell">
      <h1>Sarlavha</h1>
      <p className="lede">Bir jumlalik izoh.</p>
      {/* ... */}
    </main>
  );
}
```

`.nav` `layout.tsx` da — sahifa ichida takrorlamang.

## Matn

Barcha koʻrinadigan matn — oʻzbek tilida, U+02BB/U+02BC apostroflar bilan.
Qarang: `uzbek-matn` skili. `npm run lint:uz` JSX matnini ham tekshiradi.

## Tekshirish

```bash
npm run check     # typecheck + lint:uz
npm run build     # build buzilmaganini tasdiqlash
```

Vizual oʻzgarish kiritsangiz, `npm run dev` bilan **ikkala rejimni ham**
koʻring — macOS: System Settings → Appearance.
