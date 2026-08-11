---
name: telegram-bot
description: Telegram bot (grammy) — buyruqlar, webhook va polling rejimlari, 4096 belgilik chegara, fayl qabul qilish, hisobot yuborish (npm run report). Use when touching src/lib/bot.ts, src/app/api/telegram/, scripts/bot-poll.ts, set-webhook.ts, tg-report.mts, or when the bot does not reply, repeats messages, or truncates output.
---

# Telegram bot

`grammy`. Ikkita rejim: **webhook** (`/api/telegram`) va **polling**
(`npm run bot:poll`). Bot mantiqi `src/lib/bot.ts` da — ikkalasi ham shu
`getBot()` ni ishlatadi.

## ⚠️ Webhook: darhol `200`, ishlov fonda

Telegram 60 soniya ichida javob kutadi. Model esa undan uzoq ishlaydi.
Shuning uchun marshrut update ni qabul qiladi va **kutmasdan** `OK`
qaytaradi:

```ts
void bot.handleUpdate(update).catch((err) => { /* log */ });
return new Response("OK");
```

`await` qoʻysangiz Telegram taymautga uchraydi va **bir xil xabarni qayta
yuboradi** — foydalanuvchi bir savolga ikki-uch javob oladi. Bu eng
tez-tez uchraydigan xato.

**Bu yondashuv doimiy Node serveri uchun.** Serverless da (funksiya javobdan
keyin toʻxtatiladi) fon ishlovi tugamay qoladi — u yerda navbat (queue)
kerak yoki polling rejimiga oʻting.

## 4096 belgi chegarasi

Telegram xabari `TG_LIMIT = 4096` belgidan uzun boʻlolmaydi. `splitMessage()`
matnni boʻlaklarga ajratadi.

`ctx.reply()` ni xom uzun matn bilan chaqirmang — API xato qaytaradi va
javob umuman yetib bormaydi. Bot ichidagi yordamchi orqali yuboring.

Markdown ishlatilsa, boʻlish chegarasi formatlashni buzmasligiga eʼtibor
bering (ochilgan `*` yopilmay qolishi mumkin).

## Buyruqlar

Har biri oʻzbekcha va inglizcha nom bilan:

| Buyruq | Vazifasi |
|---|---|
| `/start` | Tanishtirish |
| `/help`, `/yordam` | Yordam |
| `/id` | Chat ID (ADMIN_CHAT_ID ni aniqlash uchun) |
| `/clear`, `/tozalash` | Suhbat tarixini tozalash |
| `/corpus`, `/baza` | Qonun bazasi holati |
| `/stat`, `/statistika` | Statistika |
| `/tizim`, `/system` | Tizim holati |
| `/xabar`, `/broadcast` | Ommaviy xabar (faqat admin) |
| `/document`, `/hujjat` | Hujjat yasash |

Yangi buyruq qoʻshsangiz — ikki tilda nom bering va `/help` matnini yangilang.

## Fayl qabul qilish

`MAX_FILE_BYTES = 20 MB`. Undan katta fayl rad etiladi — Telegram Bot API
cheklovi, oshirib boʻlmaydi.

Kengaytma `SUPPORTED_EXTENSIONS` bilan tekshiriladi (`.txt .md .pdf .docx
.html .htm`). Matn ajratish `src/lib/util/extract.ts` orqali —
`yuridik-hujjat` skiliga qarang.

## Sozlash

`.env.local`: `TELEGRAM_BOT_TOKEN`, `ADMIN_CHAT_ID`,
`TELEGRAM_WEBHOOK_SECRET` (ixtiyoriy, lekin tavsiya etiladi).

```bash
npm run bot:set-webhook    # webhook manzilini oʻrnatish
npm run bot:poll           # polling rejimi (lokal ishlab chiqish uchun)
```

Webhook secret oʻrnatilgan boʻlsa, marshrut
`x-telegram-bot-api-secret-token` sarlavhasini tekshiradi va mos kelmasa
`403` qaytaradi.

**Webhook va polling bir vaqtda ishlamaydi.** Lokalda `bot:poll` ishlatsangiz,
avval webhook ni oʻchiring — aks holda updatelar boʻlinib ketadi.

## Ish hisobotlari

Bot kanalidan alohida: `CLAUDE.md` talab qiladigan `pm-start` / `pm-done`
hisobotlari `scripts/tg-report.mts` orqali yuboriladi.

```bash
npm run report -- --kind pm-start --id 8 --title "Sarlavha" --body "Matn"
cat hisobot.txt | npm run report -- --kind pm-done --id 8 --title "Sarlavha"
```

Turlari: `pm-start`, `dev`, `qa`, `qa-fail`, `pm-done`.

## Tekshirish

QA majburiy: `getMe` **va haqiqiy xabar yuborish**.

```bash
curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe"
curl -s localhost:3000/api/telegram          # webhook holati
npm run report -- --kind dev --id 0 --title "Sinov" --body "Tekshiruv"
```

`getMe` ishlashi bot tirikligini bildiradi, lekin webhook toʻgʻri
sozlanganini emas — ikkalasini ham tekshiring.
