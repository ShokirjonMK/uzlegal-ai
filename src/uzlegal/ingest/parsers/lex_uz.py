"""lex.uz HTML parseri.

## Real struktura (2026-08-09 da Fuqarolik kodeksida o'rganilgan)

Hujjat **hujjat tartibida** joylashgan `lx_elem` bloklaridan iborat. Har bir
blok o'rovchi div bo'lib, uning klassi element **turini** bildiradi, ichidagi
`<div name="ID" id="ID">` esa matnni saqlaydi:

    <div class="CLAUSE_DEFAULT lx_elem" onmousemove="lx_mo(event,156152)">
      <div class="lx_elem2">…UI tugmalari…</div>
      <div name="156152" id="156152">Статья 1. Основные начала …</div>
    </div>

O'rovchi klasslar (Fuqarolik kodeksida o'lchangan):

| Klass                 | Soni | Ma'nosi                        |
|-----------------------|-----:|--------------------------------|
| `ACT_TITLE`           |    1 | Hujjat sarlavhasi              |
| `TEXT_HEADER_DEFAULT` |   50 | Bo'lim / bob sarlavhasi        |
| `CLAUSE_DEFAULT`      |  386 | **Modda sarlavhasi**           |
| `ACT_TEXT`            | 1251 | Matn xatboshisi                |
| `BY_DEFAULT`          |  131 | Band / kichik xatboshi         |

`CLAUSE_DEFAULT` soni moddalar soniga aynan teng — bu ishonchli chegara.

## Strategiya

Hujjatni **tartib bo'yicha** o'qiymiz va holat mashinasi yuritamiz:

* `TEXT_HEADER_DEFAULT` → ierarxiya yo'lini yangilaydi (bo'lim/bob)
* `CLAUSE_DEFAULT`      → yangi modda boshlanadi (sarlavha)
* `ACT_TEXT`/`BY_DEFAULT` → joriy moddaning tanasiga qo'shiladi

Bu TOC ga bog'lanishdan ishonchliroq: hujjat tartibi HTML da aniq, TOC esa
ba'zi hujjatlarda umuman bo'lmasligi mumkin. TOC faqat tekshiruv uchun
ishlatiladi.

## Ma'lum cheklovlar

* Sahifa 1.5–2 MB, javob vaqti ~17 s (`robots.txt`: Crawl-delay 20)
* Hujjat rus yoki o'zbek tilida; til matndan aniqlanadi
* Versiyalash bu modulda emas (alohida `versioning.py`)
"""

from __future__ import annotations

import html as html_lib
import logging
import re

from uzlegal.ingest.normalize import canonical, extract_article_number, extract_date, looks_russian
from uzlegal.ingest.types import AmendmentNote, DocType, Element, ParsedDocument, RawDocument

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# O'zgartirish eslatmalari
# --------------------------------------------------------------------------- #

# lex.uz o'zgartirishlarni matn ichida e'lon qiladi. Bu versiyalash uchun
# asosiy signal — ADR-006 va docs/03 § 3.4 ga qarang.
_AMENDMENT_MARKERS = re.compile(
    r"(Обратите внимание|Эътибор беринг|E[’'ʼ]tibor bering|"
    r"внесены изменения|ўзгартиш(лар)? киритилган|o[’'ʻ]zgartish(lar)? kiritilgan|"
    r"утратил[аи]? силу|ўз кучини йўқотган|o[’'ʻ]z kuchini yo[’'ʻ]qotgan)",
    re.IGNORECASE,
)

# O'zbek nashrlarida tahrir eslatmalari boshqa shaklda keladi — qavs ichida,
# modda yoki bob sarlavhasidan keyin alohida CLAUSE_DEFAULT blok sifatida:
#
#   (1-moddaning nomi Oʻzbekiston Respublikasining 2021-yil 21-apreldagi
#    OʻRQ-683-sonli Qonuni tahririda — Qonunchilik maʼlumotlari milliy bazasi…)
#
# Ular modda deb hisoblansa, haqiqiy modda ikkiga bo'linib, birinchisining
# tanasi bo'sh qoladi.
_EDITORIAL_KEYWORDS = re.compile(
    r"(tahririda|тахририда|таҳририда|asosida chiqarildi|"
    r"kiritilgan|киритилган|chiqarib tashlangan|чиқариб ташланган|"
    r"kuchini yo[’'ʻ]qotgan|кучини йўқотган|"
    r"O[’'ʻ]RQ[-\s]?\d|ЎРҚ[-\s]?\d|ЗРУ[-\s]?\d|"
    r"Qonunchilik ma[’'ʼ]lumotlari milliy bazasi)",
    re.IGNORECASE,
)

_PARENTHESISED = re.compile(r"^\s*\(.*\)\s*$", re.DOTALL)

_AMEND_TARGET = re.compile(
    r"(?:в\s+стать[юяи]\s+|стать[яи]\s+|(\d+)\s*[-–]?\s*модда|(\d+)\s*[-–]?\s*modda)(\d+)?",
    re.IGNORECASE,
)

_AMEND_DOC = re.compile(
    r"(Закон\w*\s+(?:РУз\s+)?от\s+[\d.]+\s*(?:г\.)?\s*№?\s*[\w-]*|"
    r"ЗРУ[-\s]?\d+|ZRU[-\s]?\d+|"
    r"(?:Қонун|Qonun)\w*\s+[\d.]+)",
    re.IGNORECASE,
)


def is_amendment_note(text: str) -> bool:
    """Matn o'zgartirish/tahrir eslatmasimi (haqiqiy modda yoki bob emas).

    Ikki shakl qo'llab-quvvatlanadi:

    * Rus nashrlari: «Обратите внимание: в статью 53 внесены изменения…»
    * O'zbek nashrlari: qavs ichidagi tahrir izohi —
      «(1-moddaning nomi … OʻRQ-683-sonli Qonuni tahririda — …)»

    Ikkinchi shakl uchun **qavs ichida bo'lishi** talab qilinadi, aks holda
    «…tahririda…» so'zi uchraydigan oddiy modda matni ham eslatma deb
    belgilanib qolardi.
    """
    if _AMENDMENT_MARKERS.search(text):
        return True
    return bool(_PARENTHESISED.match(text) and _EDITORIAL_KEYWORDS.search(text))


def parse_amendment(element_id: str, text: str) -> AmendmentNote:
    target = None
    m = _AMEND_TARGET.search(text)
    if m:
        target = next((g for g in m.groups() if g), None)

    doc_match = _AMEND_DOC.search(text)
    return AmendmentNote(
        element_id=element_id,
        raw_text=text[:500],
        target_article=target,
        amending_doc=doc_match.group(0).strip() if doc_match else None,
        effective_date=extract_date(text),
    )


# --------------------------------------------------------------------------- #
# Regexlar
# --------------------------------------------------------------------------- #

_WRAPPER = re.compile(r'<div class="([A-Z_]+) lx_elem"')

# DIQQAT: element ID lari **manfiy** bo'lishi mumkin.
# lex.uz da o'zbek (lotin) nashrlari manfiy ID bilan keladi:
#   ruscha  → /docs/111181,  element id="156152"
#   o'zbekcha → /docs/-111189, element id="-5443895"
# `(\d+)` minusni qamramaydi va butun hujjat bo'sh ajratilardi.
_CONTENT = re.compile(r'<div name="(-?\d+)" id="\1">(.*?)</div>', re.DOTALL)
_TOC_ENTRY = re.compile(r"scrollText\('(-?\d+)'\)")
_TITLE_TAG = re.compile(r"<title>(.*?)</title>", re.DOTALL | re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_SCRIPT_STYLE = re.compile(r"<(script|style)\b.*?</\1>", re.DOTALL | re.IGNORECASE)

# `<title>` tegining tuzilishi — 863/863 xom faylda o'lchangan:
#
#     <title>&nbsp;OʻRQ-982-сон 25.10.2024.&nbsp;Oʻzbekiston Respublikasi
#            Vazirlar Mahkamasi toʻgʻrisida</title>
#
# Ya'ni metama'lumot prefiksi (hujjat raqami va **qabul sanasi**)
# hujjat nomidan uzilmas bo'sh joy bilan ajratilgan. Sana sahifaning
# boshqa hech bir joyida yo'q: `ACT_TITLE` blokida u hech qachon
# uchramaydi (docs/22 § 1.1).
NBSP = "\u00a0"

HEADER_CLASSES = {"TEXT_HEADER_DEFAULT"}
ARTICLE_CLASSES = {"CLAUSE_DEFAULT"}
BODY_CLASSES = {"ACT_TEXT", "BY_DEFAULT", "ACT_FORM"}
TITLE_CLASSES = {"ACT_TITLE"}

# Har bir blokda takrorlanadigan UI matnlari
_UI_NOISE = re.compile(
    r"(Ҳужжатга таклиф юбориш|Аудиони тинглаш|Ҳужжат элементидан ҳавола олиш|"
    r"Hujjatga taklif yuborish|Audioni tinglash|Hujjat elementidan havola olish)"
)

# --------------------------------------------------------------------------- #
# Ierarxiya
# --------------------------------------------------------------------------- #

_LEVEL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("part", re.compile(r"^\s*(?:Часть|Қисм|Qism)\b", re.I)),
    ("section", re.compile(r"^\s*(?:РАЗДЕЛ|БЎЛИМ|BO['ʻ‘]LIM)\b", re.I)),
    ("subsection", re.compile(r"^\s*(?:Подраздел|Кичик\s*бўлим|Kichik\s*bo)", re.I)),
    ("chapter", re.compile(r"^\s*(?:ГЛАВА|БОБ|\d+\s*[-–]?\s*(?:боб|bob))\b", re.I)),
]

_LEVEL_ORDER = ["part", "section", "subsection", "chapter"]


def detect_header_level(title: str) -> str:
    for level, pattern in _LEVEL_PATTERNS:
        if pattern.match(title):
            return level
    return "chapter"  # nomsiz sarlavha — eng chuqur daraja deb hisoblaymiz


# DIQQAT: o'zbek va rus tillari qo'shimchali (aglyutinativ / kelishikli).
# `kodeks` → `kodeksi`, `Пленум` → `Пленума`, `qonun` → `qonunning`.
# Shuning uchun so'z oxirida `\b` emas, `\w*` ishlatiladi — aks holda
# hujjatlarning katta qismi "boshqa" deb tasniflanadi.
_DOC_TYPE_PATTERNS: list[tuple[DocType, re.Pattern[str]]] = [
    ("plenum", re.compile(r"\b(пленум\w*|plenum\w*)", re.I)),
    ("kodeks", re.compile(r"\b(кодекс\w*|kodeks\w*)", re.I)),
    (
        "PF",
        re.compile(
            r"(Президент\w*\s+фармон\w*|Prezident\w*\s+farmon\w*|\bПФ[-\s]?\d|\bPF[-\s]?\d)", re.I
        ),
    ),
    (
        "PQ",
        re.compile(
            r"(Президент\w*\s+қарор\w*|Prezident\w*\s+qaror\w*|\bПҚ[-\s]?\d|\bPQ[-\s]?\d)", re.I
        ),
    ),
    ("VMQ", re.compile(r"(Вазирлар\s+Маҳкамас\w*|Vazirlar\s+Mahkamas\w*)", re.I)),
    ("qonun", re.compile(r"\b(закон\w*|qonun\w*|қонун\w*)", re.I)),
]


def detect_doc_type(title: str) -> DocType:
    for doc_type, pattern in _DOC_TYPE_PATTERNS:
        if pattern.search(title):
            return doc_type
    return "boshqa"


# --------------------------------------------------------------------------- #
# Band segmentatsiyasi — farmon, qaror va boshqa modda tuzilmasiz hujjatlar
# --------------------------------------------------------------------------- #

# «1. Matn…» — band boshi. Nuqta majburiy, chunki raqamsiz satr boshi
# (masalan «2026-yildan boshlab…») band emas.
_POINT_START = re.compile(r"^\s*(\d{1,3})\.\s+(?=\S)")

# Bandning eng kam uzunligi. Undan qisqasi odatda jadval katagi yoki
# ro'yxat elementi bo'ladi va alohida band sifatida indekslanishi
# qidiruvni ifloslaydi.
_MIN_POINT_CHARS = 80


def segment_points(elements: list[Element]) -> list[Element]:
    """Modda tuzilmasi yo'q hujjatni **bandlar** bo'yicha bo'ladi.

    ## Nima uchun kerak

    Kodeks va qonunda «234-modda» sarlavhasi bor va parser uni CSS
    sinfi bo'yicha taniydi. Prezident farmoni va qarorida esa bunday
    sarlavha **umuman yo'q** — butun matn tekis paragraflar bo'lib
    keladi, tuzilma faqat «1.», «2.», «3.» raqamlarida.

    Amalda o'lchandi (863 hujjat, 2026-08-12): 631 tasi — ya'ni **73%** —
    nol modda bilan qaytdi. Ular indeksga tushsa ham, iqtibos bera
    olmaydigan tekis matn bo'lib qolardi va gate ularni tasdiqlay
    olmasdi.

    ## Nima uchun `level="article"`

    Chunker, gate va iqtibos mexanizmi `article_number` ga tayanadi.
    Bandni alohida daraja qilish uchalasini ham o'zgartirishni talab
    qilardi. Raqam bir xil ma'noni bajaradi — farq faqat **nomlanishda**,
    va u `unit_label()` orqali hal qilinadi: kodeksda «3-modda»,
    farmonda «3-band».

    Faqat modda topilmagan hujjatlarda ishlaydi — kodeksga tegmaydi.
    """
    if any(e.level == "article" for e in elements):
        return elements

    out: list[Element] = []
    current: Element | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current, buffer
        if current is not None:
            current.body = "\n".join(buffer).strip()
            if len(current.body) >= _MIN_POINT_CHARS:
                out.append(current)
            else:
                # Juda qisqa band — oldingi bandga qo'shiladi, aks holda
                # u alohida chunk bo'lib qidiruvni ifloslaydi.
                if out and out[-1].level == "article":
                    out[-1].body = f"{out[-1].body}\n{current.title}\n{current.body}".strip()
        current, buffer = None, []

    for element in elements:
        if element.level != "text":
            flush()
            out.append(element)
            continue

        body = element.body or ""
        match = _POINT_START.match(body)
        if match:
            flush()
            current = Element(
                element_id=element.element_id,
                level="article",
                title=body[: match.end()].strip(),
                article_number=match.group(1),
                lang=element.lang,
                path=list(element.path),
            )
            buffer = [body[match.end() :].strip()]
        elif current is not None:
            buffer.append(body)
        else:
            out.append(element)

    flush()
    return out


# «Prim» moddalar: keyinchalik kiritilgan qo'shimcha moddalar yuqori indeks
# bilan raqamlanadi — 358¹, 26², 176³. HTML da bu `<sup>` tegi:
#
#     358<sup>1</sup>-modda. Korporativ shartnoma
#
# Teglarni oddiy bo'sh joyga aylantirsak «358 1 -modda» chiqadi va modda
# raqami **1** deb ajratiladi — u haqiqiy 1-modda bilan to'qnashadi.
# Shuning uchun `<sup>` avval kanonik `-N` shakliga o'giriladi: `358-1`.
_SUPERSCRIPT = re.compile(r"<sup>\s*(\d{1,2})\s*</sup>", re.IGNORECASE)


def clean_text(fragment: str) -> str:
    fragment = _SCRIPT_STYLE.sub(" ", fragment)
    fragment = _SUPERSCRIPT.sub(r"-\1", fragment)
    fragment = fragment.replace("<br />", "\n").replace("<br/>", "\n").replace("<br>", "\n")
    fragment = _TAG.sub(" ", fragment)
    fragment = html_lib.unescape(fragment)
    fragment = _UI_NOISE.sub(" ", fragment)
    fragment = re.sub(r"[ \t]+", " ", fragment)
    return re.sub(r"\n\s*\n+", "\n", fragment).strip()


def title_tag_parts(html: str) -> tuple[str, str]:
    """`<title>` tegini `(prefiks, hujjat nomi)` juftligiga ajratadi.

    Prefiks — raqam va sana (`OʻRQ-982-сон 25.10.2024.`), nom esa
    hujjatning o'zi. Ajratuvchi — uzilmas bo'sh joy (`NBSP` izohiga
    qarang). Teg yo'q yoki ajratuvchi topilmasa `("", "")` qaytadi:
    bunday sahifada taxmin qilinmaydi (docs/22 § 1.6 — aniqlik
    qamrovdan muhimroq).
    """
    m = _TITLE_TAG.search(html)
    if m is None:
        return "", ""
    segments = [part.strip() for part in html_lib.unescape(m.group(1)).split(NBSP) if part.strip()]
    if len(segments) < 2:
        return "", ""
    return segments[0], " ".join(segments[1:])


def title_tag_date(html: str) -> str | None:
    """`<title>` prefiksidagi qabul sanasi (`YYYY-MM-DD`) yoki `None`.

    Sana **faqat prefiksdan** olinadi. Butun sarlavhaga `extract_date()`
    qo'llansa, nom ichidagi «2020-yil 22-iyundagi» kabi boshqa hujjatga
    tegishli havola ustun chiqadi va sana noto'g'ri bo'lardi — 863
    xom fayldan 15 tasida aynan shunday bo'lgan bo'lardi.
    """
    prefix, _name = title_tag_parts(html)
    return extract_date(prefix) if prefix else None


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #


class LexUzParser:
    source = "lex.uz"

    def can_parse(self, raw: RawDocument) -> bool:
        return raw.source == self.source or "lex.uz" in raw.url

    def parse(self, raw: RawDocument) -> ParsedDocument:
        html = raw.content
        warnings: list[str] = []

        blocks = self._walk(html)
        if not blocks:
            warnings.append("Hech qanday lx_elem bloki topilmadi — sahifa formati o'zgargan?")

        sample = " ".join(text for _, _, text in blocks[:60])
        lang = "ru" if looks_russian(sample) else "uz"

        title, adopted_at = self._document_title(html, blocks)
        amendments: list[AmendmentNote] = []
        elements = self._build(blocks, lang, warnings, amendments)
        # Modda tuzilmasi topilmasa — bandlar bo'yicha bo'lamiz. Farmon va
        # qarorlarda «N-modda» sarlavhasi umuman yo'q, tuzilma faqat
        # «1.», «2.» raqamlarida (`segment_points` izohiga qarang).
        elements = segment_points(elements)
        self._cross_check(html, blocks, warnings)

        return ParsedDocument(
            doc_id=raw.doc_id,
            source=raw.source,
            url=raw.url,
            title=title,
            doc_type=detect_doc_type(title),
            lang=lang,  # type: ignore[arg-type]
            adopted_at=adopted_at,
            elements=elements,
            amendments=amendments,
            warnings=warnings,
        )

    # ------------------------------------------------------------------ #

    def _walk(self, html: str) -> list[tuple[str, str, str]]:
        """Hujjatni tartib bo'yicha (klass, element_id, matn) ro'yxatiga aylantiradi.

        Har bir kontent divini undan oldingi eng yaqin o'rovchi bilan
        juftlashtiramiz — HTML da o'rovchi har doim kontentdan oldin keladi.
        """
        wrappers = [(m.start(), m.group(1)) for m in _WRAPPER.finditer(html)]
        out: list[tuple[str, str, str]] = []
        wi = 0
        current = "UNKNOWN"

        for m in _CONTENT.finditer(html):
            while wi < len(wrappers) and wrappers[wi][0] < m.start():
                current = wrappers[wi][1]
                wi += 1
            text = clean_text(m.group(2))
            if text:
                out.append((current, m.group(1), text))
        return out

    def _document_title(
        self, html: str, blocks: list[tuple[str, str, str]]
    ) -> tuple[str, str | None]:
        """Hujjat sarlavhasi va qabul sanasi.

        Ikkalasi **turli manbadan** olinadi va bu ataylab:

        * sarlavha — `ACT_TITLE` blokidan, u toza hujjat nomi;
        * sana — `<title>` tegining prefiksidan, u boshqa joyda yo'q.

        Sarlavhaga raqam va sana prefiksi **qo'shilmaydi**:
        `linking.py` dagi `_code_registry()` kodekslarni sarlavha
        bo'yicha indekslaydi, prefiks esa `refs.jsonl` tarkibini
        siljitardi (docs/22 § 1.3).
        """
        prefix, name = title_tag_parts(html)
        title = ""
        for cls, _eid, text in blocks:
            if cls in TITLE_CLASSES and len(text) > 10:
                title = canonical(text.replace("\n", " "))
                break
        if not title and name:
            # `ACT_TITLE` bloki yo'q (863 fayldan 2 tasida) — `<title>`
            # tegining **nom** qismi olinadi, prefiks emas.
            title = canonical(clean_text(name).replace("\n", " "))
        if not title:
            m = _TITLE_TAG.search(html)
            if m:
                title = canonical(clean_text(m.group(1)).replace("\n", " "))

        # Prefiks bo'lsa — sana faqat undan. Prefikssiz sahifada eski
        # xulq saqlanadi: sarlavhaning o'zidan qidiriladi.
        adopted_at = extract_date(prefix) if prefix else extract_date(title)
        return title or "(sarlavhasiz)", adopted_at

    def _build(
        self,
        blocks: list[tuple[str, str, str]],
        lang: str,
        warnings: list[str],
        amendments: list[AmendmentNote],
    ) -> list[Element]:
        elements: list[Element] = []
        path: dict[str, str] = {}
        current_article: Element | None = None
        body_parts: list[str] = []
        translit = lang == "uz"

        def flush() -> None:
            nonlocal current_article, body_parts
            if current_article is not None:
                current_article.body = canonical("\n".join(body_parts), transliterate=translit)
                elements.append(current_article)
            current_article = None
            body_parts = []

        for cls, element_id, text in blocks:
            flat = text.replace("\n", " ").strip()

            if cls in TITLE_CLASSES:
                continue

            if cls in HEADER_CLASSES:
                # Bob sarlavhasi o'rnida tahrir izohi kelishi mumkin —
                # u ierarxiya yo'liga tushmasligi kerak.
                if is_amendment_note(flat):
                    note = parse_amendment(element_id, flat)
                    amendments.append(note)
                    continue

                flush()
                level = detect_header_level(flat)
                path[level] = flat
                for deeper in _LEVEL_ORDER[_LEVEL_ORDER.index(level) + 1 :]:
                    path.pop(deeper, None)
                elements.append(
                    Element(
                        element_id=element_id,
                        level=level,  # type: ignore[arg-type]
                        title=canonical(flat, transliterate=translit),
                        lang=lang,  # type: ignore[arg-type]
                        path=[path[k] for k in _LEVEL_ORDER if k in path and path[k] != flat],
                    )
                )
                continue

            if cls in ARTICLE_CLASSES:
                # O'zgartirish eslatmalari ham CLAUSE_DEFAULT bilan keladi,
                # lekin ular modda emas — versiya metama'lumoti.
                if is_amendment_note(flat):
                    note = parse_amendment(element_id, flat)
                    amendments.append(note)
                    if current_article is not None:
                        current_article.amendments.append(note)
                    continue

                flush()
                number = extract_article_number(flat)
                if number is None:
                    warnings.append(f"Modda raqami ajratilmadi: {flat[:60]!r}")
                current_article = Element(
                    element_id=element_id,
                    level="article",
                    title=canonical(flat, transliterate=translit),
                    article_number=number,
                    lang=lang,  # type: ignore[arg-type]
                    path=[path[k] for k in _LEVEL_ORDER if k in path],
                )
                continue

            if cls in BODY_CLASSES:
                if current_article is not None:
                    body_parts.append(text)
                else:
                    # Modda tashqarisidagi matn (muqaddima, ilova)
                    elements.append(
                        Element(
                            element_id=element_id,
                            level="text",
                            title="",
                            body=canonical(text, transliterate=translit),
                            lang=lang,  # type: ignore[arg-type]
                            path=[path[k] for k in _LEVEL_ORDER if k in path],
                        )
                    )

        flush()
        return elements

    def _cross_check(
        self, html: str, blocks: list[tuple[str, str, str]], warnings: list[str]
    ) -> None:
        """TOC ni tekshiruv sifatida ishlatamiz (parsing uchun emas)."""
        toc_ids = set(_TOC_ENTRY.findall(html))
        if not toc_ids:
            return
        body_ids = {eid for _, eid, _ in blocks}
        missing = toc_ids - body_ids
        if missing:
            warnings.append(
                f"TOC da {len(missing)} ta element tanada topilmadi (masalan {sorted(missing)[:3]})"
            )
