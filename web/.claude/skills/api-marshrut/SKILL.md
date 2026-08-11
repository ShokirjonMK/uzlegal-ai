---
name: api-marshrut
description: API marshrut naqshi — route.ts tuzilishi, SSE streaming (sseResponse/readSse), xato javoblari (errorJson), API kalit tekshiruvi, runtime sozlamalari. Use when adding or changing anything under src/app/api/, debugging streaming, CORS, 401/500 responses, or wiring a new endpoint to a service in src/lib/services/.
---

# API marshrut naqshi

Barcha marshrutlar bitta shaklga amal qiladi. Yangisini yozganda shundan
nusxa oling — `src/app/api/ask/route.ts` etalon.

## Har bir `route.ts` boshida

```ts
export const runtime = "nodejs";        // Edge EMAS
export const dynamic = "force-dynamic";
export const maxDuration = 300;
```

`runtime = "nodejs"` majburiy: `node:sqlite` (RAG doʻkoni), `unpdf`,
`mammoth` va `docx` Edge runtime da ishlamaydi. Buni tushirib qoldirsangiz
xato faqat deploy paytida chiqadi.

`maxDuration = 300` — model javobi uzoq davom etadi.

## Tartib: kalit → JSON → validatsiya → xizmat → xato

```ts
export async function POST(request: Request): Promise<Response> {
  if (!checkApiKey(request)) return errorJson("Ruxsat yoʻq.", 401);

  let body: AskRequest;
  try {
    body = (await request.json()) as AskRequest;
  } catch {
    return errorJson("Soʻrov JSON formatida boʻlishi kerak.");
  }

  if (!body.question?.trim()) {
    return errorJson("`question` maydoni boʻsh boʻlmasligi kerak.");
  }

  try {
    return Response.json(await ask(body));
  } catch (err) {
    return errorJson(humanError(err), 500);
  }
}
```

Toʻrtta qoida:

1. **Mantiq marshrutda emas.** `route.ts` faqat kirishni tekshiradi va
   `src/lib/services/` dagi funksiyani chaqiradi. Biznes mantiqni bu yerga
   yozmang — bot va CLI ham shu xizmatlarni chaqiradi.
2. **Xato matni oʻzbekcha va foydalanuvchiga tushunarli.** `errorJson()`
   standarti `400`. Xom `err.message` ni bermang — `humanError(err)`.
3. **API kalit** — `checkApiKey(request)`, `401`.
4. **Kutilmagan xato** — `500`, lekin stack trace javobga tushmaydi.

## Streaming (SSE)

Oqim kerak boʻlsa xizmat `AsyncGenerator<StreamEvent>` qaytaradi:

```ts
import { sseResponse } from "@/lib/util/sse";
return sseResponse(streamAsk(body));
```

`sseResponse()` allaqachon toʻgʻri sarlavhalarni qoʻyadi:

```
content-type: text/event-stream; charset=utf-8
cache-control: no-cache, no-transform
x-accel-buffering: no        ← nginx buferlashini oʻchiradi
```

`x-accel-buffering` ni olib tashlamang — proksi ortida oqim "qotib qoladi"
va sabab topish qiyin.

Generator ichida xato chiqsa `sseResponse` uni `{type:"error"}` hodisasiga
aylantiradi va oqimni yopadi — `try/catch` ni yana qoʻshish shart emas.

Brauzer tomonda:

```ts
import { readSse } from "@/lib/util/sse";
for await (const ev of readSse(response)) { /* ... */ }
```

## Mavjud marshrutlar

| Marshrut | Metod | Nima qiladi |
|---|---|---|
| `/api/ask` | POST | Savol-javob, oddiy JSON (bot/integratsiya uchun) |
| `/api/chat` | POST | Savol-javob, SSE oqim (web UI) |
| `/api/search` | GET | Qonun bazasidan qidiruv |
| `/api/generate` | GET/POST | Shablon roʻyxati / hujjat yasash |
| `/api/analyze` | POST | Hujjat tahlili |
| `/api/review` | POST | Hujjatni koʻrib chiqish |
| `/api/telegram` | POST/GET | Webhook / holat |
| `/api/health` | GET | Tiriklik tekshiruvi |

`GET` — faqat oʻzgartirmaydigan amallar (qidiruv, roʻyxat, holat).

## Tekshirish

`CLAUDE.md` QA talabi: API marshrut oʻzgarsa — server ishga tushirilib,
**haqiqiy `curl` soʻrovi** yuboriladi. Faqat typecheck yetarli emas.

```bash
npm run dev
curl -s localhost:3000/api/health
curl -s -X POST localhost:3000/api/ask \
  -H 'content-type: application/json' \
  -d '{"question":"Mehnat shartnomasi qanday bekor qilinadi?"}' | head -30

# SSE ni koʻrish uchun:
curl -N -X POST localhost:3000/api/chat \
  -H 'content-type: application/json' -d '{"question":"salom"}'
```

`curl -N` — buferlashsiz, oqimni real vaqtda koʻrsatadi.
