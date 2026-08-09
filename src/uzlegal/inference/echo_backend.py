"""Echo backend — modelsiz ishlaydigan stub.

Maqsadi: **tizim model yuklab olinmasdan turib ham to'liq ishlashi.**

Bu shunchaki qulaylik emas — u arxitektura vositasi:

* API, UI, CLI, orkestratsiya va testlar 8 GB model kutmasdan ishlaydi
* CI da GPU siz e2e test o'tkazish mumkin
* `InferenceBackend` protokolining ikkinchi amalga oshirilishi sifatida
  abstraksiya haqiqatan to'g'ri chegaralanganini isbotlaydi

Javoblari soxta, lekin **struktura jihatdan haqiqiy** — rol, iqtibos belgilari
va format saqlanadi, shuning yuqori qatlamlar to'g'ri sinaladi.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

from uzlegal.inference.backend import InferenceBackend, register_backend
from uzlegal.types import GenerationParams, ModelSpec


@register_backend("echo")
class EchoBackend(InferenceBackend):
    """Model o'rniga strukturali namuna javob qaytaradi."""

    def __init__(self, spec: ModelSpec) -> None:
        self.spec = spec
        self._loaded = False
        self._adapter: str | None = None

    def load(self) -> None:
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False
        self._adapter = None

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def set_adapter(self, adapter_path: str | None) -> None:
        self._adapter = adapter_path

    def generate(self, prompt: str, params: GenerationParams) -> str:
        return "".join(self.stream(prompt, params))

    def stream(self, prompt: str, params: GenerationParams) -> Iterator[str]:
        role = self._role_hint()
        text = (
            f"[ECHO BACKEND — haqiqiy model yuklanmagan]\n\n"
            f"Rol: {role}\n"
            f"So'rov uzunligi: {len(prompt)} belgi\n\n"
            f"POZITSIYA\n"
            f"Bu namuna javob. Haqiqiy huquqiy tahlil uchun model tanlang:\n"
            f"  uzlegal models use <model-id>\n"
            f"yoki UI dagi Sozlamalar → Model bo'limidan.\n\n"
            f"DALILLAR\n"
            f"1. [o'rtacha] Namuna da'vo. Asos: [C1]\n\n"
            f"ZAIF TOMONLAR\n"
            f"- Bu javob modeldan emas, stub backenddan keldi\n\n"
            f"ISHONCH: 0.0\n"
        )
        for token in text.split(" "):
            yield token + " "
            time.sleep(0.005)

    def make_prefix_cache(self, prefix: str) -> None:
        return None

    def memory_usage_gb(self) -> float:
        return 0.0

    def _role_hint(self) -> str:
        if not self._adapter:
            return "baza (adapter tanlanmagan)"
        return self._adapter.rstrip("/").split("/")[-2:][0]
