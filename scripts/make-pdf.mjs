/**
 * Markdown → PDF (Chrome headless orqali).
 *
 * NEGA CHROME, NEGA `wkhtmltopdf` YOKI `reportlab` EMAS:
 *
 * 1. Oʻzbek lotin alifbosida `oʻ` va `gʻ` U+02BB modifikator belgisi
 *    bilan yoziladi. Koʻp PDF kutubxonalari uni tashlab yuboradi yoki
 *    kvadrat qutiga aylantiradi — hujjat oʻqib boʻlmas holga keladi.
 *    Chrome brauzer shrift stekini ishlatadi va bu belgini toʻgʻri
 *    chizadi.
 * 2. Yangi bogʻliqlik qoʻshilmaydi — Chrome allaqachon oʻrnatilgan.
 *
 * Ishlatish:
 *   node scripts/make-pdf.mjs <kirish.md> <chiqish.pdf> "Sarlavha" [muqova-osti]
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";

const CHROME_CANDIDATES = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
];

function findChrome() {
  const found = CHROME_CANDIDATES.find((p) => existsSync(p));
  if (!found) throw new Error("Chrome topilmadi — PDF yasab boʻlmaydi");
  return found;
}

// ── Markdown → HTML ────────────────────────────────────────────────────────
//
// Ataylab kichik oʻram: bizga faqat shu hujjatlarda ishlatilgan belgilash
// kerak. Toʻliq markdown kutubxonasi qoʻshish — yangi bogʻliqlik va yangi
// xatolar manbai.

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function inline(s) {
  return escapeHtml(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s.,;:)!?]|$)/g, "$1<em>$2</em>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
}

function renderTable(rows) {
  const cells = (line) =>
    line.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
  const head = cells(rows[0]);
  const align = cells(rows[1]).map((c) =>
    c.endsWith(":") ? (c.startsWith(":") ? "center" : "right") : "left",
  );
  const body = rows.slice(2).map(cells);

  const th = head
    .map((c, i) => `<th style="text-align:${align[i] ?? "left"}">${inline(c)}</th>`)
    .join("");
  const tr = body
    .map(
      (r) =>
        "<tr>" +
        r
          .map((c, i) => `<td style="text-align:${align[i] ?? "left"}">${inline(c)}</td>`)
          .join("") +
        "</tr>",
    )
    .join("\n");
  return `<table><thead><tr>${th}</tr></thead><tbody>\n${tr}\n</tbody></table>`;
}

function markdownToHtml(md) {
  const lines = md.split(/\r?\n/);
  const out = [];
  let i = 0;
  let listType = null;

  const closeList = () => {
    if (listType) {
      out.push(`</${listType}>`);
      listType = null;
    }
  };

  while (i < lines.length) {
    const line = lines[i];

    // Kod bloki
    if (line.startsWith("```")) {
      closeList();
      const body = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) body.push(lines[i++]);
      i++;
      out.push(`<pre><code>${escapeHtml(body.join("\n"))}</code></pre>`);
      continue;
    }

    // Jadval
    if (line.trim().startsWith("|") && lines[i + 1]?.includes("---")) {
      closeList();
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(lines[i++]);
      out.push(renderTable(rows));
      continue;
    }

    // Sarlavha
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      closeList();
      const level = heading[1].length;
      out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      i++;
      continue;
    }

    // Ajratuvchi
    if (/^---+$/.test(line.trim())) {
      closeList();
      out.push("<hr>");
      i++;
      continue;
    }

    // Iqtibos
    if (line.startsWith("> ")) {
      closeList();
      const body = [];
      while (i < lines.length && lines[i].startsWith(">")) {
        body.push(lines[i].replace(/^>\s?/, ""));
        i++;
      }
      out.push(`<blockquote>${inline(body.join(" "))}</blockquote>`);
      continue;
    }

    // Roʻyxat
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+\.\s+(.*)$/.exec(line);
    if (bullet || numbered) {
      const want = bullet ? "ul" : "ol";
      if (listType !== want) {
        closeList();
        out.push(`<${want}>`);
        listType = want;
      }
      out.push(`<li>${inline((bullet ?? numbered)[1])}</li>`);
      i++;
      continue;
    }

    if (!line.trim()) {
      closeList();
      i++;
      continue;
    }

    closeList();
    out.push(`<p>${inline(line)}</p>`);
    i++;
  }

  closeList();
  return out.join("\n");
}

// ── Sahifa qolipi ──────────────────────────────────────────────────────────

function page(title, subtitle, bodyHtml) {
  const today = process.env.UZLEGAL_PDF_DATE || "2026-08-12";
  return `<!doctype html>
<html lang="uz"><head><meta charset="utf-8"><title>${escapeHtml(title)}</title>
<style>
  @page { size: A4; margin: 20mm 16mm; }
  * { box-sizing: border-box; }
  body {
    font-family: "Segoe UI", "Noto Sans", system-ui, sans-serif;
    font-size: 10.5pt; line-height: 1.55; color: #14181f; margin: 0;
  }
  .cover {
    page-break-after: always; display: flex; flex-direction: column;
    justify-content: center; min-height: 245mm; border-left: 5px solid #1b5e9c;
    padding-left: 14mm;
  }
  .cover .eyebrow { font-size: 10pt; letter-spacing: .16em; text-transform: uppercase; color: #1b5e9c; font-weight: 600; }
  .cover h1 { font-size: 30pt; line-height: 1.15; margin: 8mm 0 4mm; font-weight: 700; letter-spacing: -.01em; }
  .cover .sub { font-size: 13pt; color: #4a5461; margin-bottom: 14mm; max-width: 130mm; }
  .cover .meta { font-size: 9.5pt; color: #6b7785; border-top: 1px solid #dfe4ea; padding-top: 5mm; }
  .cover .meta b { color: #14181f; font-weight: 600; }

  h1 { font-size: 18pt; margin: 10mm 0 4mm; padding-bottom: 2mm; border-bottom: 2px solid #1b5e9c; page-break-after: avoid; }
  h2 { font-size: 13.5pt; margin: 8mm 0 3mm; color: #0f3f6b; page-break-after: avoid; }
  h3 { font-size: 11.5pt; margin: 6mm 0 2mm; color: #24303d; page-break-after: avoid; }
  h4 { font-size: 10.5pt; margin: 4mm 0 2mm; color: #4a5461; page-break-after: avoid; }
  p { margin: 0 0 3mm; }
  ul, ol { margin: 0 0 3mm; padding-left: 6mm; }
  li { margin-bottom: 1.2mm; }
  hr { border: none; border-top: 1px solid #e3e8ee; margin: 6mm 0; }

  table { width: 100%; border-collapse: collapse; margin: 3mm 0 5mm; font-size: 9.5pt; page-break-inside: avoid; }
  th { background: #f2f6fa; text-align: left; font-weight: 600; color: #0f3f6b; }
  th, td { border: 1px solid #dde4ec; padding: 1.8mm 2.6mm; vertical-align: top; }
  tbody tr:nth-child(even) { background: #fafbfd; }

  code { font-family: "Cascadia Mono", Consolas, monospace; font-size: 9pt; background: #f2f4f7; padding: .4mm 1.2mm; border-radius: 2px; }
  pre { background: #f7f9fb; border: 1px solid #e3e8ee; border-left: 3px solid #1b5e9c; padding: 3mm 4mm; overflow-x: auto; page-break-inside: avoid; margin: 3mm 0 5mm; }
  pre code { background: none; padding: 0; font-size: 8.6pt; line-height: 1.45; }

  blockquote { margin: 3mm 0; padding: 2.5mm 4mm; background: #fff8e6; border-left: 3px solid #e0a800; color: #4a3c10; }
  a { color: #1b5e9c; text-decoration: none; }

  .footer { position: fixed; bottom: 0; left: 0; right: 0; font-size: 8pt; color: #93a0ad; border-top: 1px solid #e9edf2; padding-top: 1.5mm; }
</style></head><body>
<div class="cover">
  <div class="eyebrow">UzLegal-AI</div>
  <h1>${escapeHtml(title)}</h1>
  <div class="sub">${escapeHtml(subtitle)}</div>
  <div class="meta">
    <b>Muallif:</b> Shokirjon Madaminov (ShokirjonMK · MKdev)<br>
    <b>Aloqa:</b> @ceoNeuron<br>
    <b>Sana:</b> ${today}<br>
    <b>Repo:</b> github.com/ShokirjonMK/uzlegal-ai
  </div>
</div>
${bodyHtml}
<div class="footer">UzLegal-AI · Shokirjon Madaminov (@ceoNeuron) · ${today}</div>
</body></html>`;
}

// ── Asosiy ─────────────────────────────────────────────────────────────────

const [input, output, title, subtitle = ""] = process.argv.slice(2);
if (!input || !output || !title) {
  console.error('Ishlatish: node scripts/make-pdf.mjs <kirish.md> <chiqish.pdf> "Sarlavha" [izoh]');
  process.exit(2);
}

const md = readFileSync(input, "utf8");
const html = page(title, subtitle, markdownToHtml(md));

const htmlPath = resolve(tmpdir(), `uzlegal-pdf-${Date.now()}.html`);
writeFileSync(htmlPath, html, "utf8");

mkdirSync(dirname(resolve(output)), { recursive: true });

execFileSync(findChrome(), [
  "--headless",
  "--disable-gpu",
  "--no-pdf-header-footer",
  `--print-to-pdf=${resolve(output)}`,
  `file:///${htmlPath.replace(/\\/g, "/")}`,
], { stdio: "ignore" });

console.log(`✓ ${output}`);
