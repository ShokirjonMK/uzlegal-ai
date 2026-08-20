"""Qamrov darvozasi — docs/27.

Ikki talab teng darajada muhim va ikkalasi ham shu yerda ushlanadi:

* qamrovdan tashqaridagi savol **rad etilsin**;
* qamrovdagi savol **rad etilmasin**.

Ikkinchisi birinchisidan xavfliroq: haddan tashqari ehtiyotkor darvoza
mahsulotni ishlatib bo'lmaydigan qiladi va buni sezish qiyin, chunki
«rad etdim» xatoga o'xshamaydi.
"""

from __future__ import annotations

import pytest

from uzlegal.index.chunker import Chunk
from uzlegal.retrieval.coverage import CoverageGap, check_coverage


class FakeIndex:
    """Yengil indeks — `_chunks` lug'ati yetarli, LanceDB kerak emas."""

    def __init__(self, docs: list[tuple[str, str, str]]) -> None:
        self._chunks = {
            doc_id: Chunk(
                chunk_id=f"{doc_id}:1",
                doc_id=doc_id,
                doc_title=title,
                doc_type=doc_type,
                lang="uz",
                heading=f"[{title}]",
                content="matn",
            )
            for doc_id, doc_type, title in docs
        }

    def read_chunks(self) -> None:  # pragma: no cover — chaqirilmaydi
        pass


def kodekslar_indeksi() -> FakeIndex:
    """Haqiqiy korpusga o'xshash: kodekslar bor, plenum va hokim yo'q."""
    return FakeIndex(
        [(f"d-{i}", "kodeks", f"{i}-kodeks") for i in range(20)]
        + [("p-1", "plenum", "Oliy sudi Plenumi qarori")]
    )


# --------------------------------------------------------------------------- #
# Boshqa yurisdiksiya
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("savol", "kutilgan"),
    [
        ("AQSh Konstitutsiyasining 5-tuzatishi nima deydi", "AQSh"),
        ("Rossiya Fuqarolik kodeksida bu qanday", "Rossiya"),
        ("Qozog'iston qonuni bo'yicha soliq stavkasi", "Qozog'iston"),
        ("Germaniya mehnat qonunchiligi qanday", "Germaniya"),
    ],
)
def test_boshqa_yurisdiksiya_rad_etiladi(savol: str, kutilgan: str) -> None:
    gap = check_coverage(savol)
    assert gap is not None
    assert gap.kind == "yurisdiksiya"
    assert gap.subject == kutilgan


def test_gdpr_qoshimcha_sozsiz_ham_taniladi() -> None:
    """«GDPR jarimasi qancha» — savolda «qonun» so'zi yo'q.

    GDPR ning o'zi huquqiy hujjat, shuning uchun u qo'shimcha manba
    so'zini talab qilmaydi.
    """
    gap = check_coverage("Yevropa Ittifoqi GDPR jarimasi qancha")
    assert gap is not None and gap.kind == "yurisdiksiya"


def test_indekssiz_ham_yurisdiksiya_ishlaydi() -> None:
    """Yurisdiksiya tekshiruvi korpusga bog'liq emas — u har doim ishlaydi."""
    assert check_coverage("AQSh qonuni nima deydi", None) is not None


# --------------------------------------------------------------------------- #
# Yolg'on ijobiy — eng xavfli xato turi
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "savol",
    [
        # Boshqa davlat TILGA OLINADI, lekin savol O'zbekiston huquqi haqida.
        "Rossiyaga tovar eksport qilishda bojxona rasmiylashtiruvi qanday",
        "Chet el fuqarosi O'zbekistonda mulk sotib ola oladimi",
        "Xitoydan olib kelingan tovarga aksiz solig'i qanday hisoblanadi",
        # Oddiy O'zbekiston savollari.
        "Mehnat shartnomasi qanday bekor qilinadi",
        "Vindikatsiya da'vosi muddati qancha",
        "Nikohdan ajrashishda mol-mulk qanday bo'linadi",
    ],
)
def test_ozbekiston_savollari_rad_etilmaydi(savol: str) -> None:
    assert check_coverage(savol, kodekslar_indeksi()) is None


def test_bosh_savol_tosmaydi() -> None:
    assert check_coverage("", kodekslar_indeksi()) is None
    assert check_coverage("   ", kodekslar_indeksi()) is None


# --------------------------------------------------------------------------- #
# Korpusda yo'q manba turi
# --------------------------------------------------------------------------- #


def test_plenum_kam_bolsa_rad_etiladi() -> None:
    """Korpusda bitta plenum qarori bor — bu «qamrov» degani emas."""
    gap = check_coverage("Oliy sud Plenumining oxirgi qarori nima", kodekslar_indeksi())
    assert gap is not None
    assert gap.kind == "manba-turi"
    assert "Plenum" in gap.subject


def test_hokim_qarori_rad_etiladi() -> None:
    savol = "Toshkent shahar hokimining 2025-yil 14-iyundagi qarorida nima yozilgan"
    gap = check_coverage(savol, kodekslar_indeksi())
    assert gap is not None and gap.kind == "manba-turi"


def test_xalqaro_huquq_rad_etiladi() -> None:
    """«Xalqaro dengiz huquqi» — oraliq so'z bilan ham tanilishi kerak."""
    savol = "Xalqaro dengiz huquqi bo'yicha O'zbekiston qanday majburiyat oldi"
    gap = check_coverage(savol, kodekslar_indeksi())
    assert gap is not None and gap.kind == "manba-turi"


def test_sud_hokimiyati_hokim_qarori_emas() -> None:
    """«Sud hokimiyati» so'zi «hokim qarori» deb tushunilmasin."""
    savol = "Sud hokimiyati mustaqilligi qanday ta'minlanadi"
    assert check_coverage(savol, kodekslar_indeksi()) is None


def test_korpus_kengaysa_tekshiruv_ozi_yumshaydi() -> None:
    """Chegara ma'lumotdan o'qiladi, kodda qotirilmagan.

    Bu muhim xossa: korpusga plenum qarorlari qo'shilsa, darvoza
    **qo'lda o'zgartirilmasdan** ularni o'tkaza boshlaydi.
    """
    savol = "Oliy sud Plenumining oxirgi qarori nima"
    kam = FakeIndex([("p-1", "plenum", "Plenum qarori")])
    kop = FakeIndex([(f"p-{i}", "plenum", f"Plenum qarori {i}") for i in range(25)])

    assert check_coverage(savol, kam) is not None
    assert check_coverage(savol, kop) is None


def test_hisobot_sababni_aytadi() -> None:
    """Rad javob «yo'q» demaydi — nima uchun yo'qligini aytadi."""
    gap = check_coverage("AQSh Konstitutsiyasi nima deydi")
    assert isinstance(gap, CoverageGap)
    assert "O'zbekiston" in gap.detail
    assert gap.subject in gap.detail
