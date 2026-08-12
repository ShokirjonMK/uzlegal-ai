"""OpenAI-mos backend — Ollama, vLLM, LM Studio va o'z serveringiz.

## Nima uchun bu backend loyihaning eng muhim qismi

`mlx` faqat Apple Silicon da ishlaydi. Undan tashqarida `echo` dan boshqa
hech narsa qolmaydi — ya'ni tizim soxta javob beradi. Bu backendsiz:

* `configs/profiles/server.yaml` (Linux + GPU) ishlay olmaydi
* `deploy/docker-compose.server.yaml` ishlay olmaydi
* Windows va Linux ishchi stantsiyalarida umuman model yo'q

Shuning uchun `backend.py` uni allaqachon kutadi (`load_builtin_backends`),
lekin fayl mavjud emas edi va import xatosi jimgina yutilardi.

## Nima uchun HTTP, nima uchun yangi kutubxona emas

`openai` paketi qo'shilmadi: bizga kerak bo'lgan ikkita endpoint oddiy
JSON POST. `httpx` esa allaqachon bog'liqliklar ro'yxatida (`pyproject.toml`).
Bitta paket kamroq — bitta versiya nizosi kamroq.

## Qaysi serverlar bilan ishlaydi

    Ollama      http://localhost:11434/v1     (eng oson, CUDA va Metal)
    vLLM        http://localhost:8000/v1      (ishlab chiqarish, A100/H100)
    LM Studio   http://localhost:1234/v1      (ish stoli)
    O'z serveri https://gpu.example.uz/v1     (hybrid profil)

Hammasi `/chat/completions` shartnomasini bajaradi, shuning uchun kod bitta.

## Xotira hisobi bu yerda YO'Q

`memory_usage_gb()` doim 0.0 qaytaradi va bu ataylab: model **boshqa
jarayonda** (yoki umuman boshqa mashinada) turadi. Uni bizning
byudjetimizga qo'shish reestrni chalg'itadi — u MLX uchun yozilgan, u
yerda model bizning jarayonimiz xotirasida yashaydi.

## Prefix KV-cache

`make_prefix_cache()` `None` qaytaradi. Sabab: KV-cache server tomonida
va u bizga ob'ekt sifatida berilmaydi. Ollama va vLLM ikkalasi ham
prefiksni **o'zi** keshlaydi (avtomatik prefix caching), shuning uchun
ADR-005 dagi tezlik baribir olinadi — faqat uni biz boshqarmaymiz.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from typing import Any

import httpx

from uzlegal.inference.backend import (
    BackendUnavailableError,
    InferenceBackend,
    register_backend,
)
from uzlegal.types import GenerationParams, ModelSpec

log = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "http://localhost:11434/v1"

# Model yuklanishi (Ollama da birinchi so'rov modelni diskdan ko'taradi) uzoq
# davom etishi mumkin — 12B model sekin diskda bir daqiqagacha oladi.
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 600.0


@register_backend("openai")
class OpenAIBackend(InferenceBackend):
    """OpenAI-mos HTTP endpoint ustidagi backend."""

    def __init__(self, spec: ModelSpec) -> None:
        self.spec = spec
        self._client: httpx.Client | None = None
        self._adapter: str | None = None

    # ------------------------------------------------------------------ #
    # Sozlamalar
    # ------------------------------------------------------------------ #

    @property
    def endpoint(self) -> str:
        """Server manzili.

        Tartib: model yozuvi → muhit o'zgaruvchisi → standart (Ollama).
        Muhit o'zgaruvchisi YAML dan past turadi, chunki YAML aniq
        ko'rsatilgan tanlov, env esa mashinaga xos standart.
        """
        return (
            self.spec.endpoint or os.getenv("UZLEGAL_OPENAI_ENDPOINT") or DEFAULT_ENDPOINT
        ).rstrip("/")

    @property
    def model_name(self) -> str:
        """Serverdagi model nomi.

        `hf_id` ishlatiladi, chunki Ollama da bu `gemma3:12b`, vLLM da esa
        `google/gemma-3-12b-it` — ikkalasi ham "server bu modelni shu nom
        bilan biladi" degani. Ko'rsatilmasa ichki `id` ga tushamiz.
        """
        return self.spec.hf_id or self.spec.id

    @property
    def _api_key(self) -> str:
        # Ollama kalit talab qilmaydi, lekin ba'zi mijozlar bo'sh
        # `Authorization` sarlavhasidan shikoyat qiladi — shuning uchun
        # o'rin to'ldiruvchi qiymat beriladi.
        return os.getenv("UZLEGAL_OPENAI_API_KEY") or "not-needed"

    # ------------------------------------------------------------------ #
    # Hayot davri
    # ------------------------------------------------------------------ #

    def load(self) -> None:
        """Serverga ulanadi va model mavjudligini tekshiradi.

        Bu yerda «yuklash» xotiraga ko'chirish emas — model serverda.
        Lekin tekshiruv baribir kerak: aks holda xato birinchi haqiqiy
        savolda, foydalanuvchi kutib turganda chiqadi. Ishga tushish
        paytida chiqqani yaxshiroq.
        """
        if self._client is not None:
            return

        client = httpx.Client(
            base_url=self.endpoint,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=httpx.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT),
        )

        try:
            response = client.get("/models")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            client.close()
            raise BackendUnavailableError(
                f"Server javob bermadi: {self.endpoint} ({exc}). "
                f"Ollama ishlayaptimi? Tekshirish: `ollama serve`"
            ) from exc

        available = self._model_ids(response)
        # Ba'zi serverlar (eski vLLM) ro'yxatni bermaydi — bo'sh ro'yxat
        # «yo'q» degani emas, «bilmadim» degani. Bunday holda o'tkazamiz.
        if available and not self._matches(available):
            client.close()
            raise BackendUnavailableError(
                f"Serverda '{self.model_name}' modeli yo'q. "
                f"Mavjud: {', '.join(sorted(available)[:10])}. "
                f"Yuklash: `ollama pull {self.model_name}`"
            )

        self._client = client
        log.info("OpenAI-mos backend tayyor: %s @ %s", self.model_name, self.endpoint)

    def unload(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        self._adapter = None

    @property
    def is_loaded(self) -> bool:
        return self._client is not None

    def set_adapter(self, adapter_path: str | None) -> None:
        """LoRA adapteri — masofaviy serverda qo'llab-quvvatlanmaydi.

        `None` (bazaga qaytish) muammosiz o'tadi. Haqiqiy adapter esa
        **jim o'tkazib yuborilmaydi**: rol adapteri so'ralgan, lekin
        qo'llanmagan javob — noto'g'ri javob, va u sezilmay qoladi.
        """
        if adapter_path is None:
            self._adapter = None
            return
        raise NotImplementedError(
            "OpenAI-mos backend LoRA adapterini almashtira olmaydi — adapter "
            "server tomonida yuklanishi kerak (vLLM `--enable-lora`). "
            "Rol farqi hozircha promptdan keladi."
        )

    # ------------------------------------------------------------------ #
    # Generatsiya
    # ------------------------------------------------------------------ #

    def generate(self, prompt: str, params: GenerationParams) -> str:
        client = self._require_loaded()
        payload = self._payload(prompt, params, stream=False)

        try:
            response = client.post("/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Generatsiya xatosi ({self.endpoint}): {exc}") from exc

        return self._first_message(response.json())

    def stream(self, prompt: str, params: GenerationParams) -> Iterator[str]:
        client = self._require_loaded()
        payload = self._payload(prompt, params, stream=True)

        try:
            with client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    chunk = self._sse_chunk(line)
                    if chunk is None:
                        continue
                    if chunk == "":
                        # Bo'sh delta — rol e'loni yoki yakunlovchi bo'lak.
                        continue
                    yield chunk
                    if params.stop and any(s in chunk for s in params.stop):
                        break
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Oqim xatosi ({self.endpoint}): {exc}") from exc

    def make_prefix_cache(self, prefix: str) -> Any:
        """Server tomonida — bizda ob'ekt yo'q (modul izohiga qarang)."""
        return None

    def memory_usage_gb(self) -> float:
        """Model boshqa jarayonda — bizning byudjetimizda o'rni yo'q."""
        return 0.0

    # ------------------------------------------------------------------ #
    # Ichki yordamchilar
    # ------------------------------------------------------------------ #

    def _payload(self, prompt: str, params: GenerationParams, *, stream: bool) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if params.system:
            messages.append({"role": "system", "content": params.system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": params.max_tokens,
            "temperature": params.temperature,
            "top_p": params.top_p,
            "stream": stream,
        }
        if params.stop:
            payload["stop"] = params.stop
        if params.seed is not None:
            payload["seed"] = params.seed
        return payload

    @staticmethod
    def _first_message(data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"Server bo'sh javob qaytardi: {data}")
        content = (choices[0].get("message") or {}).get("content")
        return str(content or "")

    @staticmethod
    def _sse_chunk(line: str) -> str | None:
        """SSE satridan matn bo'lagini ajratadi.

        `None` — bu satr ma'lumot emas (bo'sh satr, izoh yoki `[DONE]`).
        Bo'sh satr (`""`) — ma'lumot bor, lekin matn yo'q.
        """
        if not line.startswith("data:"):
            return None
        body = line[5:].strip()
        if not body or body == "[DONE]":
            return None
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            log.debug("SSE bo'lagi o'qilmadi: %r", body)
            return None

        choices = data.get("choices") or []
        if not choices:
            return None
        delta = choices[0].get("delta") or {}
        return str(delta.get("content") or "")

    @staticmethod
    def _model_ids(response: httpx.Response) -> set[str]:
        try:
            data = response.json().get("data") or []
        except json.JSONDecodeError:
            return set()
        return {str(item.get("id")) for item in data if item.get("id")}

    def _matches(self, available: set[str]) -> bool:
        """Model serverda bormi.

        Ollama `gemma3:12b` ni ba'zan `gemma3:12b` deb, ba'zan
        `gemma3:12b-it-q4_K_M` deb qaytaradi — shuning uchun aniq moslik
        topilmasa prefiks bo'yicha ham qaraladi.
        """
        name = self.model_name
        if name in available:
            return True
        # `gemma3:12b` so'ralgan, serverda `gemma3:12b-...` bo'lishi mumkin
        return any(item.startswith(f"{name}-") or item == f"{name}:latest" for item in available)

    def _require_loaded(self) -> httpx.Client:
        if self._client is None:
            raise RuntimeError(f"Backend '{self.spec.id}' yuklanmagan — `load()` chaqirilmagan")
        return self._client
