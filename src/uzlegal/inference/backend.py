"""Inference backend protokoli va ro'yxatdan o'tkazish mexanizmi.

Bu modulning maqsadi — model runtime ni **almashtiriladigan** qilish.
Yangi backend qo'shish uchun:

1. `InferenceBackend` ni amalga oshiruvchi klass yozing
2. Uni `@register_backend("nom")` bilan belgilang
3. `configs/models.yaml` da `backend: nom` deb yozing

Boshqa hech qanday kod o'zgarmaydi.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any, Protocol, runtime_checkable

from uzlegal.types import GenerationParams, ModelSpec

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Protokol
# --------------------------------------------------------------------------- #


@runtime_checkable
class InferenceBackend(Protocol):
    """Har qanday model runtime shu shartnomani bajaradi.

    Yuqori qatlamlar (agents, orchestrator) faqat shu protokolni biladi va
    MLX, vLLM yoki boshqa runtime ishlatilayotganini bilmaydi.
    """

    spec: ModelSpec

    def load(self) -> None:
        """Modelni xotiraga yuklash. Idempotent bo'lishi kerak."""
        ...

    def unload(self) -> None:
        """Xotirani bo'shatish. Almashtirishdan oldin chaqiriladi."""
        ...

    @property
    def is_loaded(self) -> bool: ...

    def set_adapter(self, adapter_path: str | None) -> None:
        """LoRA adapterini almashtirish. `None` — bazaga qaytish."""
        ...

    def generate(self, prompt: str, params: GenerationParams) -> str: ...

    def stream(self, prompt: str, params: GenerationParams) -> Iterator[str]: ...

    def make_prefix_cache(self, prefix: str) -> Any:
        """Umumiy prefiks uchun KV-cache. Qo'llab-quvvatlanmasa `None`.

        Debate rejimida beshta agent bir xil huquqiy kontekstni oladi —
        uni bir marta hisoblash 3.8x tezlashtiradi (ADR-005).
        """
        ...

    def memory_usage_gb(self) -> float: ...


# --------------------------------------------------------------------------- #
# Backend reestri
# --------------------------------------------------------------------------- #

_BACKENDS: dict[str, type[InferenceBackend]] = {}


def register_backend(name: str):  # type: ignore[no-untyped-def]
    """Backend klassini `name` nomi ostida ro'yxatdan o'tkazadi."""

    def decorator(cls: type[InferenceBackend]) -> type[InferenceBackend]:
        if name in _BACKENDS:
            raise ValueError(f"Backend '{name}' allaqachon ro'yxatda")
        _BACKENDS[name] = cls
        return cls

    return decorator


def available_backends() -> list[str]:
    """Bu mashinada ishlay oladigan backendlar.

    O'rnatilganlarni o'zi yuklaydi, shuning uchun chaqiruv tartibi muhim emas.
    """
    load_builtin_backends()
    return sorted(_BACKENDS)


def create_backend(spec: ModelSpec) -> InferenceBackend:
    """Spetsifikatsiyadan backend nusxasini yaratadi (yuklamaydi)."""
    if spec.backend not in _BACKENDS:
        raise UnknownBackendError(
            f"Noma'lum backend: '{spec.backend}'. "
            f"Mavjud: {', '.join(available_backends()) or '(yo’q)'}"
        )
    return _BACKENDS[spec.backend](spec)  # type: ignore[call-arg]


class UnknownBackendError(ValueError):
    pass


class BackendUnavailableError(RuntimeError):
    """Backend ro'yxatda bor, lekin bu mashinada ishlay olmaydi.

    Masalan: MLX Linux da, yoki vLLM CUDA siz.
    """


_builtins_loaded = False


def load_builtin_backends() -> None:
    """O'rnatilgan backendlarni import qiladi (idempotent).

    Har biri ixtiyoriy bog'liqlikka ega, shuning uchun import xatosi
    jim yutiladi — mashinada mavjud bo'lganlari ro'yxatga tushadi.
    """
    global _builtins_loaded
    if _builtins_loaded:
        return
    _builtins_loaded = True

    from uzlegal.inference import echo_backend  # noqa: F401  (har doim mavjud)

    for module in ("mlx_backend", "vllm_backend", "openai_backend"):
        try:
            __import__(f"uzlegal.inference.{module}")
        except ImportError as exc:
            log.debug("Backend '%s' mavjud emas: %s", module, exc)
