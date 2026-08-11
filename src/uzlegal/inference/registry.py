"""Model reestri va issiq almashtirish (hot-swap).

Loyihaning markaziy talabi: **modelni almashtirish juda oson bo'lsin** —
config'dan, CLI'dan, API'dan va UI'dan.

Butun tizimda faqat shu modul modelni yuklaydi va bo'shatadi. Boshqa hamma joy
`registry.active` orqali murojaat qiladi, ya'ni almashtirish bir joyda sodir
bo'ladi va hamma darhol yangi modelni ko'radi.

## Yangi model qo'shish

`configs/models.yaml` ga yozuv qo'shing — boshqa hech narsa kerak emas:

```yaml
models:
  yangi-model:
    display_name: "Yangi model"
    backend: mlx
    hf_id: org/model-name
    size_gb: 8.0
```

## Almashtirish

    uzlegal models use qwen3-14b          # CLI
    POST /v1/models/active {"model_id":…}  # API
    Sozlamalar → Model → tanlash           # UI
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

import yaml

from uzlegal.inference.backend import (
    BackendUnavailableError,
    InferenceBackend,
    available_backends,
    create_backend,
    load_builtin_backends,
)
from uzlegal.types import AdapterSpec, ModelInfo, ModelSpec, ModelStatus

log = logging.getLogger(__name__)

# Apple Silicon unified memory — modeldan tashqari OS, KV-cache, embedder uchun
# joy qoldirish kerak. docs/02-hardware-runtime.md § 2 dagi byudjet.
RESERVED_GB = 9.0


class ModelSwapError(RuntimeError):
    pass


class ModelRegistry:
    """Modellar katalogini boshqaradi va faol modelni almashtiradi.

    Thread-safe: almashtirish davomida boshqa so'rovlar bloklanadi, chunki
    24 GB da eski va yangi model bir vaqtda xotiraga sig'maydi.
    """

    def __init__(
        self,
        catalog_path: Path,
        state_path: Path,
        total_memory_gb: float | None = None,
    ) -> None:
        self.catalog_path = catalog_path
        self.state_path = state_path
        self.total_memory_gb = total_memory_gb or _detect_memory_gb()

        self._lock = threading.RLock()
        self._specs: dict[str, ModelSpec] = {}
        self._adapters: dict[str, AdapterSpec] = {}
        self._backend: InferenceBackend | None = None
        self._active_id: str | None = None
        self._active_adapter: str | None = None
        self._status: dict[str, ModelStatus] = {}
        self._errors: dict[str, str] = {}

        load_builtin_backends()
        self.reload_catalog()

    # ----------------------------------------------------------------- #
    # Katalog
    # ----------------------------------------------------------------- #

    def reload_catalog(self) -> None:
        """`configs/models.yaml` ni qayta o'qiydi.

        Faol model yuklangan holida qoladi — katalog o'zgarishi uni to'xtatmaydi.
        Bu YAML ni tahrirlab, xizmatni qayta ishga tushirmasdan yangi model
        qo'shish imkonini beradi.
        """
        with self._lock:
            raw = yaml.safe_load(self.catalog_path.read_text(encoding="utf-8")) or {}
            specs: dict[str, ModelSpec] = {}

            for model_id, body in (raw.get("models") or {}).items():
                body = dict(body or {})
                body.setdefault("id", model_id)
                body.setdefault("display_name", model_id)
                try:
                    specs[model_id] = ModelSpec(**body)
                except Exception as exc:
                    log.warning("Model '%s' yozuvi noto'g'ri: %s", model_id, exc)

            self._specs = specs

            adapters: dict[str, AdapterSpec] = {}
            for role, body in (raw.get("adapters") or {}).items():
                body = dict(body or {})
                body.setdefault("role", role)
                try:
                    adapters[role] = AdapterSpec(**body)
                except Exception as exc:
                    log.warning("Adapter '%s' yozuvi noto'g'ri: %s", role, exc)
            self._adapters = adapters

            # Holatni har safar qayta tekshiramiz — modelni terminalda yuklab
            # olgandan keyin "Katalogni qayta o'qish" uni darhol ko'rsatishi
            # kerak. Faol modelning holati saqlanadi (u xotirada).
            for model_id, spec in specs.items():
                if model_id != self._active_id:
                    self._status[model_id] = self._probe_status(spec)

    def _probe_status(self, spec: ModelSpec) -> ModelStatus:
        """Model diskda bormi yoki yuklab olish kerakmi.

        Tartib muhim: `local_path` e'lon qilingan bo'lsa, uning mavjudligi
        hal qiladi — backend turidan qat'i nazar. Aks holda stub backend
        yo'q faylni "tayyor" deb ko'rsatib qo'yardi.
        """
        if spec.endpoint:
            return ModelStatus.AVAILABLE  # masofaviy — yuklab olish shart emas
        if spec.local_path:
            return (
                ModelStatus.AVAILABLE
                if Path(spec.local_path).exists()
                else ModelStatus.NOT_DOWNLOADED
            )
        if spec.backend == "echo":
            return ModelStatus.AVAILABLE  # stub — fayl kerak emas
        return ModelStatus.NOT_DOWNLOADED

    # ----------------------------------------------------------------- #
    # So'rov
    # ----------------------------------------------------------------- #

    def list_models(self) -> list[ModelInfo]:
        with self._lock:
            out: list[ModelInfo] = []
            for model_id, spec in self._specs.items():
                fits, warning = self._memory_check(spec)
                out.append(
                    ModelInfo(
                        spec=spec,
                        status=(
                            ModelStatus.ACTIVE
                            if model_id == self._active_id
                            else self._status.get(model_id, ModelStatus.NOT_DOWNLOADED)
                        ),
                        is_active=model_id == self._active_id,
                        fits_in_memory=fits,
                        memory_warning=warning,
                        error=self._errors.get(model_id),
                    )
                )
            return sorted(out, key=lambda m: (not m.is_active, m.spec.id))

    def get_spec(self, model_id: str) -> ModelSpec:
        with self._lock:
            if model_id not in self._specs:
                raise KeyError(
                    f"Model '{model_id}' katalogda yo'q. "
                    f"Mavjud: {', '.join(sorted(self._specs)) or '(bo’sh)'}"
                )
            return self._specs[model_id]

    @property
    def active_id(self) -> str | None:
        return self._active_id

    @property
    def active_adapter(self) -> str | None:
        return self._active_adapter

    @property
    def backend(self) -> InferenceBackend:
        """Faol backend. Model tanlanmagan bo'lsa xato beradi."""
        with self._lock:
            if self._backend is None or not self._backend.is_loaded:
                raise ModelSwapError(
                    "Faol model yo'q. `uzlegal models use <id>` bilan tanlang "
                    "yoki UI dagi Sozlamalar → Model bo'limidan."
                )
            return self._backend

    def _memory_check(self, spec: ModelSpec) -> tuple[bool, str | None]:
        if spec.endpoint or spec.size_gb is None:
            return True, None
        budget = self.total_memory_gb - RESERVED_GB
        if spec.size_gb > budget:
            return False, (
                f"{spec.size_gb:.1f} GB kerak, lekin faqat ~{budget:.1f} GB mavjud "
                f"({self.total_memory_gb:.0f} GB jami − {RESERVED_GB:.0f} GB tizim zaxirasi)"
            )
        if spec.size_gb > budget * 0.85:
            return True, f"Xotira qisiq: {spec.size_gb:.1f} GB / ~{budget:.1f} GB"
        return True, None

    # ----------------------------------------------------------------- #
    # Almashtirish — asosiy operatsiya
    # ----------------------------------------------------------------- #

    def activate(self, model_id: str, *, force: bool = False) -> ModelInfo:
        """Modelni faollashtiradi.

        Tartib: **avval barcha tekshiruvlar**, keyin eskisini bo'shatish,
        so'ng yangisini yuklash. Tekshiruvlar oldin bajarilgani muhim —
        aks holda yuklab olinmagan modelga o'tishga urinish ishlayotgan
        modelni ham yo'q qilardi.

        Tekshiruvlardan o'tgandan keyin yuklash baribir muvaffaqiyatsiz
        bo'lishi mumkin (masalan buzilgan fayl). Bu holda tizim modelsiz
        qoladi va xato ochiq beriladi — eskisiga jim qaytish yashirin
        nosozlikka olib kelardi (24 GB da ikkalasini ushlab turib bo'lmaydi).
        """
        with self._lock:
            spec = self.get_spec(model_id)

            if model_id == self._active_id and self._backend and self._backend.is_loaded:
                log.info("Model '%s' allaqachon faol", model_id)
                return self._info(model_id)

            # --- Tekshiruvlar: hech narsa o'zgartirilmasdan oldin --- #

            fits, warning = self._memory_check(spec)
            if not fits and not force:
                raise ModelSwapError(
                    f"'{spec.display_name}' xotiraga sig'maydi: {warning}. "
                    f"Majburlash uchun force=true (tizim beqaror bo'lishi mumkin)."
                )

            if spec.backend not in available_backends():
                raise BackendUnavailableError(
                    f"'{spec.backend}' backend bu mashinada mavjud emas. "
                    f"O'rnatilgan: {', '.join(available_backends())}. "
                    f"MLX uchun: uv pip install -e '.[mac]'"
                )

            if spec.local_path and not spec.endpoint and not Path(spec.local_path).exists():
                raise ModelSwapError(
                    f"'{spec.display_name}' yuklab olinmagan ({spec.local_path}). "
                    f"Avval yuklab oling: uzlegal models pull {model_id}"
                )

            # --- Tekshiruvlar o'tdi: endi almashtirish --- #

            previous_id = self._active_id
            self._unload_locked()

            self._status[model_id] = ModelStatus.LOADING
            self._errors.pop(model_id, None)
            log.info("Model yuklanmoqda: %s (%s)", model_id, spec.source)

            try:
                backend = create_backend(spec)
                backend.load()
            except Exception as exc:
                self._status[model_id] = ModelStatus.ERROR
                self._errors[model_id] = str(exc)
                log.error("Model '%s' yuklanmadi: %s", model_id, exc)
                raise ModelSwapError(
                    f"'{spec.display_name}' yuklanmadi: {exc}"
                    + (f" (oldingi model '{previous_id}' ham bo'shatildi)" if previous_id else "")
                ) from exc

            self._backend = backend
            self._active_id = model_id
            self._active_adapter = None
            self._status[model_id] = ModelStatus.ACTIVE
            self._persist_state()

            log.info("Model faol: %s (%.1f GB)", model_id, backend.memory_usage_gb())
            return self._info(model_id)

    def set_adapter(self, role: str | None) -> None:
        """Rol adapterini almashtiradi (~50 ms) — ADR-003.

        Baza model xotirada qoladi, faqat 40 MB lik adapter almashadi.
        """
        with self._lock:
            backend = self.backend
            if role is None:
                backend.set_adapter(None)
                self._active_adapter = None
                return

            adapter = self._adapters.get(role)
            if adapter is None:
                raise KeyError(
                    f"Adapter '{role}' ro'yxatda yo'q. "
                    f"Mavjud: {', '.join(sorted(self._adapters)) or '(hali o’qitilmagan)'}"
                )
            if not Path(adapter.path).exists():
                raise FileNotFoundError(
                    f"Adapter fayli topilmadi: {adapter.path}. "
                    f"Faza 4 da o'qitiladi — `uzlegal train lora --role {role}`"
                )
            backend.set_adapter(adapter.path)
            self._active_adapter = role

    def unload(self) -> None:
        """Modelni xotiradan bo'shatadi, lekin tanlovni **eslab qoladi**.

        Bu vaqtinchalik operatsiya (RAM ni bo'shatish), foydalanuvchi
        tanlovining bekor qilinishi emas — shuning uchun saqlangan holat
        o'zgarmaydi va keyingi ishga tushishda o'sha model tiklanadi.
        Tanlovni butunlay unutish uchun `forget()`.
        """
        with self._lock:
            self._unload_locked()

    def forget(self) -> None:
        """Modelni bo'shatadi va saqlangan tanlovni ham o'chiradi."""
        with self._lock:
            self._unload_locked()
            self._persist_state()

    def _unload_locked(self) -> None:
        if self._backend is not None:
            log.info("Model bo'shatilmoqda: %s", self._active_id)
            try:
                self._backend.unload()
            except Exception as exc:
                log.warning("Bo'shatishda xato: %s", exc)
            if self._active_id:
                self._status[self._active_id] = self._probe_status(self._specs[self._active_id])
        self._backend = None
        self._active_id = None
        self._active_adapter = None

    def _info(self, model_id: str) -> ModelInfo:
        return next(m for m in self.list_models() if m.spec.id == model_id)

    # ----------------------------------------------------------------- #
    # Holatni saqlash — qayta ishga tushirishda tiklash
    # ----------------------------------------------------------------- #

    def _persist_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(
                {"active_model": self._active_id, "active_adapter": self._active_adapter},
                indent=2,
            ),
            encoding="utf-8",
        )

    def restore_state(self) -> str | None:
        """Oxirgi tanlangan modelni tiklaydi (xizmat qayta ishga tushganda)."""
        if not self.state_path.exists():
            return None
        try:
            state: dict[str, Any] = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

        model_id = str(state.get("active_model") or "")
        if not model_id or model_id not in self._specs:
            return None
        try:
            self.activate(model_id)
            return model_id
        except Exception as exc:
            log.warning("Oxirgi model '%s' tiklanmadi: %s", model_id, exc)
            return None


def _detect_memory_gb() -> float:
    """Tizim xotirasi hajmi (GB)."""
    import subprocess

    try:
        out = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5
        )
        if out.returncode == 0:
            return int(out.stdout.strip()) / (1024**3)
    except Exception:
        pass
    try:
        import os

        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024**3)
    except Exception:
        return 16.0
