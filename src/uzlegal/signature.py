"""Mualliflik va foydalanish litsenziyasi — yagona haqiqat manbai.

Bu modul ikki narsani beradi:

1. **Mualliflik ma'lumoti** — CLI banneri, API sarlavhalari, MCP va bot
   bir xil manbadan oladi. Ismni ikki joyda yozish uni ikkiga ajratadi.
2. **Foydalanish litsenziyasi** — xizmatni ishga tushirish uchun muallif
   imzolagan token talab qilinadi.

## Litsenziya qanday ishlaydi

Ed25519 **ochiq kalitli** imzo. Muallif litsenziyani **maxfiy kaliti**
bilan imzolaydi; kodda esa faqat **ochiq kalit** turadi.

    muallif mashinasi                    har qanday o'rnatma
    ─────────────────                    ──────────────────
    maxfiy kalit  ──imzolaydi──►  token  ──tekshiradi──►  ochiq kalit

Bu shuni anglatadiki:

* kodni o'qigan odam **litsenziya yasay olmaydi** — maxfiy kalit unda yo'q;
* ochiq kalitni kodda saqlash xavfsiz — u ataylab ommaviy;
* muallif litsenziya bera oladi va uni **muddat bilan cheklashi** mumkin.

Token shakli:

    uzlegal-lic.v1.<base64url(payload)>.<base64url(imzo)>

`payload` — JSON: kimga berilgan, qachon, qachongacha, qaysi
imkoniyatlarga.

## Nimani himoya qiladi va nimani himoya QILMAYDI

Bu mexanizm **javobgarlikni** va **kim ruxsat olganini** belgilaydi:
litsenziyasiz ishga tushirilgan nusxa buni ochiq aytadi va xizmat
ko'rsatmaydi.

U kodni **o'qishdan** yoki tekshiruvni kod ichidan **olib tashlashdan**
himoya qilmaydi — manba kodi ochiq bo'lgan har qanday loyihada bu
printsipial ravishda mumkin emas. Himoyaning huquqiy qismi litsenziya
matni va mualliflik huquqi bilan ta'minlanadi, texnik qismi esa
**halol foydalanuvchi tasodifan noto'g'ri ishlatmasligini** va
**kim ruxsat olganini isbotlash** imkonini beradi.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

# --------------------------------------------------------------------------- #
# Mualliflik
# --------------------------------------------------------------------------- #

PROJECT = "UzLegal-AI"
AUTHOR = "Shokirjon Madaminov"
AUTHOR_HANDLE = "ShokirjonMK"
DEVELOPER = "MKdev"
CONTACT = "@ceoNeuron"
REPOSITORY = "https://github.com/ShokirjonMK/uzlegal-ai"

# Barcha tan olinadigan imzo kalitlari — hujjat va tekshiruv uchun.
AUTHOR_KEYS: tuple[str, ...] = ("ShokirjonMK", "MKdev", "mk", "@ceoNeuron")

# Muallifning Ed25519 ochiq kaliti (`SIGNATURE.md` dagi bilan bir xil).
# Ochiq kalit — ataylab ommaviy; u bilan faqat TEKSHIRISH mumkin.
PUBLIC_KEY_SSH = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICW+kZ5h4kDz2z7a9FyWgoAnf5Yx3SnuTg4yKDrzz6iD"
PUBLIC_KEY_FINGERPRINT = "SHA256:R4s0AF7cVC018xjK1s3jLusb67r/JoLXFqYKo2WlHkI"

LICENSE_ENV = "UZLEGAL_LICENSE"
LICENSE_FILE_ENV = "UZLEGAL_LICENSE_FILE"
TOKEN_PREFIX = "uzlegal-lic.v1."


def attribution() -> dict[str, str]:
    """API sarlavhalari va `/v1/meta` uchun mualliflik ma'lumoti."""
    return {
        "project": PROJECT,
        "author": AUTHOR,
        "author_handle": AUTHOR_HANDLE,
        "developer": DEVELOPER,
        "contact": CONTACT,
        "repository": REPOSITORY,
        "key_fingerprint": PUBLIC_KEY_FINGERPRINT,
    }


def response_headers() -> dict[str, str]:
    """Har bir HTTP javobiga qo'shiladigan mualliflik sarlavhalari."""
    return {
        "X-Author": f"{AUTHOR} ({AUTHOR_HANDLE})",
        "X-Developer": DEVELOPER,
        "X-Contact": CONTACT,
        "X-Project": PROJECT,
        "X-Key-Fingerprint": PUBLIC_KEY_FINGERPRINT,
    }


def banner() -> str:
    """CLI da ko'rsatiladigan qisqa mualliflik satri."""
    return f"{PROJECT} · {AUTHOR} ({AUTHOR_HANDLE} · {DEVELOPER} · {CONTACT})"


# --------------------------------------------------------------------------- #
# Litsenziya
# --------------------------------------------------------------------------- #


class LicenseError(RuntimeError):
    """Litsenziya yo'q, buzilgan yoki muddati o'tgan."""


@dataclass(frozen=True)
class License:
    """Tekshirilgan litsenziya.

    `raw` saqlanadi — audit jurnaliga aynan qaysi token ishlatilgani
    yozilishi kerak, qayta qurilgani emas.
    """

    licensee: str
    issued: date
    expires: date | None
    scope: tuple[str, ...]
    note: str
    raw: str

    @property
    def is_expired(self) -> bool:
        """Muddat **UTC** sanasi bo'yicha tekshiriladi.

        Soat tanlovi ataylab qayd etiladi: mahalliy sana mashinaning
        vaqt mintaqasiga bog'liq va bir xil litsenziya ikki serverda
        turlicha baholanardi. UTC esa hamma joyda bir xil.

        Amaliy oqibat: UTC+5 da (Toshkent) litsenziya e'lon qilingan
        sanadan besh soat ko'proq amal qiladi. Bu mijoz foydasiga va
        zarari yo'q — teskarisi (erta o'chib qolish) zararli bo'lardi.

        Testlar ham shu soatni ishlatishi shart (`tests/unit/
        test_signature.py::bugun`). 2026-08-21 da ular mahalliy sanani
        ishlatgani uchun to'plam sababsiz yiqildi.
        """
        return self.expires is not None and datetime.now(UTC).date() > self.expires

    @property
    def days_left(self) -> int | None:
        if self.expires is None:
            return None
        return (self.expires - datetime.now(UTC).date()).days

    def allows(self, capability: str) -> bool:
        """`scope` bo'sh yoki `*` bo'lsa — barcha imkoniyatlar."""
        return not self.scope or "*" in self.scope or capability in self.scope

    def summary(self) -> str:
        muddat = "muddatsiz" if self.expires is None else f"{self.expires} gacha"
        return f"{self.licensee} · {muddat}"


def _b64url_decode(data: str) -> bytes:
    """base64url dekodlash — **qat'iy** tekshiruv bilan.

    `validate=True` majburiy. Usiz Python alifboga kirmaydigan
    belgilarni JIMGINA tashlab yuboradi: `"!!!"` bo'sh baytlarga
    aylanadi va keyin imzo tekshiruvi «bu litsenziyani muallif
    bermagan» deb xato beradi. Tashxis noto'g'ri bo'ladi — token
    umuman soxta emas, u shunchaki buzuq. Bunday xabar sozlamani
    tuzatayotgan odamni noto'g'ri yo'lga solib yuboradi.
    """
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _b64url_decode_strict(data: str) -> bytes:
    return base64.b64decode(
        data.replace("-", "+").replace("_", "/") + "=" * (-len(data) % 4), validate=True
    )


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _public_key() -> Any:
    """SSH formatidagi ochiq kalitni Ed25519 obyektiga aylantiradi."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    body = _b64url_decode(PUBLIC_KEY_SSH.split()[1].replace("+", "-").replace("/", "_"))
    # SSH wire formati: <uzunlik><"ssh-ed25519"><uzunlik><32 baytlik kalit>
    offset = 4 + int.from_bytes(body[:4], "big")
    key_len = int.from_bytes(body[offset : offset + 4], "big")
    raw = body[offset + 4 : offset + 4 + key_len]
    return Ed25519PublicKey.from_public_bytes(raw)


def parse_license(token: str) -> License:
    """Tokenni tekshiradi va litsenziyani qaytaradi.

    Har qanday nosozlik — `LicenseError`. Sabab aniq aytiladi: noto'g'ri
    sozlangan o'rnatmani tuzatish mumkin, «nimadir xato» esa yo'q.
    """
    token = token.strip()
    if not token.startswith(TOKEN_PREFIX):
        raise LicenseError(f"Token shakli noto'g'ri — «{TOKEN_PREFIX}…» bilan boshlanishi kerak")

    body = token[len(TOKEN_PREFIX) :]
    parts = body.split(".")
    if len(parts) != 2:
        raise LicenseError("Token buzilgan — payload va imzo qismlari ajratilmadi")

    payload_b64, signature_b64 = parts
    try:
        payload_raw = _b64url_decode_strict(payload_b64)
        signature = _b64url_decode_strict(signature_b64)
    except Exception as exc:
        raise LicenseError(f"Token o'qilmadi — base64 buzilgan: {exc}") from exc

    if len(signature) != 64:
        # Ed25519 imzosi doim 64 bayt. Boshqa uzunlik — token buzilgan,
        # soxta emas; xabar shuni aytishi kerak.
        raise LicenseError(
            f"Token o'qilmadi — imzo uzunligi noto'g'ri ({len(signature)} bayt, 64 kutilgan)"
        )

    try:
        from cryptography.exceptions import InvalidSignature

        _public_key().verify(signature, payload_raw)
    except ImportError as exc:  # pragma: no cover
        raise LicenseError(
            "`cryptography` o'rnatilmagan — litsenziyani tekshirib bo'lmaydi. "
            "O'rnatish: pip install cryptography"
        ) from exc
    except InvalidSignature as exc:
        raise LicenseError(
            "Imzo noto'g'ri — bu litsenziya muallif tomonidan berilmagan. "
            f"Muallif: {AUTHOR} ({CONTACT})"
        ) from exc

    try:
        data = json.loads(payload_raw.decode("utf-8"))
    except Exception as exc:
        raise LicenseError(f"Payload JSON emas: {exc}") from exc

    licensee = str(data.get("licensee") or "").strip()
    if not licensee:
        raise LicenseError("Litsenziyada `licensee` ko'rsatilmagan")

    try:
        issued = date.fromisoformat(str(data["issued"]))
        expires = date.fromisoformat(str(data["expires"])) if data.get("expires") else None
    except Exception as exc:
        raise LicenseError(f"Sana maydonlari noto'g'ri: {exc}") from exc

    license_ = License(
        licensee=licensee,
        issued=issued,
        expires=expires,
        scope=tuple(str(s) for s in (data.get("scope") or ())),
        note=str(data.get("note") or ""),
        raw=token,
    )

    if license_.is_expired:
        raise LicenseError(
            f"Litsenziya muddati tugagan ({license_.expires}). "
            f"Yangilash uchun murojaat qiling: {CONTACT}"
        )
    return license_


def load_license() -> License | None:
    """Muhitdan litsenziyani o'qiydi. Yo'q bo'lsa `None`, buzuq bo'lsa xato.

    Tartib: `UZLEGAL_LICENSE` → `UZLEGAL_LICENSE_FILE` → `license.key`.

    «Yo'q» va «buzuq» ATAYLAB farqlanadi: birinchisi sozlanmagan
    o'rnatma, ikkinchisi esa soxta yoki muddati o'tgan token va u
    jimgina o'tmasligi kerak.
    """
    token = os.getenv(LICENSE_ENV, "").strip()
    if not token:
        from pathlib import Path

        path_str = os.getenv(LICENSE_FILE_ENV, "").strip()
        path = Path(path_str) if path_str else Path("license.key")
        if path.exists():
            token = path.read_text(encoding="utf-8").strip()

    if not token:
        return None
    return parse_license(token)


def require_license(capability: str) -> License:
    """Xizmatni ishga tushirish uchun amaldagi litsenziyani talab qiladi.

    `uzlegal serve`, `uzlegal bot`, `uzlegal mcp` shu funksiyani
    chaqiradi. Litsenziyasiz ular ishga tushmaydi.
    """
    license_ = load_license()
    if license_ is None:
        raise LicenseError(
            f"Foydalanish litsenziyasi yo'q.\n\n"
            f"{PROJECT} — {AUTHOR} ({AUTHOR_HANDLE}) ning mualliflik ishi. "
            f"Xizmatni ishga tushirish uchun muallif bergan litsenziya kerak.\n"
            f"Murojaat: {CONTACT} · {REPOSITORY}\n\n"
            f"Litsenziya olgach:\n"
            f"  {LICENSE_ENV}=uzlegal-lic.v1.…   (yoki `license.key` fayli)"
        )
    if not license_.allows(capability):
        raise LicenseError(
            f"«{capability}» bu litsenziyada ruxsat etilmagan "
            f"(ruxsat: {', '.join(license_.scope) or 'yo‘q'}). Murojaat: {CONTACT}"
        )
    return license_


def license_status() -> dict[str, Any]:
    """Diagnostika uchun — tokenning o'zini oshkor qilmasdan."""
    try:
        license_ = load_license()
    except LicenseError as exc:
        return {"valid": False, "error": str(exc).split("\n")[0]}
    if license_ is None:
        return {"valid": False, "error": "litsenziya sozlanmagan"}
    return {
        "valid": True,
        "licensee": license_.licensee,
        "issued": license_.issued.isoformat(),
        "expires": license_.expires.isoformat() if license_.expires else None,
        "days_left": license_.days_left,
        "scope": list(license_.scope) or ["*"],
    }


# --------------------------------------------------------------------------- #
# Litsenziya berish — faqat muallif mashinasida
# --------------------------------------------------------------------------- #


def issue_license(
    licensee: str,
    *,
    private_key_path: str,
    expires: date | None = None,
    scope: tuple[str, ...] = (),
    note: str = "",
) -> str:
    """Yangi litsenziya tokeni yasaydi va uni maxfiy kalit bilan imzolaydi.

    Maxfiy kalit faqat muallifda, shuning uchun bu funksiya boshqa
    mashinada ishlamaydi — aynan shu narsa tizimni himoya qiladi.

    Parol bilan himoyalangan kalitlar qo'llab-quvvatlanadi:
    `UZLEGAL_KEY_PASSPHRASE`.
    """
    from pathlib import Path

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import load_ssh_private_key

    key_bytes = Path(private_key_path).read_bytes()
    passphrase = os.getenv("UZLEGAL_KEY_PASSPHRASE", "").encode() or None
    private_key = load_ssh_private_key(key_bytes, password=passphrase)

    # `load_ssh_private_key` RSA, ECDSA yoki Ed25519 qaytarishi mumkin va
    # ularning `sign()` imzolari boshqacha. Bu yerda faqat Ed25519 to'g'ri:
    # tekshiruv tomoni ham Ed25519. Aks holda token yasaladi, lekin hech
    # qachon tekshiruvdan o'tmaydi — xato foydalanuvchiga yetib borardi.
    if not isinstance(private_key, Ed25519PrivateKey):
        raise LicenseError(
            f"Kalit turi mos emas: {type(private_key).__name__}. "
            f"Ed25519 kerak — `ssh-keygen -t ed25519` bilan yaratiladi."
        )

    payload = {
        "licensee": licensee,
        "issued": datetime.now(UTC).date().isoformat(),
        "expires": expires.isoformat() if expires else None,
        "scope": list(scope),
        "note": note,
        "issuer": f"{AUTHOR} ({AUTHOR_HANDLE})",
    }
    # `sort_keys` + ixcham ajratuvchilar: bir xil payload har doim bir xil
    # baytlarga aylanishi kerak, aks holda imzo takrorlanmaydi.
    payload_raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload_bytes = payload_raw.encode("utf-8")
    signature = private_key.sign(payload_bytes)

    return f"{TOKEN_PREFIX}{_b64url_encode(payload_bytes)}.{_b64url_encode(signature)}"


__all__ = [
    "AUTHOR",
    "AUTHOR_HANDLE",
    "AUTHOR_KEYS",
    "CONTACT",
    "DEVELOPER",
    "PROJECT",
    "PUBLIC_KEY_FINGERPRINT",
    "License",
    "LicenseError",
    "attribution",
    "banner",
    "issue_license",
    "license_status",
    "load_license",
    "parse_license",
    "require_license",
    "response_headers",
]
