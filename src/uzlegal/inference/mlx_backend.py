"""MLX backend — Apple Silicon (ADR-004).

MLX tanlangan sabab: bir stekda ham inference, ham LoRA trening. Model
konvertatsiyasi va formatlar bir xil bo'lib qoladi.

Bu modul `mlx` o'rnatilmagan bo'lsa import xatosi beradi va reestr uni jim
o'tkazib yuboradi — Linux mashinada tizim baribir ishga tushadi.
"""

from __future__ import annotations

import gc
import logging
from collections.abc import Iterator
from pathlib import Path

import mlx.core as mx
from mlx_lm import generate, load, stream_generate
from mlx_lm.sample_utils import make_sampler

from uzlegal.inference.backend import InferenceBackend, register_backend
from uzlegal.types import GenerationParams, ModelSpec

log = logging.getLogger(__name__)


@register_backend("mlx")
class MLXBackend(InferenceBackend):
    def __init__(self, spec: ModelSpec) -> None:
        self.spec = spec
        self._model = None
        self._tokenizer = None
        self._adapter: str | None = None
        self._loaded_from: str | None = None

    # ------------------------------------------------------------------ #

    def load(self) -> None:
        if self._model is not None:
            return
        if not mx.metal.is_available():
            raise RuntimeError(
                "Metal mavjud emas. MLX faqat Apple Silicon da ishlaydi. "
                "Boshqa platformada `backend: vllm` yoki `backend: echo` ishlating."
            )

        source = self.spec.local_path or self.spec.hf_id
        if not source:
            raise ValueError(f"Model '{self.spec.id}' uchun local_path yoki hf_id ko'rsatilmagan")

        if self.spec.local_path and not Path(self.spec.local_path).exists():
            raise FileNotFoundError(
                f"Model topilmadi: {self.spec.local_path}. "
                f"Yuklab olish: uzlegal models pull {self.spec.id}"
            )

        log.info("MLX model yuklanmoqda: %s", source)
        self._model, self._tokenizer = load(source)
        self._loaded_from = source

    def unload(self) -> None:
        self._model = None
        self._tokenizer = None
        self._adapter = None
        self._loaded_from = None
        gc.collect()
        # Metal bufer keshini bo'shatish — keyingi model uchun joy ochadi.
        # 24 GB da bu majburiy: aks holda eski model xotirasi band qoladi.
        clear = getattr(mx, "clear_cache", None) or getattr(mx.metal, "clear_cache", None)
        if clear is not None:
            clear()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    # ------------------------------------------------------------------ #

    def set_adapter(self, adapter_path: str | None) -> None:
        """LoRA adapterini almashtiradi (~50 ms) — ADR-003.

        Baza vaznlar xotirada qoladi; faqat past-rangli qo'shimcha almashadi.
        """
        if adapter_path == self._adapter:
            return
        if self._model is None:
            raise RuntimeError("Model yuklanmagan")

        if adapter_path is None:
            # Bazaga qaytish uchun modelni qayta yuklash kerak — MLX adapterni
            # o'rnatilgandan keyin ajratishni qo'llab-quvvatlamaydi.
            source = self._loaded_from
            self.unload()
            self.spec.local_path = self.spec.local_path or source
            self.load()
            return

        from mlx_lm.tuner.utils import load_adapters

        load_adapters(self._model, adapter_path)
        self._adapter = adapter_path

    # ------------------------------------------------------------------ #

    def _apply_template(self, prompt: str, params: GenerationParams) -> str:
        """Instruct modellar uchun chat shablonini qo'llaydi.

        Busiz Qwen3/Gemma kabi instruct modellar promptni davom ettiradi
        (takrorlaydi) — javob bermaydi. `params.raw=True` bilan o'chiriladi;
        prefix KV-cache da shablon qo'lda qo'yilgani uchun bu kerak bo'ladi.
        """
        if params.raw:
            return prompt
        tokenizer = self._tokenizer
        if not hasattr(tokenizer, "apply_chat_template") or tokenizer.chat_template is None:
            return prompt

        messages = []
        if params.system:
            messages.append({"role": "system", "content": params.system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, object] = {"tokenize": False, "add_generation_prompt": True}
        # Qwen3 "thinking" rejimi — yuridik javobda keraksiz uzun mulohaza beradi
        # va kechikishni oshiradi. Shablon qo'llab-quvvatlasa o'chiriladi.
        if "enable_thinking" in (tokenizer.chat_template or ""):
            kwargs["enable_thinking"] = params.thinking
        return tokenizer.apply_chat_template(messages, **kwargs)  # type: ignore[no-any-return]

    def generate(self, prompt: str, params: GenerationParams) -> str:
        self._require_loaded()
        return generate(  # type: ignore[no-any-return]
            self._model,
            self._tokenizer,
            prompt=self._apply_template(prompt, params),
            max_tokens=params.max_tokens,
            sampler=self._sampler(params),
            verbose=False,
        )

    def stream(self, prompt: str, params: GenerationParams) -> Iterator[str]:
        self._require_loaded()
        for response in stream_generate(
            self._model,
            self._tokenizer,
            prompt=self._apply_template(prompt, params),
            max_tokens=params.max_tokens,
            sampler=self._sampler(params),
            prompt_cache=params.prefix_cache,
        ):
            yield response.text
            if params.stop and any(s in response.text for s in params.stop):
                break

    def make_prefix_cache(self, prefix: str) -> object:
        """Umumiy prefiks uchun KV-cache — debate ni 3.8x tezlashtiradi (ADR-005)."""
        self._require_loaded()
        from mlx_lm.models.cache import make_prompt_cache

        cache = make_prompt_cache(self._model)
        tokens = self._tokenizer.encode(prefix)  # type: ignore[union-attr]
        self._model(mx.array(tokens)[None], cache=cache)  # type: ignore[misc]
        mx.eval([c.state for c in cache])
        return cache

    def memory_usage_gb(self) -> float:
        getter = getattr(mx, "get_active_memory", None) or mx.metal.get_active_memory
        try:
            return float(getter()) / (1024**3)
        except Exception:
            return 0.0

    # ------------------------------------------------------------------ #

    def _sampler(self, params: GenerationParams):  # type: ignore[no-untyped-def]
        return make_sampler(temp=params.temperature, top_p=params.top_p)

    def _require_loaded(self) -> None:
        if self._model is None:
            raise RuntimeError(f"Model '{self.spec.id}' yuklanmagan")
