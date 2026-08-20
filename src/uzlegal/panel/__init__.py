"""Senior yurist kengashi — trening namunalarini avtomatik saralash.

Kengash odam tekshiruvini **almashtirmaydi**, unga tushadigan oqimni
tozalaydi: aniq yomonini rad etadi, aniq yaxshisini namunaviy
tekshiruvga qoldiradi, chinakam noaniqni esa kelishmovchilik bilan
birga yuristga uzatadi. Batafsil: `docs/26`.
"""

from uzlegal.panel.review import (
    MIN_CONFIDENCE,
    SPOT_CHECK_RATE,
    PanelReport,
    SeniorReviewer,
    SeniorVerdict,
    decide,
    review_sample,
)
from uzlegal.panel.seniors import PANEL_SIZE, SENIORS, Senior, select

__all__ = [
    "MIN_CONFIDENCE",
    "PANEL_SIZE",
    "SENIORS",
    "SPOT_CHECK_RATE",
    "PanelReport",
    "Senior",
    "SeniorReviewer",
    "SeniorVerdict",
    "decide",
    "review_sample",
    "select",
]
