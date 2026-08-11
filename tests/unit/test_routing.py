"""Hujjat yo'naltirish testlari.

Yo'naltirishning eng muhim xususiyati — u **qat'iy filtr emas**. Shuning
uchun testlar ikki narsani tekshiradi: to'g'ri hujjat ko'tarildimi va
mos kelmagan hujjat ro'yxatda qoldimi.
"""

from __future__ import annotations

from uzlegal.retrieval.routing import Domain, DocumentRouter, Route, RoutingConfig

# --------------------------------------------------------------------------- #
# Sinov sozlamasi — haqiqiy YAML dan mustaqil
# --------------------------------------------------------------------------- #

CONFIG = RoutingConfig(
    domains=(
        Domain(
            name="mehnat",
            documents=("mehnat kodeksi",),
            triggers=("xodim", "ish haqi", "maosh", "sinov muddati"),
        ),
        Domain(
            name="soliq",
            documents=("soliq kodeksi",),
            triggers=("soliq", "mmt"),
        ),
        Domain(
            name="fuqarolik-protsessual",
            documents=("fuqarolik protsessual kodeksi", "fuqarolik kodeksi"),
            triggers=("sudga murojaat", "dalil"),
            weight=0.9,
        ),
    ),
    boost=0.8,
    min_score=1.0,
)


def router() -> DocumentRouter:
    return DocumentRouter(CONFIG)


# --------------------------------------------------------------------------- #
# Yo'naltirish
# --------------------------------------------------------------------------- #


def test_soha_aniqlanadi() -> None:
    route = router().route("Maoshni toʻlash tartibi va muddatlari")
    assert route.domains == ["mehnat"]
    assert route.primary_document == "mehnat kodeksi"


def test_umumiy_savol_yonaltirilmaydi() -> None:
    """Hech bir soha belgisi yo'q — taxmin qilishning ma'nosi yo'q."""
    route = router().route("Bu qanday hujjat")
    assert not route.is_routed
    assert route.documents == []


def test_kop_sozli_ibora_kuchliroq() -> None:
    """«sinov muddati» ikki so'zli — u bitta so'zdan ko'proq ball beradi."""
    single = router()._term_score("xodim")
    phrase = router()._term_score("sinov muddati")
    assert phrase > single


def test_protsessual_savol_moddiy_kodeksni_ham_kotaradi() -> None:
    """«Sudga murojaat muddati» protsessual ko'rinadi, javob esa FK da.

    Shuning uchun protsessual soha ikkala kodeksni ham ko'taradi —
    aks holda bu savol butunlay buzilardi.
    """
    route = router().route("Sudga murojaat qilish uchun necha yil vaqt bor")
    assert "fuqarolik protsessual kodeksi" in route.documents
    assert "fuqarolik kodeksi" in route.documents


def test_ikki_soha_ishonchni_pasaytiradi() -> None:
    """Savol ikki sohaga tegishli bo'lsa ko'tarish kuchi kamayadi."""
    one = router().route("Xodimning ish haqi")
    two = router().route("Xodim soliq toʻlaydimi")
    assert two.confidence < one.confidence


def test_apostrof_shakli_ahamiyatsiz() -> None:
    """`fold()` tufayli barcha apostrof variantlari bir xil ishlaydi."""
    assert router().route("Maosh toʻlash").domains == router().route("Maosh to'lash").domains


# --------------------------------------------------------------------------- #
# Ko'tarish ko'paytmasi
# --------------------------------------------------------------------------- #


def test_mos_hujjat_kotariladi() -> None:
    route = router().route("Xodimning ish haqi")
    assert router().boost_factor(route, "Oʻzbekiston Respublikasining Mehnat kodeksi") > 1.0


def test_mos_kelmagan_hujjat_jazolanmaydi() -> None:
    """Ko'tarish faqat qo'shadi — boshqa hujjat balli o'zgarmaydi.

    Bu ataylab: yo'naltirish xato qilsa to'g'ri javob pastga tushadi,
    lekin **yo'qolmaydi**.
    """
    route = router().route("Xodimning ish haqi")
    assert router().boost_factor(route, "Oʻzbekiston Respublikasining Bojxona kodeksi") == 1.0


def test_yonaltirilmagan_sorovda_hech_narsa_ozgarmaydi() -> None:
    assert router().boost_factor(Route(), "Mehnat kodeksi") == 1.0


def test_notogri_sozlama_yiqilmaydi() -> None:
    """Hujjati yoki triggeri yo'q soha o'tkazib yuboriladi, xato bermaydi."""
    from uzlegal.retrieval.routing import _parse_config

    config = _parse_config({"domains": {"bosh": {"documents": [], "triggers": []}}})
    assert config.domains == ()
