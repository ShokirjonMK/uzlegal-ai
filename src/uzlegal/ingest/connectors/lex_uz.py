"""lex.uz konnektori — yuklab olish va o'zgarishlarni aniqlash.

## Kritik cheklov: Crawl-delay 20

lex.uz `robots.txt` da:

    User-agent: *
    Crawl-delay: 20

Bu **majburiy** va u butun Faza 1 rejasini o'zgartiradi:

| Ko'rsatkich | Qiymat |
|-------------|--------|
| So'rovlar orasidagi minimal pauza | 20 s |
| Sahifa o'lchami | 1.5–2 MB |
| Server javob vaqti | ~17 s |
| Amaldagi tezlik | **~1.6 hujjat/daqiqa** |
| 40 000 hujjat uchun | **~17 kun uzluksiz** |

Shuning uchun:

1. To'liq yig'ish **bir martalik**, fonda, uzoq davom etadigan operatsiya
2. Keyingi yangilanishlar **inkremental** — faqat o'zgarganlari
3. Har bir hujjat `sha256` bilan taqqoslanadi; o'zgarmagan bo'lsa parsing
   o'tkazib yuboriladi
4. Ish **to'xtatilib, davom ettirilishi** mumkin (`resume`)

## Yangilanish siyosati

Qonunchilik doimiy o'zgaradi, shuning uchun bilim bazasi eskirmasligi kerak:

* Avtomatik: har **7 kunda** ustuvor hujjatlar qayta tekshiriladi
* Qo'lda: admin panelidan istalgan vaqtda ishga tushiriladi
* Har sinxronizatsiya natijasi `SyncReport` sifatida saqlanadi

Batafsil: `uzlegal.ingest.sync`
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import httpx

from uzlegal.ingest.types import DocumentRef, RawDocument

log = logging.getLogger(__name__)

USER_AGENT = "UzLegal-AI/0.1 (+https://github.com/ShokirjonMK/uzlegal-ai)"

# robots.txt dan o'qiladi, lekin bu qiymatdan past tushmaydi
DEFAULT_CRAWL_DELAY = 20.0
MIN_CRAWL_DELAY = 20.0


class RateLimiter:
    """robots.txt Crawl-delay ga rioya qiladi.

    Thread-safe: bir necha ishchi bo'lsa ham umumiy pauza saqlanadi.
    Bu **ataylab** global — parallel yuklab olish `Crawl-delay` ni buzadi.
    """

    def __init__(self, delay: float = DEFAULT_CRAWL_DELAY) -> None:
        self.delay = max(delay, MIN_CRAWL_DELAY)
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> float:
        with self._lock:
            elapsed = time.monotonic() - self._last
            sleep_for = max(0.0, self.delay - elapsed)
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._last = time.monotonic()
            return sleep_for


class LexUzConnector:
    """lex.uz dan hujjatlarni yuklab oladi."""

    name = "lex.uz"
    base_url = "https://lex.uz"

    def __init__(
        self,
        raw_dir: Path = Path("data/raw/lex.uz"),
        timeout: float = 60.0,
        crawl_delay: float | None = None,
        ui_lang: str = "uz",
    ) -> None:
        self.ui_lang = ui_lang
        self.raw_dir = raw_dir
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.limiter = RateLimiter(crawl_delay or DEFAULT_CRAWL_DELAY)
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            follow_redirects=True,
        )

    # ------------------------------------------------------------------ #
    # robots.txt
    # ------------------------------------------------------------------ #

    def read_crawl_delay(self) -> float:
        """robots.txt dan Crawl-delay ni o'qiydi.

        Xato bo'lsa standart (20 s) qoladi — hech qachon tezroq emas.
        """
        try:
            r = self._client.get(f"{self.base_url}/robots.txt")
            m = re.search(r"Crawl-delay:\s*(\d+(?:\.\d+)?)", r.text, re.IGNORECASE)
            if m:
                delay = max(float(m.group(1)), MIN_CRAWL_DELAY)
                self.limiter.delay = delay
                log.info("robots.txt Crawl-delay: %.0f s", delay)
                return delay
        except Exception as exc:
            log.warning("robots.txt o'qilmadi (%s) — standart %.0f s", exc, MIN_CRAWL_DELAY)
        return self.limiter.delay

    # ------------------------------------------------------------------ #
    # Yuklab olish
    # ------------------------------------------------------------------ #

    def doc_url(self, doc_id: str) -> str:
        """Hujjat manzili.

        DIQQAT: lex.uz da til nashrlari **alohida hujjatlar**:

            /uz/docs/-111189   →  Fuqarolik kodeksi, o'zbek (lotin)
            /ru/docs/111181    →  Гражданский кодекс, rus

        O'zbek lotin nashrlari **manfiy ID** bilan keladi. URL dagi
        `/uz/` yoki `/ru/` prefiksi faqat interfeys tilini o'zgartiradi —
        hujjat matni ID bilan belgilanadi.
        """
        return f"{self.base_url}/{self.ui_lang}/docs/{doc_id}"

    def raw_path(self, doc_id: str) -> Path:
        # Manfiy ID lar uchun fayl nomi: "-111189" → "neg111189"
        # (ba'zi fayl tizimlarida bosh minus muammo tug'diradi)
        return self.raw_dir / f"{self._safe_name(doc_id)}.html"

    def meta_path(self, doc_id: str) -> Path:
        return self.raw_dir / f"{self._safe_name(doc_id)}.meta.json"

    @staticmethod
    def _safe_name(doc_id: str) -> str:
        return f"neg{doc_id[1:]}" if doc_id.startswith("-") else doc_id

    @staticmethod
    def _from_safe_name(name: str) -> str:
        return f"-{name[3:]}" if name.startswith("neg") else name

    def fetch(self, doc_id: str) -> RawDocument:
        """Bitta hujjatni yuklab oladi. Crawl-delay avtomatik qo'llaniladi."""
        waited = self.limiter.wait()
        url = self.doc_url(doc_id)
        log.debug("GET %s (kutildi %.1f s)", url, waited)

        response = self._client.get(url)
        response.raise_for_status()
        content = response.text

        return RawDocument(
            source=self.name,
            doc_id=doc_id,
            url=url,
            fetched_at=datetime.now(UTC),
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            http_status=response.status_code,
            content_type=response.headers.get("content-type", "text/html"),
            content=content,
        )

    def store(self, raw: RawDocument) -> Path:
        """Xom hujjatni **o'zgarmas arxivga** yozadi.

        Bu nusxa hech qachon tahrirlanmaydi. Parser yaxshilanganda butun
        quvur shu arxivdan qayta ishga tushiriladi — takrorlanuvchanlik
        shundan keladi (docs/03 § 3).
        """
        path = self.raw_path(raw.doc_id)
        path.write_text(raw.content, encoding="utf-8")
        self.meta_path(raw.doc_id).write_text(
            raw.model_dump_json(indent=2, exclude={"content"}), encoding="utf-8"
        )
        return path

    def load_cached(self, doc_id: str) -> RawDocument | None:
        """Arxivdan o'qiydi — tarmoqqa chiqmasdan."""
        path, meta = self.raw_path(doc_id), self.meta_path(doc_id)
        if not (path.exists() and meta.exists()):
            return None
        import json

        data = json.loads(meta.read_text(encoding="utf-8"))
        data["content"] = path.read_text(encoding="utf-8")
        return RawDocument(**data)

    def known_hash(self, doc_id: str) -> str | None:
        meta = self.meta_path(doc_id)
        if not meta.exists():
            return None
        import json

        digest = json.loads(meta.read_text(encoding="utf-8")).get("content_sha256")
        return str(digest) if digest else None

    # ------------------------------------------------------------------ #
    # O'zgarishni aniqlash
    # ------------------------------------------------------------------ #

    def check_changed(self, doc_id: str) -> tuple[bool, RawDocument | None]:
        """Hujjat o'zgarganmi tekshiradi.

        `(o'zgardimi, yangi_hujjat)` qaytaradi. Hujjat baribir to'liq
        yuklab olinadi (lex.uz `If-Modified-Since` ni qo'llab-quvvatlamaydi),
        lekin o'zgarmagan bo'lsa parsing va indekslash o'tkazib yuboriladi —
        bu vaqtning katta qismini tejaydi.
        """
        previous = self.known_hash(doc_id)
        raw = self.fetch(doc_id)
        return (previous != raw.content_sha256), raw

    def fetch_many(
        self, doc_ids: list[str], *, skip_unchanged: bool = True
    ) -> Iterator[tuple[str, str, RawDocument | None]]:
        """Ko'p hujjatni yuklaydi. Har biri uchun `(doc_id, holat, hujjat)`.

        Holatlar: `new` · `changed` · `unchanged` · `error`
        """
        for doc_id in doc_ids:
            try:
                previous = self.known_hash(doc_id)
                raw = self.fetch(doc_id)

                if previous is None:
                    self.store(raw)
                    yield doc_id, "new", raw
                elif previous != raw.content_sha256:
                    self.store(raw)
                    yield doc_id, "changed", raw
                else:
                    yield doc_id, "unchanged", (None if skip_unchanged else raw)
            except Exception as exc:
                log.warning("Hujjat %s yuklanmadi: %s", doc_id, exc)
                yield doc_id, "error", None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> LexUzConnector:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# --------------------------------------------------------------------------- #
# Ustuvor hujjatlar ro'yxati
# --------------------------------------------------------------------------- #

# P0 — eng ko'p so'raladigan kodekslar. To'liq katalog kashfiyot bosqichida
# quriladi, lekin birinchi ishlaydigan bilim bazasi shulardan boshlanadi.
# lex.uz qidiruvi orqali **tekshirilgan** ID lar (2026-08-09):
#   /uz/search/nat?query=kodeks&lang=4&form_id=3964&status=Y
#
# lang=4 → O'ZB (lotin) · form_id=3964 → Kodeks · status=Y → amaldagi
#
# Bu ro'yxat qo'lda yozilmagan — `uzlegal kb discover` buyrug'i uni
# qayta yaratadi va yangi kodeks qo'shilsa avtomatik topadi.
PRIORITY_DOCS: list[DocumentRef] = [
    DocumentRef(
        source="lex.uz", doc_id=i, url=f"https://lex.uz/uz/docs/{i}", title=t, doc_type="kodeks"
    )
    for i, t in [
        ("-111189", "Fuqarolik kodeksi (birinchi qism)"),
        ("-180552", "Fuqarolik kodeksi (ikkinchi qism)"),
        ("-6257288", "Mehnat kodeksi"),
        ("-111453", "Jinoyat kodeksi"),
        ("-111460", "Jinoyat-protsessual kodeksi"),
        ("-163629", "Jinoyat-ijroiya kodeksi"),
        ("-3517337", "Fuqarolik protsessual kodeksi"),
        ("-3523891", "Iqtisodiy protsessual kodeksi"),
        ("-3527353", "Ma'muriy sud ishlarini yuritish to'g'risidagi kodeks"),
        ("-97664", "Ma'muriy javobgarlik to'g'risidagi kodeks"),
        ("-104720", "Oila kodeksi"),
        ("-4674902", "Soliq kodeksi"),
        ("-2304138", "Budjet kodeksi"),
        ("-2876354", "Bojxona kodeksi"),
        ("-152653", "Yer kodeksi"),
        ("-106136", "Uy-joy kodeksi"),
        ("-5307951", "Shaharsozlik kodeksi"),
        ("-7655343", "Suv kodeksi"),
        ("-55594", "Havo kodeksi"),
        ("-4386848", "Saylov kodeksi"),
    ]
]
