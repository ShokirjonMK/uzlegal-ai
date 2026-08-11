/**
 * Hujjat generatsiyasi: shartnoma, ariza, ishonchnoma va boshqa loyihalar.
 *
 * Hujjat Markdown ko'rinishida chiqadi; to'ldirilmagan joylar {{ORIN}} shaklida
 * qoldiriladi va alohida ro'yxat sifatida qaytariladi.
 */

import { complete, streamText } from "../llm";
import { config } from "../config";
import { generateSystemStable, sourcesBlock, templateName } from "../prompts";
import { retrieve } from "../rag/retrieve";
import { resolveLang } from "../uz/detect";
import { polishUzbek } from "../uz/orthography";
import { UzbekStreamPolisher } from "../uz/stream-polish";
import type { GenerateRequest, GenerateResult, StreamEvent, Usage } from "../types";

/** Hujjat matnidan {{ORIN}} shaklidagi to'ldirish joylarini yig'adi. */
export function extractPlaceholders(markdown: string): string[] {
  const found = new Set<string>();
  for (const m of markdown.matchAll(/\{\{\s*([^}]+?)\s*\}\}/g)) {
    if (m[1]) found.add(m[1].trim());
  }
  return [...found];
}

function buildPrompt(req: GenerateRequest): string {
  const parts: string[] = [];

  if (req.template === "erkin") {
    parts.push("Quyidagi tavsif asosida hujjat loyihasini tayyorlang.");
  } else {
    parts.push(`Quyidagi hujjat turini tayyorlang: ${templateName(req.template)}.`);
  }

  const fields = Object.entries(req.fields ?? {}).filter(([, v]) => v?.trim());
  if (fields.length > 0) {
    parts.push(
      "\nMaʼlum maʼlumotlar:\n" +
        fields.map(([k, v]) => `- ${k}: ${v}`).join("\n"),
    );
  }

  if (req.details?.trim()) {
    parts.push(`\nQoʻshimcha tafsilotlar:\n${req.details.trim()}`);
  }

  parts.push(
    "\nBerilmagan barcha maʼlumot uchun {{...}} shaklida oʻrin qoldiring. " +
      "Hujjat oxirida '## Eslatmalar' sarlavhasi ostida foydalanuvchi eʼtibor " +
      "berishi kerak boʻlgan 2–5 ta qisqa eslatma bering.",
  );

  return parts.join("\n");
}

/** Generatsiya uchun kerakli qonun normalarini topadi. */
async function findSources(req: GenerateRequest) {
  const query =
    req.template === "erkin"
      ? req.details
      : `${templateName(req.template)} ${req.details}`;
  return retrieve(query.slice(0, 2000), { topK: 8 });
}

/** Streaming generatsiya (web UI uchun). */
export async function* generateStream(
  req: GenerateRequest,
): AsyncGenerator<StreamEvent, void, unknown> {
  const { lang, script } = resolveLang(
    `${req.details} ${Object.values(req.fields ?? {}).join(" ")}`,
    req.lang ?? config.lang,
    req.script ?? config.script,
  );

  try {
    yield { type: "status", message: "Namunaviy normalar qidirilmoqda…" };
    const found = await findSources(req);
    yield { type: "status", message: "Hujjat tayyorlanmoqda…" };

    const polisher = new UzbekStreamPolisher();
    let usage: Usage | undefined;

    const stream = streamText({
      systemStable: generateSystemStable(lang, script),
      systemDynamic: sourcesBlock(found, lang),
      messages: [{ role: "user", content: buildPrompt(req) }],
      maxTokens: 32000,
      onDone: (u) => {
        usage = u;
      },
    });

    for await (const chunk of stream) {
      const text = lang === "uz" && script === "latn" ? polisher.push(chunk) : chunk;
      if (text) yield { type: "delta", text };
    }

    const tail = lang === "uz" && script === "latn" ? polisher.flush() : "";
    if (tail) yield { type: "delta", text: tail };

    yield { type: "done", usage };
  } catch (err) {
    const { humanError } = await import("../llm");
    yield { type: "error", message: humanError(err) };
  }
}

/** Streamingsiz generatsiya (API, bot, CLI uchun). */
export async function generate(req: GenerateRequest): Promise<GenerateResult> {
  const { lang, script } = resolveLang(
    `${req.details} ${Object.values(req.fields ?? {}).join(" ")}`,
    req.lang ?? config.lang,
    req.script ?? config.script,
  );

  const found = await findSources(req);

  const res = await complete({
    systemStable: generateSystemStable(lang, script),
    systemDynamic: sourcesBlock(found, lang),
    messages: [{ role: "user", content: buildPrompt(req) }],
    maxTokens: 32000,
  });

  const markdown =
    lang === "uz" && script === "latn" ? polishUzbek(res.text) : res.text.trim();

  return {
    title: extractTitle(markdown) ?? templateName(req.template),
    markdown,
    placeholders: extractPlaceholders(markdown),
    notes: extractNotes(markdown),
    lang,
    script,
    usage: res.usage,
  };
}

/** Markdown'dagi birinchi sarlavhani hujjat nomi sifatida oladi. */
function extractTitle(markdown: string): string | null {
  const m = /^#{1,2}\s+(.+)$/m.exec(markdown);
  return m?.[1]?.trim() ?? null;
}

/** "## Eslatmalar" bo'limidagi punktlarni ajratadi. */
function extractNotes(markdown: string): string[] {
  const m = /^#{1,3}\s*(?:Eslatmalar|Примечания|Notes)\s*$([\s\S]*)/im.exec(markdown);
  if (!m?.[1]) return [];
  return m[1]
    .split("\n")
    .map((l) => l.replace(/^\s*(?:[-*+]|\d+[.)])\s*/, "").trim())
    .filter((l) => l.length > 0 && !l.startsWith("#"));
}
