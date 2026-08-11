"""Groundedness gate — javob foydalanuvchiga yetishidan oldingi oxirgi to'siq.

## Tamoyil

Gate javobni **yaxshilamaydi** — u faqat **olib tashlaydi** (docs/01 § 6).
Bu ataylab: gate yangi matn generatsiya qilsa, uning o'zi hallucination
manbaiga aylanardi va tekshiruvchi tekshiriladigan narsaga aylanardi.

Shuning uchun gate deterministik: model emas, qoidalar to'plami.

## Uch bosqich

Har bir da'vo (gap) uchun ketma-ket:

1. **Iqtibos bormi?** Yo'q bo'lsa — da'vo turi hal qiladi. Huquqiy da'vo
   («…moddasiga ko'ra javobgarlik yuzaga keladi») o'chiriladi; umumiy yoki
   mantiqiy gap («Quyidagi hujjatlar kerak bo'ladi») qoladi.

2. **Iqtibos haqiqiymi?** `[C7]` kontekstda yo'q bo'lsa — o'chiriladi.
   Model belgi o'ylab topishi eng ko'p uchraydigan xato turi.

3. **Iqtibos matni da'voni qo'llab-quvvatlaydimi?** Leksik qoplama
   hisoblanadi: da'vodagi ma'noli so'zlar iqtibos matnida uchraydimi.
   Past bo'lsa da'vo o'chirilmaydi, **«noaniq» deb belgilanadi** — chunki
   bu bosqich xato qilishi mumkin va to'g'ri da'voni o'chirish
   noto'g'risini qoldirishdan ko'ra qimmatroq.

## Nima uchun NLI modeli emas

docs/01 § 6 uchinchi bosqich uchun NLI yoki qisqa model chaqiruvini
taklif qiladi. Bu amalga oshirishda leksik qoplama ishlatiladi, sabab:

* Har bir da'vo uchun model chaqiruvi kechikishni ikki baravar oshiradi
* O'zbek tili uchun tayyor NLI modeli yo'q
* Gate ning **birinchi ikki bosqichi** xatolarning katta qismini tutadi;
  uchinchisi faqat belgilaydi, o'chirmaydi

Model asosidagi tekshiruv `verifier=` orqali ulanishi mumkin — shartnoma
tayyor, amalga oshirish keyingi bosqichda o'lchov bilan qo'shiladi.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

from uzlegal.ingest.normalize import fold
from uzlegal.types import Citation, GateReport

log = logging.getLogger(__name__)

# Da'vo huquqiy ekanini ko'rsatuvchi belgilar. Bular topilsa iqtibos
# **majburiy** bo'ladi.
_LEGAL_MARKERS = re.compile(
    r"\b(modda|kodeks|qonun|norma|band|qism|farmon|qaror|nizom|"
    r"javobgar|majbur|huquq|muddat|jarima|jazo|sud|shartnoma|"
    r"taqiqla|ruxsat|belgila|nazarda tutil)",
    re.IGNORECASE,
)

# Sarlavha satri — da'vo emas, struktura. Gate ularni tegmasdan o'tkazadi.
_HEADING = re.compile(r"^[A-ZЎҚҒҲ'ʻʼ \-]{3,40}$")

_CITE = re.compile(r"\[\s*(C\d{1,3})\s*\]", re.IGNORECASE)

# Gap chegarasi. Qisqartmalardan keyin bo'linmaslik uchun raqamli nuqta
# («1. Birinchi») hisobga olinadi.
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZЎҚҒҲ0-9])")

# Ma'no tashimaydigan so'zlar — qoplama hisobida hisobga olinmaydi.
# `fold()` qilingan shaklda yoziladi, chunki taqqoslash ham shu shaklda.
_STOPWORDS = frozenset(
    [
        "va",
        "yoki",
        "ammo",
        "lekin",
        "bilan",
        "uchun",
        "ham",
        "bu",
        "shu",
        "ular",
        "biz",
        "siz",
        "men",
        "bolgan",
        "bolsa",
        "boladi",
        "qilish",
        "qiladi",
        "qilingan",
        "kerak",
        "mumkin",
        "agar",
        "shuning",
        "yani",
        "hamda",
        "hisoblanadi",
        "deb",
        "ushbu",
        "mazkur",
        "har",
        "bir",
        "barcha",
        "faqat",
        "keyin",
        "oldin",
        "ichida",
    ]
)

# Da'vo qo'llab-quvvatlangan deb hisoblanishi uchun kerakli leksik qoplama.
# 0.25 past ko'rinadi, lekin ataylab: da'vo iqtibosni **qayta ifodalaydi**,
# nusxa ko'chirmaydi — yuqori chegara to'g'ri da'volarni belgilab tashlardi.
SUPPORT_THRESHOLD = 0.25

MIN_CLAIM_CHARS = 12

Verifier = Callable[[str, list[Citation]], bool]


def split_claims(text: str) -> list[str]:
    """Javobni da'volarga ajratadi.

    Ajratish satr va gap chegarasi bo'yicha. Sudya javobi strukturali
    yoziladi (`Verdict.as_answer`), shuning uchun bir satr odatda bitta
    da'vo bo'ladi — bu tekshiruvni aniqroq qiladi.
    """
    claims: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _HEADING.match(line.rstrip(":")):
            claims.append(line)  # sarlavha — o'zgarishsiz o'tadi
            continue
        line = re.sub(r"^\s*(?:[-*•–—]|\d{1,2}[.)])\s+", "", line).strip()
        for piece in _SENTENCE.split(line):
            piece = piece.strip()
            if piece:
                claims.append(piece)
    return claims


def is_heading(claim: str) -> bool:
    return bool(_HEADING.match(claim.rstrip(":")))


def is_legal_claim(claim: str) -> bool:
    """Da'vo huquqiy normaga tayanadimi.

    Huquqiy bo'lsa iqtibos majburiy. Umumiy gap («Bu holatda ikki yo'l
    bor») iqtibossiz ham qolishi mumkin — u norma haqida hech narsa
    da'vo qilmaydi.
    """
    return bool(_LEGAL_MARKERS.search(claim))


def cited_tags(claim: str) -> list[str]:
    return [m.group(1).upper() for m in _CITE.finditer(claim)]


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[a-zʻʼ0-9]{4,}", fold(text))
    return {w for w in words if w not in _STOPWORDS}


def support_score(claim: str, citations: list[Citation]) -> float:
    """Da'vodagi ma'noli so'zlarning iqtibos matnida uchrash ulushi.

    Iqtibos matni bo'lmasa `1.0` qaytadi — bu bosqich matn mavjud
    bo'lgandagina tekshiradi, aks holda barcha da'volarni sababsiz
    belgilab tashlardi.
    """
    source = " ".join(c.excerpt or "" for c in citations).strip()
    if not source:
        return 1.0
    claim_words = _content_words(claim)
    if not claim_words:
        return 1.0
    return len(claim_words & _content_words(source)) / len(claim_words)


class GroundednessGate:
    """Iqtibossiz huquqiy da'voni javobdan chiqaradi."""

    def __init__(
        self,
        citations: list[Citation],
        *,
        threshold: float = SUPPORT_THRESHOLD,
        verifier: Verifier | None = None,
    ) -> None:
        self.citations = citations
        self.index = {c.tag.upper(): c for c in citations}
        self.threshold = threshold
        self.verifier = verifier

    # ------------------------------------------------------------------ #

    def check(self, answer: str) -> tuple[str, GateReport]:
        """`(tozalangan_javob, hisobot)`.

        Javob qayta yig'iladi: o'chirilgan da'volar tushib qoladi,
        «noaniq» belgilanganlar esa ⚠ bilan qoladi. Hech qanday yangi
        matn qo'shilmaydi.
        """
        report = GateReport()
        kept_lines: list[str] = []

        for claim in split_claims(answer):
            if is_heading(claim):
                kept_lines.append(claim)
                continue
            if len(claim) < MIN_CLAIM_CHARS:
                kept_lines.append(claim)
                continue

            verdict, rendered = self._judge(claim)
            if verdict == "drop":
                report.dropped.append(claim)
                continue
            if verdict == "flag":
                report.flagged.append(claim)
            else:
                report.kept.append(claim)
            kept_lines.append(rendered)

        report.citations = self._used(report.kept + report.flagged)
        return self._reassemble(kept_lines), report

    # ------------------------------------------------------------------ #

    def _judge(self, claim: str) -> tuple[str, str]:
        tags = cited_tags(claim)
        resolved = [self.index[t] for t in tags if t in self.index]
        unknown = [t for t in tags if t not in self.index]

        # 1-bosqich: iqtibos yo'q
        if not tags:
            if is_legal_claim(claim):
                log.debug("Gate o'chirdi (iqtibossiz huquqiy da'vo): %s", claim[:70])
                return "drop", claim
            return "keep", claim

        # 2-bosqich: o'ylab topilgan belgi. Belgilarning **hammasi**
        # noto'g'ri bo'lsa da'voning asosi yo'q — o'chiriladi. Bir qismi
        # to'g'ri bo'lsa yolg'on belgi olib tashlanadi va da'vo qoladi.
        if unknown and not resolved:
            log.debug("Gate o'chirdi (mavjud bo'lmagan iqtibos %s): %s", unknown, claim[:70])
            return "drop", claim
        cleaned = claim
        for tag in unknown:
            cleaned = re.sub(rf"\[\s*{tag}\s*\]", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

        # 3-bosqich: iqtibos da'voni qo'llab-quvvatlaydimi
        if self.verifier is not None:
            supported = self.verifier(cleaned, resolved)
        else:
            supported = support_score(cleaned, resolved) >= self.threshold
        if not supported:
            return "flag", f"⚠ {cleaned}"
        return "keep", cleaned

    def _used(self, claims: list[str]) -> list[Citation]:
        """Yakuniy javobda haqiqatan qolgan iqtiboslar.

        Bu muhim: javobdan da'vo o'chirilsa, uning manbasi ham manbalar
        ro'yxatidan tushishi kerak — aks holda foydalanuvchi javobda
        ishlatilmagan normani ko'radi.
        """
        used: list[Citation] = []
        seen: set[str] = set()
        for claim in claims:
            for tag in cited_tags(claim):
                citation = self.index.get(tag)
                if citation is not None and tag not in seen:
                    seen.add(tag)
                    used.append(citation)
        return used

    @staticmethod
    def _reassemble(lines: list[str]) -> str:
        """Satrlarni qayta yig'adi, bo'sh sarlavhalarni tashlaydi."""
        out: list[str] = []
        for i, line in enumerate(lines):
            if is_heading(line.rstrip(":")):
                following = lines[i + 1 :]
                nxt = next((x for x in following if x.strip()), None)
                if nxt is None or is_heading(nxt.rstrip(":")):
                    continue  # sarlavha ostidagi hamma da'vo o'chirilgan
                if out:
                    out.append("")
            out.append(line)
        return "\n".join(out).strip()


REFUSAL = (
    "Ishonchli javob shakllantirilmadi.\n\n"
    "Topilgan manbalar savolga to'g'ridan-to'g'ri javob bermadi yoki "
    "javobdagi da'volar manbaga bog'lanmadi. Quyidagi normalar ko'rib "
    "chiqildi — ular bilan tanishib chiqishingiz mumkin."
)
