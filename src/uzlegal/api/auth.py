"""API autentifikatsiyasi va so'rov chastotasi cheklovi.

## Nima uchun bu modul kerak edi

`configs/profiles/server.yaml` da siyosat ALLAQACHON yozilgan edi:

    api:
      auth: api_key
      rate_limit:
        per_key_daily: 1000
        per_ip_minute: 60

Lekin kod bu maydonlarni hech qachon o'qimasdi. Natijada `server`
profilida ishga tushirilgan API ham butunlay ochiq bo'lardi. Tekshirib
ko'rilgan: `POST /v1/admin/users` — foydalanuvchi yaratish — va
`POST /v1/admin/users/{id}/regenerate-key` — kalitni qayta yaratish —
hech qanday kalitsiz javob berardi.

Ya'ni bu modul yangi siyosat o'ylab topmaydi. U mavjud siyosatni
**bajaradi**.

## Ikki daraja

| Daraja | Kim uchun | Qachon talab qilinadi |
|--------|-----------|------------------------|
| Foydalanuvchi kaliti | `/v1/consult`, `/v1/search`, … | `auth: api_key` bo'lganda |
| Admin kaliti | `/v1/admin/*` | **DOIM** |

Admin darajasi profilga bog'liq emas va bu ataylab. `local-dev` da ham
foydalanuvchi yaratish va kalit qayta tiklash ochiq turishi kerak emas:
port 127.0.0.1 ga bog'langan bo'lsa ham, mashinadagi har qanday jarayon
(brauzerdagi sahifa ham) unga murojaat qila oladi.

Admin kaliti sozlanmagan bo'lsa — `/v1/admin/*` **503** qaytaradi, ochiq
qolmaydi. «Sozlanmagan» hech qachon «hammaga ruxsat» degani emas.

## Rate-limit haqida halol ogohlantirish

Hisoblagich **jarayon xotirasida**. Bitta `uvicorn` ishchisi uchun to'g'ri
ishlaydi. Bir necha ishchi yoki bir necha nusxa bo'lsa, har biri o'z
hisobini yuritadi va amaldagi chegara ishchilar soniga ko'payadi. Haqiqiy
ishlab chiqarishda bu Redis ga ko'chirilishi kerak — hozir shunday emas
va buni bilib turish yashirishdan yaxshiroq.

Kunlik kalit chegarasi esa `UserStore` dagi haqiqiy foydalanish hisobiga
tayanadi (SQLite), shuning uchun u qayta ishga tushirishdan omon qoladi.
"""

from __future__ import annotations

import hmac
import logging
import os
import time
from collections import deque
from threading import Lock
from typing import TYPE_CHECKING, Any

from fastapi import Header, HTTPException, Request

from uzlegal.config import get_settings

if TYPE_CHECKING:
    from uzlegal.users.models import User

log = logging.getLogger(__name__)

ADMIN_KEY_ENV = "UZLEGAL_ADMIN_KEY"
STATIC_KEYS_ENV = "UZLEGAL_API_KEYS"


# --------------------------------------------------------------------------- #
# Kalitlar
# --------------------------------------------------------------------------- #


def _admin_key() -> str | None:
    key = os.getenv(ADMIN_KEY_ENV, "").strip()
    return key or None


def _static_keys() -> set[str]:
    """`UZLEGAL_API_KEYS` — vergul bilan ajratilgan statik kalitlar.

    Bular `UserStore` dan mustaqil: integratsiya va monitoring uchun
    foydalanuvchi yozuvisiz kalit kerak bo'ladi. Ularga reja limitlari
    qo'llanmaydi, faqat IP chastotasi.
    """
    raw = os.getenv(STATIC_KEYS_ENV, "")
    return {k.strip() for k in raw.split(",") if k.strip()}


def _matches(candidate: str, expected: str) -> bool:
    """Doimiy vaqtli taqqoslash — vaqt bo'yicha hujumni yopadi."""
    return hmac.compare_digest(candidate, expected)


def _presented_key(authorization: str | None, x_api_key: str | None) -> str | None:
    """Kalitni ikkala odatiy joydan qidiradi.

    `Authorization: Bearer …` — OpenAI-mos mijozlar shunday yuboradi.
    `X-API-Key` — oddiy `curl` va web qobiq uchun qulayroq.
    """
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


# --------------------------------------------------------------------------- #
# IP chastotasi
# --------------------------------------------------------------------------- #


class _IpLimiter:
    """Bir daqiqalik siljuvchi oyna, IP bo'yicha."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, ip: str, per_minute: int) -> None:
        if per_minute <= 0:
            return
        now = time.monotonic()
        with self._lock:
            window = self._hits.setdefault(ip, deque())
            while window and now - window[0] > 60.0:
                window.popleft()
            if len(window) >= per_minute:
                retry = int(60.0 - (now - window[0])) + 1
                raise HTTPException(
                    429,
                    detail=f"Juda ko'p so'rov. {retry} soniyadan keyin urinib ko'ring.",
                    headers={"Retry-After": str(retry)},
                )
            window.append(now)

            # Faol bo'lmagan IP larni tozalash — aks holda lug'at cheksiz
            # o'sadi va bu xotira sizishi bo'lardi.
            if len(self._hits) > 10_000:
                stale = [k for k, v in self._hits.items() if not v or now - v[-1] > 300]
                for k in stale:
                    del self._hits[k]


_ip_limiter = _IpLimiter()


def _client_ip(request: Request) -> str:
    """Mijoz IP si.

    `X-Forwarded-For` ISHONCHSIZ va shuning uchun ATAYLAB o'qilmaydi:
    uni mijozning o'zi yozadi, ya'ni chegarani chetlab o'tish uchun har
    so'rovda boshqa qiymat yuborish yetarli. Teskari proksi ortida
    ishlatilganda proksi haqiqiy IP ni o'zi qo'yishi kerak (masalan
    `uvicorn --proxy-headers` bilan, u ishonchli proksilar ro'yxatini
    tekshiradi).
    """
    return request.client.host if request.client else "unknown"


# --------------------------------------------------------------------------- #
# FastAPI bog'liqliklari
# --------------------------------------------------------------------------- #


ADMIN_PREFIX = "/v1/admin/"

# Kalitsiz ochiq qoladigan marshrutlar.
#
# `/v1/health` va `/v1/meta` — monitoring uchun: uptime tekshiruvchi
# kalit yubora olmaydi va salomatlik tekshiruvi hech qanday maxfiy
# ma'lumot bermaydi. `/v1/plans` — narx ro'yxati, u ommaviy.
# Hujjatlar (`/docs`, `/openapi.json`) shartnomani tasvirlaydi, ma'lumot
# bermaydi.
#
# `/v1/passport/verify` — javob pasportini tekshirish (docs/21 § 4.7).
# Pasportni ko'rsatgan tomon odatda tizim mijozi EMAS: sud, qarshi tomon
# vakili yoki tekshiruvchi. Ularda API kaliti yo'q va bo'lmaydi ham.
# Marshrut hech narsa oshkor qilmaydi — pasportda savol ham, javob matni
# ham yo'q, faqat xeshi.
PUBLIC_PATHS = frozenset(
    {
        "/v1/health",
        "/v1/meta",
        "/v1/plans",
        "/v1/passport/verify",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/",
    }
)

# Marshrut → reja imkoniyati. `users/limits.py` dagi nomlar bilan bir xil.
_PATH_FEATURE: tuple[tuple[str, str], ...] = (
    ("/v1/consult", "consult"),
    ("/v1/search", "consult"),
    ("/v1/court/analyze", "court_analyze"),
    ("/v1/litigation/", "litigation"),
    ("/v1/integrity/", "integrity"),
    ("/v1/education", "education"),
    ("/v1/generate", "consult"),
)


def _feature_for(path: str) -> str:
    for prefix, feature in _PATH_FEATURE:
        if path.startswith(prefix):
            return feature
    return ""


async def access_control(request: Request, call_next: Any) -> Any:
    """Har bir so'rov uchun kirish nazorati.

    Tartib ataylab shunday:

    1. Ommaviy marshrutlar — hech narsa tekshirilmaydi
    2. `/v1/admin/*` — admin kaliti, profildan qat'iy nazar
    3. Qolganlari — IP chastotasi, so'ng (kerak bo'lsa) foydalanuvchi
       kaliti va reja chegarasi

    IP chastotasi kalitdan OLDIN tekshiriladi: aks holda noto'g'ri kalit
    bilan cheksiz urinish mumkin bo'lardi va bu kalitni topish yo'liga
    aylanardi.
    """
    from fastapi.responses import JSONResponse

    path = request.url.path

    if path in PUBLIC_PATHS or path.startswith("/static"):
        return await call_next(request)

    authorization = request.headers.get("authorization")
    x_api_key = request.headers.get("x-api-key")

    try:
        if path.startswith(ADMIN_PREFIX):
            require_admin(authorization, x_api_key)
        else:
            user = require_user(request, authorization, x_api_key)
            feature = _feature_for(path)
            if feature:
                enforce_plan(user, feature)
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    return await call_next(request)


def require_admin(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Admin kalitini talab qiladi. Profildan QAT'IY NAZAR.

    Kalit sozlanmagan bo'lsa 503 — marshrut ochiq qolmaydi.
    """
    expected = _admin_key()
    if expected is None:
        log.error("%s sozlanmagan — admin endpointlari o'chirilgan", ADMIN_KEY_ENV)
        raise HTTPException(
            503,
            detail=(
                f"Admin endpointlari o'chirilgan: {ADMIN_KEY_ENV} sozlanmagan. "
                f"Yoqish uchun muhitga kuchli tasodifiy kalit qo'ying."
            ),
        )

    presented = _presented_key(authorization, x_api_key)
    if not presented or not _matches(presented, expected):
        raise HTTPException(401, detail="Admin kaliti noto'g'ri yoki berilmagan")


def require_user(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> User | None:
    """Ommaviy endpointlar uchun kirish nazorati.

    `auth: none` (local-dev) — kalit talab qilinmaydi, lekin berilgan
    bo'lsa baribir tanib olinadi: shunda reja limitlari va foydalanish
    hisobi lokal sinovda ham ishlaydi.

    Qaytaradi: tanilgan foydalanuvchi yoki `None` (anonim/statik kalit).
    """
    settings = get_settings()
    required = settings.api_auth == "api_key"

    per_minute = int(settings.rate_limit.get("per_ip_minute") or 0)
    _ip_limiter.check(_client_ip(request), per_minute)

    presented = _presented_key(authorization, x_api_key)

    if presented is None:
        if required:
            raise HTTPException(401, detail="API kaliti kerak (X-API-Key yoki Bearer)")
        return None

    # Admin kaliti hamma joyda ishlaydi — monitoring va nosozlik qidirish
    # uchun alohida foydalanuvchi yozuvi ochish shart bo'lmasin.
    admin = _admin_key()
    if admin and _matches(presented, admin):
        return None

    if any(_matches(presented, k) for k in _static_keys()):
        return None

    user = _lookup_user(presented)
    if user is None:
        raise HTTPException(401, detail="API kaliti noto'g'ri")
    if not user.is_active:
        raise HTTPException(403, detail="Hisob faol emas")
    return user


def _lookup_user(api_key: str) -> User | None:
    from uzlegal.users.models import UserNotFoundError

    try:
        from uzlegal.api.app import _get_store
    except ImportError:  # pragma: no cover — faqat aylanma import holatida
        return None

    try:
        return _get_store().get_by_api_key(api_key)
    except UserNotFoundError:
        return None
    except Exception as exc:  # pragma: no cover
        log.warning("Foydalanuvchi bazasi o'qilmadi: %s", exc)
        return None


def enforce_plan(user: User | None, feature: str) -> None:
    """Reja cheklovlarini majburlaydi va foydalanishni yozadi.

    Foydalanuvchi anonim bo'lsa (`auth: none` yoki statik kalit) —
    hech narsa qilinmaydi. Rejalar faqat ro'yxatdan o'tgan hisoblarga
    tegishli.

    `users/limits.py` allaqachon shu mantiqni saqlaydi; bu yerda faqat
    HTTP qatlamiga bog'lanadi — modul ilgari yozilgan, lekin API dan
    hech qachon chaqirilmasdi.
    """
    if user is None:
        return

    from uzlegal.users.limits import FeatureNotAllowedError, record_and_check
    from uzlegal.users.models import QuotaExceededError

    try:
        from uzlegal.api.app import _get_store

        record_and_check(_get_store(), user.user_id, feature)
    except FeatureNotAllowedError as exc:
        # 403 — reja bu imkoniyatni umuman bermaydi. Qayta urinish
        # yordam bermaydi, rejani ko'tarish kerak.
        raise HTTPException(403, detail=str(exc)) from None
    except QuotaExceededError as exc:
        # 429 — chegara vaqtinchalik. Ertaga (yoki keyingi oyda) o'tadi.
        raise HTTPException(429, detail=str(exc)) from None
    except HTTPException:
        raise
    except Exception as exc:
        # Limit tekshiruvi so'rovni YIQITMASLIGI kerak: hisob yuritish
        # xatosi foydalanuvchini xizmatsiz qoldirmaydi. Lekin u jimgina
        # o'tmaydi ham — log da qoladi.
        log.warning("Limit tekshiruvi bajarilmadi (%s): %s", feature, exc)


def auth_status() -> dict[str, Any]:
    """Diagnostika uchun: qanday himoya yoqilgan (kalitlarni oshkor qilmasdan)."""
    settings = get_settings()
    return {
        "auth": settings.api_auth,
        "admin_key_configured": _admin_key() is not None,
        "static_keys": len(_static_keys()),
        "rate_limit": settings.rate_limit or None,
    }
