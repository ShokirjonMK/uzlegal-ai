"""lex.uz hujjatlarini kashf qilish — qidiruv filtrlari orqali.

## Kashfiyot API si (2026-08-09 da aniqlangan)

lex.uz qidiruvi server tomonda render qilinadi va URL parametrlari bilan
filtrlanadi:

    https://lex.uz/uz/search/nat?query=<so'z>&lang=<til>&form_id=<shakl>&status=<holat>

| Parametr | Qiymatlar |
|----------|-----------|
| `lang` | `4` = O'ZB (lotin) · `3` = ЎЗБ (kirill) · `1` = РУС · `2` = ENG |
| `form_id` | `4131` Konstitutsiya · `3964` Kodeks · `3968` Qonun · `3973` Farmon · `3972` Qaror |
| `status` | `Y` amaldagi · `R` kuchini yo'qotgan · `N` amalda emas |

`query` **majburiy** — bo'sh so'rov 302 redirect beradi.

## Muhim: til nashrlari alohida hujjatlar

O'zbek (lotin) nashrlari **manfiy ID** bilan keladi:

    Fuqarolik kodeksi (o'zbek)  →  -111189
    Гражданский кодекс (rus)    →   111181

Bu bir hujjatning ikki tarjimasi emas, ikki alohida hujjat. Loyihada
**o'zbek lotin nashri asosiy** — mahsulot o'zbek tilida javob beradi va
iqtiboslar ham o'zbekcha bo'lishi kerak.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import quote

from uzlegal.ingest.types import DocType, DocumentRef

log = logging.getLogger(__name__)

# Til kodlari
LANG_UZ_LATIN = "4"
LANG_UZ_CYRILLIC = "3"
LANG_RU = "1"
LANG_EN = "2"

# Hujjat shakllari
FORM_CONSTITUTION = "4131"
FORM_CODE = "3964"
FORM_LAW = "3968"
FORM_DECREE = "3973"  # Farmon
FORM_RESOLUTION = "3972"  # Qaror

# Holat
STATUS_IN_FORCE = "Y"
STATUS_REPEALED = "R"
STATUS_NOT_IN_FORCE = "N"

FORM_TO_DOCTYPE: dict[str, DocType] = {
    FORM_CONSTITUTION: "qonun",
    FORM_CODE: "kodeks",
    FORM_LAW: "qonun",
    FORM_DECREE: "PF",
    FORM_RESOLUTION: "PQ",
}

_RESULT_LINK = re.compile(
    r'<a class="lx_link" href="/\w{2}/docs/(-?\d+)\?query=[^"]*"[^>]*>(.*?)</a>',
    re.DOTALL,
)
_TOTAL = re.compile(r"(\d[\d\s]*)\s*(?:ta\s+)?(?:hujjat|документ)", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub("", text)).strip()


@dataclass
class DiscoveryQuery:
    query: str
    lang: str = LANG_UZ_LATIN
    form_id: str | None = FORM_CODE
    status: str = STATUS_IN_FORCE

    def url(self, base_url: str = "https://lex.uz", ui_lang: str = "uz") -> str:
        parts = [f"query={quote(self.query)}", f"lang={self.lang}", f"status={self.status}"]
        if self.form_id:
            parts.append(f"form_id={self.form_id}")
        return f"{base_url}/{ui_lang}/search/nat?" + "&".join(parts)


def parse_results(html: str, form_id: str | None = None) -> list[DocumentRef]:
    """Qidiruv sahifasidan hujjat havolalarini ajratadi."""
    doc_type: DocType = FORM_TO_DOCTYPE.get(form_id or "", "boshqa")
    seen: set[str] = set()
    out: list[DocumentRef] = []

    for doc_id, raw_title in _RESULT_LINK.findall(html):
        title = _clean(raw_title)
        if doc_id in seen or len(title) < 6:
            continue
        seen.add(doc_id)
        out.append(
            DocumentRef(
                source="lex.uz",
                doc_id=doc_id,
                url=f"https://lex.uz/uz/docs/{doc_id}",
                title=title,
                doc_type=doc_type,
            )
        )
    return out


def parse_total(html: str) -> int | None:
    m = _TOTAL.search(_TAG.sub(" ", html))
    if m:
        return int(re.sub(r"\s", "", m.group(1)))
    return None


class LexUzDiscovery:
    """Qidiruv orqali hujjatlarni topadi.

    Konnektorning `RateLimiter` ini bo'lishadi — kashfiyot ham
    `Crawl-delay: 20` ga bo'ysunadi.
    """

    def __init__(self, connector: object) -> None:
        self.connector = connector

    def search(self, query: DiscoveryQuery) -> list[DocumentRef]:
        conn = self.connector
        conn.limiter.wait()  # type: ignore[attr-defined]
        url = query.url(conn.base_url, conn.ui_lang)  # type: ignore[attr-defined]
        log.info("Kashfiyot: %s", url)

        response = conn._client.get(url)  # type: ignore[attr-defined]
        response.raise_for_status()

        refs = parse_results(response.text, query.form_id)
        total = parse_total(response.text)
        if total is not None and total > len(refs):
            log.warning(
                "Sahifada %d ta natija ko'rsatildi, lekin %d tasi ajratildi — "
                "sahifalash qo'llab-quvvatlanmaydi (hozircha)",
                total,
                len(refs),
            )
        return refs

    def discover_codes(self) -> list[DocumentRef]:
        """Barcha amaldagi kodekslarni o'zbek (lotin) tilida topadi."""
        return self.search(DiscoveryQuery(query="kodeks", lang=LANG_UZ_LATIN, form_id=FORM_CODE))
