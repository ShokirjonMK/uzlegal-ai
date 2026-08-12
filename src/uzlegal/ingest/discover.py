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


# --------------------------------------------------------------------------- #
# Keng kashfiyot
# --------------------------------------------------------------------------- #

# Huquqiy sohalar bo'yicha qidiruv lug'ati.
#
# NEGA LUG'AT KERAK. lex.uz qidiruvi bir so'rovga **20 ta** natija
# qaytaradi va sahifalashni qo'llab-quvvatlamaydi (statik HTML da hech
# qanday `page` parametri yo'q — tekshirildi). Ya'ni bitta so'rov bilan
# katalogni qurib bo'lmaydi.
#
# Yechim: bitta keng so'rov o'rniga **ko'p tor so'rov**. Har biri o'z
# sohasining eng tegishli 20 tasini beradi, natijalar birlashtiriladi va
# takrorlanuvchilar olib tashlanadi. Bu to'liq katalogni bermaydi, lekin
# amaliy qamrovni sezilarli kengaytiradi.
#
# Atamalar huquq sohalari bo'yicha tanlangan — alifbo tartibida emas,
# chunki maqsad KENG QAMROV, tekis taqsimot emas.
SEARCH_VOCABULARY: tuple[str, ...] = (
    # Fuqarolik huquqi
    "shartnoma",
    "mulk",
    "meros",
    "zarar",
    "majburiyat",
    "ijara",
    "oldi-sotdi",
    "garov",
    "vakolat",
    "yuridik shaxs",
    "intellektual mulk",
    "sug'urta",
    # Mehnat
    "mehnat",
    "ish haqi",
    "ta'til",
    "mehnat shartnomasi",
    "kasaba uyushmasi",
    "mehnat muhofazasi",
    "nafaqa",
    "pensiya",
    # Jinoyat va protsess
    "jinoyat",
    "jazo",
    "sud",
    "tergov",
    "dalil",
    "apellyatsiya",
    "kassatsiya",
    "advokatura",
    "prokuratura",
    "ekspertiza",
    # Ma'muriy
    "ma'muriy javobgarlik",
    "litsenziya",
    "ruxsatnoma",
    "davlat xizmati",
    "murojaat",
    "nazorat",
    "jarima",
    # Iqtisodiy va soliq
    "soliq",
    "bojxona",
    "budjet",
    "bank",
    "valyuta",
    "investitsiya",
    "tadbirkorlik",
    "raqobat",
    "bankrotlik",
    "auditorlik",
    # Oila va shaxs
    "oila",
    "nikoh",
    "bola",
    "vasiylik",
    "fuqarolik",
    "migratsiya",
    # Yer va qurilish
    "yer",
    "uy-joy",
    "shaharsozlik",
    "qurilish",
    "ko'chmas mulk",
    # Boshqa sohalar
    "ta'lim",
    "sog'liqni saqlash",
    "ekologiya",
    "transport",
    "energetika",
    "axborot",
    "shaxsga doir ma'lumot",
    "elektron hukumat",
    "davlat xaridlari",
    "korrupsiyaga qarshi",
    "qishloq xo'jaligi",
    "madaniyat",
    "sport",
)


# Rus nashrlari uchun ALOHIDA lug'at.
#
# NEGA ALOHIDA. Bu birinchi urinishda o'tkazib yuborilgan va u 95
# daqiqani behuda sarfladi: rus hujjatlariga o'zbekcha atamalar bilan
# murojaat qilindi (`majburiyat`, `ijara`) va qidiruv har safar **0 ta**
# natija qaytardi. lex.uz matn bo'yicha qidiradi, tarjima qilmaydi —
# rus hujjatida o'zbekcha so'z uchramaydi.
#
# Atamalar yuqoridagi o'zbek lug'ati bilan bir xil sohalarni qoplaydi.
SEARCH_VOCABULARY_RU: tuple[str, ...] = (
    # Гражданское право
    "договор",
    "собственность",
    "наследство",
    "ущерб",
    "обязательство",
    "аренда",
    "купля-продажа",
    "залог",
    "доверенность",
    "юридическое лицо",
    "интеллектуальная собственность",
    "страхование",
    # Труд
    "труд",
    "заработная плата",
    "отпуск",
    "трудовой договор",
    "профсоюз",
    "охрана труда",
    "пособие",
    "пенсия",
    # Уголовное и процесс
    "преступление",
    "наказание",
    "суд",
    "следствие",
    "доказательство",
    "апелляция",
    "кассация",
    "адвокатура",
    "прокуратура",
    "экспертиза",
    # Административное
    "административная ответственность",
    "лицензия",
    "разрешение",
    "государственная служба",
    "обращение",
    "контроль",
    "штраф",
    # Экономика и налоги
    "налог",
    "таможня",
    "бюджет",
    "банк",
    "валюта",
    "инвестиции",
    "предпринимательство",
    "конкуренция",
    "банкротство",
    "аудит",
    # Семья и личность
    "семья",
    "брак",
    "ребёнок",
    "опека",
    "гражданство",
    "миграция",
    # Земля и строительство
    "земля",
    "жильё",
    "градостроительство",
    "строительство",
    "недвижимость",
    # Прочие
    "образование",
    "здравоохранение",
    "экология",
    "транспорт",
    "энергетика",
    "информация",
    "персональные данные",
    "электронное правительство",
    "государственные закупки",
    "противодействие коррупции",
    "сельское хозяйство",
    "культура",
    "спорт",
)

# Til → lug'at. Kirill o'zbek nashrlari lotin bilan bir xil atamalarga
# javob bermaydi, lekin ular hozircha qamrovga kiritilmagan.
VOCABULARY_BY_LANG: dict[str, tuple[str, ...]] = {
    LANG_UZ_LATIN: SEARCH_VOCABULARY,
    LANG_RU: SEARCH_VOCABULARY_RU,
}


def broad_queries(
    *,
    langs: tuple[str, ...] = (LANG_UZ_LATIN,),
    forms: tuple[str | None, ...] = (FORM_CODE, FORM_LAW, FORM_DECREE, FORM_RESOLUTION),
    vocabulary: tuple[str, ...] | None = None,
    statuses: tuple[str, ...] = (STATUS_IN_FORCE,),
) -> list[DiscoveryQuery]:
    """Keng kashfiyot uchun so'rovlar ro'yxatini yig'adi.

    Har til uchun **o'z lug'ati** ishlatiladi (`VOCABULARY_BY_LANG`).
    `vocabulary` aniq berilsa — u barcha tillarga qo'llaniladi; bu
    faqat sinov uchun.

    So'rovlar soni = lug'at × shakl × til × holat. Har biri bitta HTTP
    so'rov, ya'ni `Crawl-delay: 20` bo'yicha 20 soniya. 71 atama × 4
    shakl ≈ 284 so'rov ≈ **95 daqiqa** bitta til uchun.

    Chaqiruvchi hajmni oldindan bilishi kerak — funksiya ro'yxat
    qaytaradi, uni o'zi bajarmaydi.
    """
    return [
        DiscoveryQuery(query=term, lang=lang, form_id=form, status=status)
        for lang in langs
        for status in statuses
        for form in forms
        for term in (vocabulary or VOCABULARY_BY_LANG.get(lang, SEARCH_VOCABULARY))
    ]


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
