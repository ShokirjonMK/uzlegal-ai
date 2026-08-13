"""PII anonimizatsiya — docs/03 § 3.7.

Sud qarorlarida shaxsiy ma'lumot bo'ladi va u **indekslashdan oldin** olib
tashlanadi. Hozirgi korpusda (lex.uz normativ hujjatlari) sud qarorlari yo'q,
lekin `public.sud.uz` P1 manba sifatida rejalashtirilgan — modul o'sha
paytgacha tayyor turadi va validatsiya uni hoziroq detektor sifatida
ishlatadi.

## Jadval (docs/03 § 3.7)

| Ma'lumot | Natija |
|----------|--------|
| F.I.Sh. | `[SHAXS-1]`, `[SHAXS-2]` — izchil |
| Passport, JSHSHIR, STIR | `[HUJJAT]` |
| Manzil (ko'cha, uy) | `[MANZIL]` — shahar/viloyat **qoladi** |
| Telefon, email | `[ALOQA]` |
| Bank hisobi, karta | `[HISOB]` |
| Tug'ilgan sana | `[SANA]` |
| Yuridik shaxs nomi | **qoladi** — ochiq ma'lumot |
| Sudya, prokuror ismi | **qoladi** — rasmiy rol |

## Nima uchun «qoladi» ustuni muhimroq

Ortiqcha o'chirish ham xato: «“Oltin Vodiy” MChJ» yoki sudya ismi o'chirilsa
qaror o'z yuridik ma'nosini yo'qotadi va iqtibos tekshirib bo'lmaydigan
bo'ladi. Shuning uchun har bir nomzod avval **saqlash qoidalari** dan
o'tkaziladi: rasmiy rol, tirnoq ichidagi nom, tashkiliy-huquqiy shakl.

## Izchillik

Bir qarordagi bir shaxs har doim bir xil raqam oladi, aks holda matn
o'qib bo'lmaydigan holga keladi («[SHAXS-1] [SHAXS-2] ga qarshi» —
ikkalasi ham bitta odam bo'lsa). Kalit sifatida **familiya** olinadi:
«Karimov Alisher Baxtiyorovich» va keyinroq «Karimov A.B.» bir shaxs.
Bir qarorda bir xil familiyali ikki shaxs bo'lsa — karantin bayrog'i.

## Ishonch va karantin

Qoida asosidagi detektor barcha holatni qoplay olmaydi (docs/03: qoida + NER
birlashmasi). Shuning uchun har bir topilma `confidence` bilan keladi va
past ishonchli holat topilsa hujjat **karantinga** belgilanadi — u
indekslanmaydi, qo'lda ko'rib chiqiladi.
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

PERSON = "SHAXS"
DOCUMENT = "[HUJJAT]"
CONTACT = "[ALOQA]"
ACCOUNT = "[HISOB]"
ADDRESS = "[MANZIL]"
BIRTHDATE = "[SANA]"

# Past ishonchli topilma bo'lsa hujjat karantinga tushadi
QUARANTINE_BELOW = 0.75

_UPPER = r"A-ZА-ЯЁЎҚҒҲ"
_WORD = r"[\w’ʻʼ'-]"

# --------------------------------------------------------------------------- #
# Saqlanadigan kontekst
# --------------------------------------------------------------------------- #

# Rasmiy rol — ism qoladi (docs/03 § 3.7)
_OFFICIAL_ROLE = re.compile(
    r"(sudya|sud\s+raisi|raislik\s+qiluvchi|prokuror|hakam|tergovchi|"
    r"судья|прокурор|следовател)\w*\s*$",
    re.IGNORECASE,
)

# Tashkiliy-huquqiy shakl — yuridik shaxs nomi qoladi
_LEGAL_ENTITY = re.compile(
    r"^\s*(MChJ|AJ|OAJ|YoAJ|XK|QK|YaTT|DUK|AT|МЧЖ|АЖ|ООО|АО)\b",
    re.IGNORECASE,
)
_ENTITY_BEFORE = re.compile(
    r"(MChJ|AJ|OAJ|XK|QK|YaTT|bank\w*|korxona\w*|tashkilot\w*|idora\w*)\s*$",
    re.IGNORECASE,
)

# Davlat organi va tashkilot nomi — «Oʻzbekiston Respublikasi», «Vazirlar
# Mahkamasi». Bular ikki so'zli nomzod shabloniga to'liq mos keladi va
# normativ matnda shaxs konteksti yonida turadi («chet el fuqarosi
# Oʻzbekiston Respublikasida…»). O'lchangan: 20 kodeksda 34 ta yolg'on
# topilmaning 32 tasi shu sabab edi.
_ORGANISATION = re.compile(
    r"\b(respublika|mahkama|majlis|vazirlik|vazirlar|qo[’'ʻ]mita|kengash|bank|"
    r"sud\w*|prokuratura|inspeksiya|idora|markaz|palata|hokimiyat|hokimlik|"
    r"departament|agentlik|xizmat|nazorat|federatsiya|davlat)\w*",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------- #
# Detektorlar
# --------------------------------------------------------------------------- #


class Redaction(BaseModel):
    """Bitta anonimizatsiya qilingan bo'lak."""

    start: int
    end: int
    original: str
    placeholder: str
    category: str
    confidence: float = 1.0


class RedactionResult(BaseModel):
    text: str
    redactions: list[Redaction] = Field(default_factory=list)
    persons: dict[str, str] = Field(
        default_factory=dict, description="familiya (kalit) → `[SHAXS-N]`"
    )
    quarantine: bool = False
    reasons: list[str] = Field(default_factory=list)

    @property
    def confidence(self) -> float:
        if not self.redactions:
            return 1.0
        return min(r.confidence for r in self.redactions)

    def count(self, category: str) -> int:
        return sum(1 for r in self.redactions if r.category == category)


# Passport: AA 1234567 · JSHSHIR/PINFL: 14 raqam · STIR: 9 raqam
_ID_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    ("passport", re.compile(r"\b[A-ZА-Я]{2}\s?\d{7}\b"), 0.95),
    ("jshshir", re.compile(r"\b\d{14}\b"), 0.95),
    (
        "stir",
        re.compile(r"\b(?:STIR|INN|ИНН)\W{0,3}(\d{9})\b", re.IGNORECASE),
        0.95,
    ),
]

_ACCOUNT_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    ("hisob", re.compile(r"\b\d{20}\b"), 0.95),
    ("karta", re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), 0.9),
]

_CONTACT_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b"), 0.98),
    ("telefon", re.compile(r"\+?998[\s()-]?\d{2}[\s()-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}\b"), 0.95),
    ("telefon", re.compile(r"\b\d{2}-\d{3}-\d{2}-\d{2}\b"), 0.85),
]

# «Amir Temur koʻchasi, 12-uy», «Chilonzor tumani, 5-mavze, 3-uy, 15-xonadon».
# Shahar va viloyat **ataylab** qoldiriladi — yurisdiksiya huquqiy ahamiyatga ega.
_ADDRESS_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    (
        "kocha",
        re.compile(
            rf"\b(?:{_WORD}+\s+){{0,3}}(?:ko[’'ʻ]chasi|mahallasi|shoh\s+ko[’'ʻ]chasi|"
            rf"улица|ул\.)\s*,?\s*\d*[-\s]?(?:uy|дом)?\b",
            re.IGNORECASE,
        ),
        0.85,
    ),
    ("uy", re.compile(r"\b\d{1,4}[-\s]?(?:uy|xonadon|kvartira|дом|кв)\b", re.IGNORECASE), 0.8),
]

# «1985-yil 12-mayda tugʻilgan», «12.05.1985 yilda tugʻilgan»
_BIRTH_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    (
        "tugilgan",
        re.compile(
            r"\b(\d{4}[-\s]?yil\w*\s+\d{1,2}[-\s]?\w+|\d{1,2}\.\d{2}\.\d{4})"
            r"(?=\w*\s+(?:yilda\s+)?tu[gʻ’']{1,2}ilgan)",
            re.IGNORECASE,
        ),
        0.9,
    ),
]

# To'liq F.I.Sh.: «Karimov Alisher Baxtiyorovich»
_FULL_NAME = re.compile(
    rf"\b([{_UPPER}]{_WORD}+)\s+([{_UPPER}]{_WORD}+)\s+"
    rf"([{_UPPER}]?{_WORD}*(?:ovich|evich|ovna|evna|o[’'ʻ]g[’'ʻ]li|qizi|ович|евич|овна|евна))\b"
)

# «Yusupova Nodira Anvar qizi» — otasining ismi alohida so'z bilan keladi.
# Bu shakl uch so'zli shablondan **oldin** sinaladi, aks holda familiya
# («Yusupova») almashtirishdan tashqarida qolib ketadi.
_FULL_NAME_KIN = re.compile(
    rf"\b([{_UPPER}]{_WORD}+)\s+([{_UPPER}]{_WORD}+)\s+([{_UPPER}]{_WORD}+)\s+"
    rf"(?:o[’'ʻ]g[’'ʻ]li|qizi)\b"
)

# Familiya + initsiallar: «Karimov A.B.» yoki «A.B. Karimov»
_NAME_INITIALS = re.compile(rf"\b([{_UPPER}]{_WORD}+)\s+([{_UPPER}]\.\s?[{_UPPER}]?\.?)(?!\w)")
_INITIALS_NAME = re.compile(rf"\b([{_UPPER}]\.\s?[{_UPPER}]?\.)\s*([{_UPPER}]{_WORD}+)\b")

# Oʻzbek familiya qoʻshimchalari — juda ajratuvchi belgi.
#
# NEGA BU KERAK. Yuqoridagi shablonlar SUD HUJJATI shakllari uchun
# qurilgan: «Karimov A.A.», «Karimov Alisher Baxtiyorovich». Amalda
# oʻlchandi: foydalanuvchi savoli boshqacha yoziladi —
# «Alisher Karimovni ishdan boʻshatish mumkinmi?» — va u
# **maskalanmasdan** qolardi.
#
# Audit jurnali uchun bu jiddiy: jurnalda haqiqiy ism qoladi.
#
# Familiya qoʻshimchalari (`-ov`, `-yeva`, `-zoda` …) bosh harf bilan
# birga kelganda notoʻgʻri ishlash ehtimoli past: yuridik atamalar va
# joy nomlari bunday shaklda uchramaydi.
_SURNAME_SUFFIX = r"(?:ova|ov|yeva|yev|eva|ev|zoda|ова|ов|ева|ев|заде)"

# Familiyadan keyin kelishik qoʻshimchasi: «Karimovni», «Yusupovaga».
#
# NEGA ANIQ ROʻYXAT, `\w*` EMAS. Birinchi urinishda erkin `\w*`
# yozilgan edi va u OTASINING ISMINI familiya deb olardi:
# «Anvarovich» = «Anvar» + «ov» + «ich». Natijada «Sudya Rahimov
# Bahodir Anvarovich» dan «Bahodir Anvarovich» qismi maskalanardi —
# holbuki rasmiy rol ismlari ATAYLAB saqlanadi (sud qarorida sudya
# kim ekani yashirilmaydi).
_CASE_SUFFIX = r"(?:ning|niki|dan|ga|ni|da|si|i)?"

# «Alisher Karimov», «Alisher Karimovni», «Nodira Yusupovaga».
#
# Familiya IKKINCHI soʻzda: oʻzbek tilida savol «Ism Familiya»
# tartibida yoziladi. Sud hujjatidagi «Familiya Ism» tartibi
# yuqoridagi `_FULL_NAME` bilan qamrab olingan.
_NAME_SURNAME = re.compile(
    rf"\b([{_UPPER}]{_WORD}+)\s+"
    rf"([{_UPPER}]{_WORD}*?{_SURNAME_SUFFIX}{_CASE_SUFFIX})\b"
)

# Ikki so'zli nomzod — past ishonch, faqat shaxs konteksti bo'lsa
_PERSON_CONTEXT = re.compile(
    r"(fuqaro|da[’'ʼ]vogar|javobgar|ariza\s+beruvchi|jabrlanuvchi|sudlanuvchi|"
    r"guvoh|vakil|merosxo[’'ʻ]r|гражданин|истец|ответчик)\w*\s*$",
    re.IGNORECASE,
)
# Kesishuvchi nomzodlar kerak: «Guvoh Nodira Yusupova» da oddiy qidiruv
# «Guvoh Nodira» ni yeb qo'yadi va haqiqiy ism ko'rinmay qoladi. Shuning
# uchun lookahead — barcha ikki so'zli birikmalar ko'riladi.
_BARE_NAME = re.compile(rf"(?=(\b[{_UPPER}]{_WORD}+\s+[{_UPPER}]{_WORD}+\b))")


def _protected(text: str, start: int, end: int) -> bool:
    """Topilma saqlanishi kerakmi (rasmiy rol, yuridik shaxs, tirnoq ichi)."""
    before = text[max(0, start - 40) : start]
    after = text[end : end + 12]
    if _ORGANISATION.search(text[start:end]):
        return True
    if _OFFICIAL_ROLE.search(before) or _ENTITY_BEFORE.search(before):
        return True
    if _LEGAL_ENTITY.match(after):
        return True
    # Tirnoq ichidagi nom — «Oltin Vodiy» kabi brend
    opening = before.rfind("«")
    return opening != -1 and "»" not in before[opening:]


# --------------------------------------------------------------------------- #
# Redactor
# --------------------------------------------------------------------------- #


class Redactor:
    """Qoida asosidagi PII anonimizatori.

    Bir nusxa bir **hujjat** uchun ishlatiladi: shaxs raqamlari shu nusxa
    ichida izchil bo'ladi. Hujjatlar orasida raqam takrorlanishi normal —
    ular boshqa-boshqa ishlar.
    """

    def __init__(self, *, quarantine_below: float = QUARANTINE_BELOW) -> None:
        self.quarantine_below = quarantine_below
        self._persons: dict[str, str] = {}
        self._full_names: dict[str, set[str]] = {}

    def reset(self) -> None:
        self._persons.clear()
        self._full_names.clear()

    # ------------------------------------------------------------------ #

    def detect(self, text: str) -> list[Redaction]:
        """Matnni o'zgartirmasdan PII topadi (validatsiya shu funksiyani chaqiradi)."""
        found: list[Redaction] = []

        for group, placeholder in (
            (_CONTACT_PATTERNS, CONTACT),
            (_ID_PATTERNS, DOCUMENT),
            (_ACCOUNT_PATTERNS, ACCOUNT),
            (_BIRTH_PATTERNS, BIRTHDATE),
            (_ADDRESS_PATTERNS, ADDRESS),
        ):
            for category, pattern, confidence in group:
                for m in pattern.finditer(text):
                    found.append(
                        Redaction(
                            start=m.start(),
                            end=m.end(),
                            original=m.group(0),
                            placeholder=placeholder,
                            category=category,
                            confidence=confidence,
                        )
                    )

        found += self._detect_persons(text)
        resolved = _resolve_overlaps(found)

        # Yorliq raqamlari **hujjat tartibida** beriladi va faqat saqlanib
        # qolgan topilmalar hisobga olinadi: kesishuvda tashlab yuborilgan
        # nomzod raqam olsa, [SHAXS-N] ketma-ketligi uzilib qolardi.
        for r in resolved:
            if r.category in _PERSON_CATEGORIES:
                r.placeholder = self._person_tag(_surname_of(r.category, r.original), r.original)
        return resolved

    def _detect_persons(self, text: str) -> list[Redaction]:
        out: list[Redaction] = []

        for pattern, category, confidence in (
            (_FULL_NAME_KIN, "fish", 0.95),
            (_FULL_NAME, "fish", 0.95),
            (_NAME_INITIALS, "fish_initsial", 0.85),
            (_INITIALS_NAME, "initsial_fish", 0.85),
            (_NAME_SURNAME, "ism_familiya", 0.85),
            (_BARE_NAME, "nomzod", 0.55),
        ):
            for m in pattern.finditer(text):
                bare = category == "nomzod"
                start, end = m.span(1) if bare else m.span(0)
                original = m.group(1) if bare else m.group(0)
                if _protected(text, start, end):
                    continue
                # «Prokuror Ergashev» — rol soʻzi ISM oʻrnida qolib
                # ketmasin. `_protected()` faqat topilmadan OLDINGI
                # matnni koʻradi, bu yerda esa rol topilmaning ICHIDA.
                if category == "ism_familiya" and _OFFICIAL_ROLE.search(m.group(1) + " "):
                    continue
                if bare and not _PERSON_CONTEXT.search(text[max(0, start - 30) : start]):
                    continue
                out.append(
                    Redaction(
                        start=start,
                        end=end,
                        original=original,
                        placeholder="",  # yorliq tartib aniqlangach beriladi
                        category=category,
                        confidence=confidence,
                    )
                )
        return out

    def _person_tag(self, surname: str, full: str) -> str:
        """Familiya bo'yicha izchil yorliq beradi."""
        key = surname.casefold()
        if key not in self._persons:
            self._persons[key] = f"[{PERSON}-{len(self._persons) + 1}]"
        self._full_names.setdefault(key, set()).add(full)
        return self._persons[key]

    # ------------------------------------------------------------------ #

    def redact(self, text: str) -> RedactionResult:
        """Matnni anonimizatsiya qiladi."""
        redactions = self.detect(text)

        pieces: list[str] = []
        cursor = 0
        for r in redactions:
            pieces.append(text[cursor : r.start])
            pieces.append(r.placeholder)
            cursor = r.end
        pieces.append(text[cursor:])

        result = RedactionResult(
            text="".join(pieces),
            redactions=redactions,
            persons=dict(self._persons),
        )
        self._flag(result)
        return result

    def _flag(self, result: RedactionResult) -> None:
        """Karantin sabablarini yig'adi.

        Karantin — «shubha bor» degani, «PII bor» degani emas: aniq
        topilgan PII allaqachon almashtirilgan. Bu yerda **qolib ketgan**
        bo'lishi mumkin bo'lgan narsa qidiriladi.
        """
        low = [r for r in result.redactions if r.confidence < self.quarantine_below]
        if low:
            result.reasons.append(
                f"{len(low)} ta past ishonchli topilma (masalan {low[0].original!r})"
            )

        leftovers = re.findall(r"\b\d{7,}\b", result.text)
        if leftovers:
            result.reasons.append(f"almashtirilmagan uzun raqam: {leftovers[:3]}")

        for key, variants in self._full_names.items():
            surnames = {v.split()[0].casefold() for v in variants}
            if len(variants) > 1 and len(surnames) == 1 and _distinct_people(variants):
                result.reasons.append(f"bir familiyada bir necha shaxs: {key}")

        result.quarantine = bool(result.reasons)


_PERSON_CATEGORIES = {"fish", "fish_initsial", "initsial_fish", "ism_familiya", "nomzod"}


def _surname_of(category: str, original: str) -> str:
    """Yorliq kaliti — familiya.

    Familiya qayerda turishi shaklga bogʻliq:

        Karimov A.B.              -> boshida
        A.B. Karimov              -> oxirida
        Alisher Karimov           -> oxirida  (ism birinchi)
        Karimov Alisher B.ovich   -> boshida  (F.I.Sh. tartibi)
    """
    parts = original.split()
    if category in {"initsial_fish", "ism_familiya"}:
        return parts[-1]
    return parts[0]


def _distinct_people(variants: set[str]) -> bool:
    """Bir familiyaning turli ismlari — turli shaxs belgisi.

    «Karimov A.B.» va «Karimov Alisher Baxtiyorovich» bir odam bo'lishi
    mumkin, «Karimov Alisher …» va «Karimov Nodira …» esa yo'q.
    """
    given: set[str] = set()
    for v in variants:
        parts = v.split()
        if len(parts) >= 2 and not parts[1].endswith("."):
            given.add(parts[1].casefold()[:3])
    return len(given) > 1


def _resolve_overlaps(found: list[Redaction]) -> list[Redaction]:
    """Kesishgan topilmalarni hal qiladi: uzunroq va ishonchliroq g'olib."""
    ordered = sorted(found, key=lambda r: (r.start, -(r.end - r.start), -r.confidence))
    out: list[Redaction] = []
    for r in ordered:
        if out and r.start < out[-1].end:
            continue
        out.append(r)
    return out


def redact_text(text: str) -> RedactionResult:
    """Bir martalik anonimizatsiya (holatsiz chaqiruv uchun)."""
    return Redactor().redact(text)


def detect_pii(text: str) -> list[Redaction]:
    """Matnda PII bormi — o'zgartirmasdan tekshiradi."""
    return Redactor().detect(text)
