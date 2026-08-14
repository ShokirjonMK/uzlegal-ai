"""Javob pasporti — maslahatning tekshirib bo'ladigan qabul xati (docs/21 § 4).

Audit jurnali javobni **ichkarida** hujjatlashtiradi: u xizmatni yuritgan
tomonda qoladi va uni faqat o'sha tomon ko'rsata oladi. Nizoda esa
javobni **tashqariga** olib chiqqan odam kerak: mijoz, yurist yoki sud
qo'lida shunchaki matn bo'ladi va u matn haqiqatan shu tizim tomonidan,
shu manbalar asosida berilganini isbotlab bo'lmaydi.

Pasport aynan shu bo'shliqni yopadi: u javob bilan birga beriladigan,
o'z-o'zini tasdiqlaydigan qisqa token.

    javob matni  ─sha256─►  pasport  ─Ed25519 imzo─►  token
                                                       │
    keyinroq, boshqa joyda:  token + javob matni ──────┴──► «ha, aynan shu»

## Nima uchun `signature.py` dagi kalit YARAMAYDI

`signature.py` — **litsenziya** tizimi: uning maxfiy kaliti faqat
muallif mashinasida turadi va repoda umuman yo'q (`signature.py` § izohi).
Xizmat esa har bir javobga imzo qo'yishi kerak — ya'ni imzolash kaliti
**ishlayotgan nusxada** bo'lishi shart. Bu ikki kalitning maqsadi ham
qarama-qarshi:

| | Litsenziya kaliti | Pasport kaliti |
|---|---|---|
| Kimda | faqat muallifda | har bir joylashtirmada |
| Nimani isbotlaydi | «bu nusxaga ruxsat berilgan» | «bu javobni shu nusxa bergan» |

Shuning uchun pasport uchun **alohida, joylashtirishga xos** kalit
yaratiladi. Ular birlashtirilsa: yo muallif kaliti hamma serverga
tarqalardi (litsenziya tizimi qulardi), yo javoblar imzosiz qolardi.

## Pasportda nima YO'Q

**Savol ham, javob matni ham yo'q** — faqat ularning sha256 xeshi
(`audit.py` shu tamoyilga allaqachon amal qiladi). Sabab oddiy: pasport
javob bilan birga tarqaydi va uni saqlab qo'ygan har kim uni o'qiy
oladi. Xesh esa da'voni isbotlash uchun yetarli — matn qo'lida bo'lgan
odam uni qayta xeshlab taqqoslaydi, matni yo'q odam esa pasportdan
hech narsa bilib ololmaydi.

## Kalit boshqaruvi

Tartib (docs/21 § 4.3):

1. `UZLEGAL_PASSPORT_KEY` — PEM matni to'g'ridan-to'g'ri muhitda
   (konteynerlar va sirlar ombori uchun);
2. `UZLEGAL_PASSPORT_KEY_FILE` — kalit fayli yo'li;
3. `data/keys/passport_ed25519` — birinchi ishlatishda **avtomatik**
   yaratiladi va bu haqda ogohlantirish chiqadi.

Kalit parolsiz saqlanadi va bu ataylab: xizmat pasportni odam
aralashuvisiz imzolaydi, parol so'ralsa u birinchi qayta ishga
tushirishdayoq to'xtab qolardi. Himoya fayl huquqlari va `.gitignore`
bilan ta'minlanadi.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from uzlegal.config import DATA_DIR

# Kanonik shakl va base64url — `signature.py` dagi bilan **ayni**.
# Ikkinchi nusxa yozilsa ular vaqt o'tib bir-biridan ajralib ketardi va
# bir joyda yasalgan token boshqa joyda o'qilmay qolardi.
from uzlegal.signature import _b64url_decode_strict, _b64url_encode

log = logging.getLogger(__name__)

VERSION = "uzlegal-pass.v1"
TOKEN_PREFIX = f"{VERSION}."

KEY_ENV = "UZLEGAL_PASSPORT_KEY"
KEY_FILE_ENV = "UZLEGAL_PASSPORT_KEY_FILE"
DEFAULT_KEY_PATH = DATA_DIR / "keys" / "passport_ed25519"

# Ed25519 imzosi doim shuncha bayt.
SIGNATURE_BYTES = 64


class PassportError(RuntimeError):
    """Pasport yo'q, buzilgan yoki bu tizim tomonidan berilmagan."""


@dataclass(frozen=True)
class Passport:
    """Tekshirilgan pasport.

    `raw` saqlanadi: tekshiruv natijasini yozib qo'yayotgan tomon aynan
    qaysi token ko'rsatilganini bilishi kerak, qayta qurilganini emas.
    """

    version: str
    trace_id: str
    issued_at: str
    question_hash: str
    answer_hash: str
    citations: tuple[str, ...]
    kb_version: str
    model_version: str | None
    as_of: str | None
    gate: dict[str, Any]
    key_fingerprint: str
    raw: str

    def matches_question(self, question: str) -> bool:
        """Qo'ldagi savol matni pasportdagi xeshga mos keladimi."""
        return _sha256(question) == self.question_hash

    def matches_answer(self, answer: str) -> bool:
        """Qo'ldagi javob matni pasportdagi xeshga mos keladimi.

        Nizoda asosiy savol shu bo'ladi: «tizim aynan shuni aytganmi?».
        """
        return _sha256(answer) == self.answer_hash

    def as_dict(self) -> dict[str, Any]:
        """Pasport mazmuni — API javobi va CLI chiqishi uchun.

        `raw` kiritilmaydi: uni so'ragan tomon o'zi bergan.
        """
        return {
            "version": self.version,
            "trace_id": self.trace_id,
            "issued_at": self.issued_at,
            "question_hash": self.question_hash,
            "answer_hash": self.answer_hash,
            "citations": list(self.citations),
            "kb_version": self.kb_version,
            "model_version": self.model_version,
            "as_of": self.as_of,
            "gate": dict(self.gate),
            "key_fingerprint": self.key_fingerprint,
        }

    def summary(self) -> str:
        return f"{self.trace_id} · {self.issued_at} · {len(self.citations)} ta manba"


# --------------------------------------------------------------------------- #
# Kalit
# --------------------------------------------------------------------------- #


def key_path() -> Path:
    """Kalit fayli yo'li — muhitdan yoki standart joydan."""
    override = os.getenv(KEY_FILE_ENV, "").strip()
    return Path(override) if override else DEFAULT_KEY_PATH


def _key_material() -> bytes | None:
    """Kalit baytlari: avval muhit o'zgaruvchisi, keyin fayl. Yo'q bo'lsa `None`."""
    pem = os.getenv(KEY_ENV, "").strip()
    if pem:
        return pem.encode("utf-8")

    path = key_path()
    if path.exists():
        return path.read_bytes()
    return None


def _parse_private_key(material: bytes) -> Any:
    """PEM yoki OpenSSH formatidagi Ed25519 maxfiy kalitni o'qiydi.

    Ikkala format ham qabul qilinadi: kalitni odatda `ssh-keygen` bilan
    yasashadi, sirlar ombori esa PEM beradi. Boshqa turdagi kalit
    (RSA, ECDSA) darhol rad etiladi — u bilan token yasalardi, lekin
    tekshiruv tomoni Ed25519 bo'lgani uchun hech qachon o'tmasdi.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        load_pem_private_key,
        load_ssh_private_key,
    )

    # `Any` — ikkala yuklovchi ham har xil kalit turlaridan iborat
    # birlashma qaytaradi; keraklisini quyidagi tekshiruv ajratadi.
    key: Any
    if b"OPENSSH PRIVATE KEY" in material[:80]:
        key = load_ssh_private_key(material, password=None)
    else:
        key = load_pem_private_key(material, password=None)

    if not isinstance(key, Ed25519PrivateKey):
        raise PassportError(
            f"Pasport kaliti turi mos emas: {type(key).__name__}. "
            f"Ed25519 kerak — `ssh-keygen -t ed25519` bilan yaratiladi."
        )
    return key


def _restrict(path: Path) -> None:
    """Kalit faylini faqat egasiga ochiq qoldiradi.

    Windows da `chmod` amalda ishlamaydi va bu jimgina o'tadi — u yerda
    huquqlar ACL bilan boshqariladi. Shuning uchun bu chora yagona
    himoya emas: kalit `.gitignore` da ham bo'lishi shart.
    """
    try:
        os.chmod(path, 0o600)
    except OSError as exc:  # pragma: no cover — platformaga bog'liq
        log.debug("Kalit fayli huquqlari o'zgartirilmadi (%s): %s", path, exc)


def _generate_key(path: Path) -> Any:
    """Yangi joylashtirma kalitini yaratadi va faylga yozadi.

    Bu jimgina bo'lmasligi kerak: yangi kalit — yangi shaxs. Eski
    pasportlar endi tekshirilmaydi, shuning uchun ogohlantirish va
    barmoq izi log ga chiqariladi (docs/21 § 4.3).
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    _restrict(path)

    log.warning(
        "Pasport kaliti topilmadi — yangisi yaratildi: %s (barmoq izi %s). "
        "Bu kalit shu o'rnatmaga xos: uni yo'qotish oldin berilgan barcha "
        "pasportlarni tekshirib bo'lmaydigan qiladi. Zaxira nusxasini oling "
        "va uni hech qachon repoga qo'ymang.",
        path,
        _fingerprint(key.public_key()),
    )
    return key


def _private_key(*, create: bool) -> Any:
    """Joylashtirma maxfiy kaliti.

    `create=True` — imzolash yo'li: kalit yo'q bo'lsa yaratiladi.
    `create=False` — tekshirish yo'li: kalit yo'q bo'lsa **yaratilmaydi**.
    Aks holda tekshiruvchi o'ziga yangi kalit yasab olardi va har bir
    haqiqiy pasportga «imzo noto'g'ri» deb javob berardi — sabab esa
    butunlay boshqa bo'lardi.
    """
    material = _key_material()
    if material is not None:
        return _parse_private_key(material)

    if not create:
        raise PassportError(
            f"Pasport kaliti topilmadi ({key_path()}) — bu nusxa pasportlarni "
            f"tekshira olmaydi. Kalitni pasportni bergan tizimdan oling yoki "
            f"{KEY_ENV} orqali ko'rsating."
        )
    return _generate_key(key_path())


def _public_ssh(public: Any) -> str:
    from cryptography.hazmat.primitives import serialization

    raw = public.public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
    return str(raw.decode())


def _fingerprint(public: Any) -> str:
    """OpenSSH uslubidagi barmoq izi — `ssh-keygen -lf` bergani bilan bir xil.

    Format `signature.PUBLIC_KEY_FINGERPRINT` bilan bir xil bo'lishi
    kerak: hujjatda va CLI da ikki xil ko'rinishdagi barmoq izi bo'lsa,
    ularni taqqoslash mumkinligiga hech kim ishonmaydi.
    """
    body = base64.b64decode(_public_ssh(public).split()[1])
    return "SHA256:" + base64.b64encode(hashlib.sha256(body).digest()).decode().rstrip("=")


def passport_public_key() -> str:
    """Joylashtirmaning ochiq kaliti — OpenSSH satri, izohida barmoq izi.

    Kalit hali bo'lmasa yaratiladi: «ochiq kalitni ko'rsat» so'rovi
    aslida «shu nusxaning shaxsini ayt» degani va shaxs shu yerda
    tug'iladi.
    """
    public = _private_key(create=True).public_key()
    return f"{_public_ssh(public)} {_fingerprint(public)}"


# --------------------------------------------------------------------------- #
# Berish
# --------------------------------------------------------------------------- #


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(payload: dict[str, Any]) -> bytes:
    """Kanonik JSON — `signature.py` dagi bilan ayni shakl.

    `sort_keys` va ixcham ajratuvchilar majburiy: bir xil mazmun har
    doim bir xil baytlarga aylanmasa, imzo takrorlanmaydi va tekshiruv
    tasodifiy yiqiladi.
    """
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return raw.encode("utf-8")


def issue_passport(
    *,
    trace_id: str,
    question: str,
    answer: str,
    citations: list[str],
    kb_version: str,
    model_version: str | None,
    as_of: date | None,
    gate: dict[str, Any] | None,
) -> str | None:
    """Javob uchun pasport tokenini yasaydi. Xato bo'lsa `None`.

    Bu funksiya **hech qachon so'rovni yiqitmasligi kerak**
    (`audit.py` dagi bilan bir xil qoida): kalit yo'q, disk to'la yoki
    `cryptography` o'rnatilmagan bo'lsa — foydalanuvchi javobsiz
    qolmaydi, faqat pasportsiz qoladi. Pasportning yo'qligi ko'rinadi,
    javobning yo'qligi esa xizmatni to'xtatadi.
    """
    try:
        key = _private_key(create=True)
        payload: dict[str, Any] = {
            "version": VERSION,
            "trace_id": trace_id,
            "issued_at": datetime.now(UTC).isoformat(),
            # Matnning O'ZI emas, xeshi — modul izohiga qarang.
            "question_hash": _sha256(question),
            "answer_hash": _sha256(answer),
            "citations": list(citations),
            "kb_version": kb_version,
            "model_version": model_version,
            "as_of": as_of.isoformat() if as_of else None,
            "gate": dict(gate or {}),
            "key_fingerprint": _fingerprint(key.public_key()),
        }
        payload_bytes = _canonical(payload)
        signature: bytes = key.sign(payload_bytes)
        return f"{TOKEN_PREFIX}{_b64url_encode(payload_bytes)}.{_b64url_encode(signature)}"
    except Exception as exc:
        log.error("Pasport berilmadi (%s): %s", trace_id, exc)
        return None


# --------------------------------------------------------------------------- #
# Tekshirish
# --------------------------------------------------------------------------- #


def _mismatch_reason(payload_raw: bytes, ours: str) -> str:
    """Imzo o'tmaganda aniq sabab.

    Payload bu yerda hali **ishonchsiz** va undan faqat tashxis uchun
    o'qiladi — hech qanday qaror unga tayanmaydi. Sababi: eng ko'p
    uchraydigan holat soxta token emas, balki pasportning boshqa
    o'rnatmada tekshirilishi. «Imzo noto'g'ri» degan xabar bunday
    holatda odamni soxtakorlik qidirishga yuborib, vaqtini yo'qotadi.
    """
    try:
        data = json.loads(payload_raw.decode("utf-8"))
        claimed = str(data.get("key_fingerprint") or "")
    except Exception:
        claimed = ""

    if claimed and claimed != ours:
        return (
            f"Imzo mos kelmadi — bu pasport boshqa o'rnatma kaliti bilan berilgan "
            f"(pasportda {claimed}, bu yerda {ours}). Uni bergan tizimda tekshiring."
        )
    return "Imzo noto'g'ri — pasport o'zgartirilgan yoki soxta"


def verify_passport(token: str) -> Passport:
    """Tokenni tekshiradi va pasportni qaytaradi.

    Har qanday nosozlik — `PassportError`, sababi aniq aytilgan holda:
    «buzilgan», «boshqa kalit bilan berilgan» va «soxta» — uch xil
    hodisa va ularga uch xil javob qaytariladi.
    """
    token = token.strip()
    if not token.startswith(TOKEN_PREFIX):
        raise PassportError(f"Token shakli noto'g'ri — «{TOKEN_PREFIX}…» bilan boshlanishi kerak")

    parts = token[len(TOKEN_PREFIX) :].split(".")
    if len(parts) != 2:
        raise PassportError("Token buzilgan — payload va imzo qismlari ajratilmadi")

    payload_b64, signature_b64 = parts
    try:
        payload_raw = _b64url_decode_strict(payload_b64)
        signature = _b64url_decode_strict(signature_b64)
    except Exception as exc:
        raise PassportError(f"Token o'qilmadi — base64 buzilgan: {exc}") from exc

    if len(signature) != SIGNATURE_BYTES:
        raise PassportError(
            f"Token o'qilmadi — imzo uzunligi noto'g'ri "
            f"({len(signature)} bayt, {SIGNATURE_BYTES} kutilgan)"
        )

    try:
        public = _private_key(create=False).public_key()
    except PassportError:
        raise
    except ImportError as exc:  # pragma: no cover
        raise PassportError(
            "`cryptography` o'rnatilmagan — pasportni tekshirib bo'lmaydi. "
            "O'rnatish: pip install cryptography"
        ) from exc
    except Exception as exc:
        raise PassportError(f"Pasport kaliti o'qilmadi: {exc}") from exc

    from cryptography.exceptions import InvalidSignature

    try:
        public.verify(signature, payload_raw)
    except InvalidSignature as exc:
        raise PassportError(_mismatch_reason(payload_raw, _fingerprint(public))) from exc

    try:
        data = json.loads(payload_raw.decode("utf-8"))
    except Exception as exc:
        raise PassportError(f"Payload JSON emas: {exc}") from exc

    if not isinstance(data, dict):
        raise PassportError("Payload obyekt emas — pasport shakli noto'g'ri")
    if data.get("version") != VERSION:
        raise PassportError(
            f"Pasport versiyasi qo'llab-quvvatlanmaydi: {data.get('version')!r} "
            f"({VERSION} kutilgan)"
        )

    return Passport(
        version=str(data["version"]),
        trace_id=str(data.get("trace_id") or ""),
        issued_at=str(data.get("issued_at") or ""),
        question_hash=str(data.get("question_hash") or ""),
        answer_hash=str(data.get("answer_hash") or ""),
        citations=tuple(str(c) for c in (data.get("citations") or ())),
        kb_version=str(data.get("kb_version") or ""),
        model_version=data.get("model_version"),
        as_of=data.get("as_of"),
        gate=dict(data.get("gate") or {}),
        key_fingerprint=str(data.get("key_fingerprint") or ""),
        raw=token,
    )


__all__ = [
    "DEFAULT_KEY_PATH",
    "KEY_ENV",
    "KEY_FILE_ENV",
    "TOKEN_PREFIX",
    "VERSION",
    "Passport",
    "PassportError",
    "issue_passport",
    "key_path",
    "passport_public_key",
    "verify_passport",
]
