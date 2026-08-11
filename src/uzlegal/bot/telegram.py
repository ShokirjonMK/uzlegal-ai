"""Telegram bot — savol-javob va hisobot yuborish.

## Nima uchun tashqi kutubxonasiz

`python-telegram-bot` qulay, lekin u asyncio ilovasi bo'lishni talab
qiladi va o'z sikliga ega. Bizga kerak bo'lgani — ikkita HTTP chaqiruv
(`getUpdates`, `sendMessage`). `httpx` allaqachon bog'liqlikda bor,
shuning uchun bot ~200 satr va nol yangi bog'liqlik.

## Nima uchun long-polling, webhook emas

Webhook ochiq HTTPS manzil talab qiladi. `local-dev` profili esa
noutbukda ishlaydi va u yerda ochiq manzil yo'q (ADR-007: hech qanday
tashqi xizmatga bog'liqlik). Long-polling har joyda ishlaydi.

## Xavfsizlik

Token **faqat muhit o'zgaruvchisidan** o'qiladi (docs/10 § 4) va
`allowed_chats` bo'sh bo'lmasa faqat ro'yxatdagi chatlarga javob
beriladi. Yuridik savollar shaxsiy ma'lumot bo'lishi mumkin — bot
ochiq holda hammaga javob bermasligi kerak.
"""

from __future__ import annotations

import html
import logging
import time
from typing import Any, Literal

import httpx

from uzlegal.config import TelegramSettings, get_settings
from uzlegal.core import ConsultRequest, ConsultResult

log = logging.getLogger(__name__)

# `ConsultRequest.mode` bilan bir xil qiymatlar to'plami
Mode = Literal["auto", "simple", "standard", "complex"]

API_BASE = "https://api.telegram.org"

# Telegram xabar chegarasi 4096 belgi. Zaxira qoldiramiz — bo'lish
# chegarasida HTML teg ikkiga bo'linib qolmasligi kerak.
MAX_MESSAGE = 3800

POLL_TIMEOUT = 25
GREETING = (
    "<b>UzLegal-AI</b> — Oʻzbekiston qonunchiligi boʻyicha yordamchi.\n\n"
    "Savolingizni oddiy matn bilan yozing. Javobdagi har bir huquqiy "
    "daʼvo qonun moddasiga bogʻlanadi; bogʻlanmagani oʻchiriladi.\n\n"
    "<b>Buyruqlar</b>\n"
    "/start — shu xabar\n"
    "/holat — tizim holati\n"
    "/tez &lt;savol&gt; — tez rejim (bitta agent)\n\n"
    "<i>Bu maʼlumot xarakteridagi javob, yuridik maslahat emas.</i>"
)


class TelegramError(RuntimeError):
    pass


class TelegramBot:
    """Long-polling bot. `run()` bloklaydi, `poll_once()` bir siklni bajaradi."""

    def __init__(
        self,
        settings: TelegramSettings | None = None,
        *,
        consult: Any = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings().telegram
        if not self.settings.bot_token:
            raise TelegramError(
                "UZLEGAL_TELEGRAM_BOT_TOKEN o'rnatilmagan. `.env.example` ga qarang."
            )
        self._consult = consult
        self._client = client or httpx.Client(timeout=POLL_TIMEOUT + 10)
        self._offset: int | None = None

    # ------------------------------------------------------------------ #
    # Telegram API
    # ------------------------------------------------------------------ #

    def _call(self, method: str, **payload: Any) -> Any:
        url = f"{API_BASE}/bot{self.settings.bot_token}/{method}"
        response = self._client.post(url, json=payload)
        data = response.json()
        if not data.get("ok"):
            raise TelegramError(f"{method}: {data.get('description', 'noma’lum xato')}")
        return data.get("result")

    def send(self, chat_id: str | int, text: str, *, reply_to: int | None = None) -> None:
        """Xabar yuboradi, uzunini bo'lib.

        Bo'lish **satr chegarasi bo'yicha** bo'ladi: gap o'rtasidan kesish
        yuridik matnda ma'noni buzadi va iqtibos belgisi ikkiga bo'linib
        qolishi mumkin.
        """
        for i, part in enumerate(_split_message(text)):
            self._call(
                "sendMessage",
                chat_id=chat_id,
                text=part,
                parse_mode="HTML",
                disable_web_page_preview=True,
                **({"reply_to_message_id": reply_to} if reply_to and i == 0 else {}),
            )

    def chat_action(self, chat_id: str | int) -> None:
        """«yozmoqda…» — maslahat bir daqiqagacha davom etishi mumkin."""
        try:
            self._call("sendChatAction", chat_id=chat_id, action="typing")
        except TelegramError as exc:
            log.debug("chat action yuborilmadi: %s", exc)

    # ------------------------------------------------------------------ #
    # Sikl
    # ------------------------------------------------------------------ #

    def poll_once(self) -> int:
        """Bitta `getUpdates` sikli. Qayta ishlangan xabarlar sonini qaytaradi."""
        updates = self._call(
            "getUpdates",
            timeout=POLL_TIMEOUT,
            **({"offset": self._offset} if self._offset is not None else {}),
        )
        handled = 0
        for update in updates or []:
            self._offset = int(update["update_id"]) + 1
            message = update.get("message") or update.get("edited_message")
            if message and self.handle(message):
                handled += 1
        return handled

    def run(self) -> None:
        log.info("Telegram bot ishga tushdi")
        while True:
            try:
                self.poll_once()
            except KeyboardInterrupt:
                log.info("To'xtatildi")
                return
            except (httpx.HTTPError, TelegramError) as exc:
                # Tarmoq uzilishi botni o'ldirmasligi kerak — u soatlab
                # ishlaydi va qisqa uzilish normal holat.
                log.warning("Telegram xatosi, 5 s dan keyin qayta urinaman: %s", exc)
                time.sleep(5)

    # ------------------------------------------------------------------ #
    # Xabarni qayta ishlash
    # ------------------------------------------------------------------ #

    def handle(self, message: dict[str, Any]) -> bool:
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = (message.get("text") or "").strip()
        if not chat_id or not text:
            return False

        if not self.settings.allows(chat_id):
            log.warning("Ruxsatsiz chat: %s", chat_id)
            return False

        # Buyruq **faqat** `/` bilan boshlanadi. Busiz «savol» yoki «holat»
        # so'zi bilan boshlangan oddiy savol buyruq deb qabul qilinardi va
        # foydalanuvchi javob o'rniga yordam matnini olardi.
        command, argument = "", text
        if text.startswith("/"):
            head, _, argument = text.partition(" ")
            command = head[1:].lower().split("@")[0]

        if command in ("start", "help", "yordam"):
            self.send(chat_id, GREETING)
            return True
        if command in ("holat", "status"):
            self.send(chat_id, self._status())
            return True

        question = argument.strip()
        mode: Mode = "simple" if command == "tez" else "auto"
        if not question:
            self.send(chat_id, "Savolni yozing: <code>/tez Daʼvo muddati qancha</code>")
            return True

        self.chat_action(chat_id)
        try:
            result = self._run_consult(question, mode)
        except Exception as exc:
            log.exception("Maslahat bajarilmadi")
            self.send(chat_id, f"❌ Xato yuz berdi: <code>{html.escape(str(exc))}</code>")
            return True

        self.send(chat_id, render(result), reply_to=message.get("message_id"))
        return True

    def _run_consult(self, question: str, mode: Mode) -> ConsultResult:
        if self._consult is not None:
            return self._consult(question, mode=mode)  # type: ignore[no-any-return]
        from uzlegal.core import consult

        return consult(ConsultRequest(question=question, mode=mode))

    def _status(self) -> str:
        from uzlegal.config import get_registry
        from uzlegal.ingest.sync import SyncManager

        registry = get_registry()
        state = SyncManager().state
        return (
            "<b>Tizim holati</b>\n"
            f"Model: <code>{registry.active_id or 'tanlanmagan'}</code>\n"
            f"Bilim bazasi: <code>{state.kb_version or 'qurilmagan'}</code>\n"
            f"Yangilangan: {state.age_days() if state.age_days() is not None else '—'} kun oldin"
        )


# --------------------------------------------------------------------------- #
# Javobni Telegram uchun formatlash
# --------------------------------------------------------------------------- #


def render(result: ConsultResult) -> str:
    """`ConsultResult` → Telegram HTML.

    Iqtiboslar alohida ro'yxatga chiqariladi va havola bilan beriladi:
    foydalanuvchi normani o'zi o'qiy olishi kerak, aks holda «iqtibosga
    asoslangan» degani shunchaki so'z bo'lib qoladi.
    """
    # Javob matni **butunlay** ekranlanadi. Model chiqishi HTML sifatida
    # talqin qilinmasligi kerak: `<` belgisi Telegram parseriga tushsa
    # xabar umuman yuborilmaydi va foydalanuvchi javobsiz qoladi.
    blocks = [html.escape(result.answer)]

    if result.citations:
        lines = ["", "<b>Manbalar</b>"]
        for citation in result.citations:
            label = html.escape(
                f"{citation.doc_title or citation.doc_id}, {citation.article}-modda"
            )
            lines.append(
                f'[{citation.tag}] <a href="{citation.url}">{label}</a>'
                if citation.url
                else f"[{citation.tag}] {label}"
            )
        blocks.append("\n".join(lines))

    if result.caveats:
        blocks.append(
            "\n<b>Eslatmalar</b>\n" + "\n".join(f"• {html.escape(c)}" for c in result.caveats[:5])
        )

    meta = [f"rejim: {result.mode_used}", f"{result.latency_ms / 1000:.0f} s"]
    if result.confidence:
        meta.append(f"ishonch: {result.confidence:.0%}")
    blocks.append(f"\n<i>{' · '.join(meta)}</i>")
    blocks.append(f"<i>{html.escape(result.disclaimer)}</i>")

    return "\n".join(blocks)


def _split_message(text: str, limit: int = MAX_MESSAGE) -> list[str]:
    """Uzun matnni satr chegarasi bo'yicha bo'ladi."""
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    current: list[str] = []
    size = 0
    for line in text.splitlines(keepends=True):
        # Bitta satr ham chegaradan uzun bo'lsa — majburan kesamiz
        while len(line) > limit:
            if current:
                parts.append("".join(current))
                current, size = [], 0
            parts.append(line[:limit])
            line = line[limit:]
        if size + len(line) > limit:
            parts.append("".join(current))
            current, size = [], 0
        current.append(line)
        size += len(line)
    if current:
        parts.append("".join(current))
    return [p for p in parts if p.strip()]


def notify(text: str, settings: TelegramSettings | None = None) -> bool:
    """Hisobotni sozlangan chatga yuboradi (PM xabarnomasi uchun).

    Sozlanmagan bo'lsa `False` qaytadi va **xato bermaydi** — xabarnoma
    ixtiyoriy, uning yo'qligi ish oqimini to'xtatmasligi kerak.
    """
    settings = settings or get_settings().telegram
    if not settings.is_configured:
        log.info("Telegram sozlanmagan — xabar yuborilmadi")
        return False
    bot = TelegramBot(settings)
    assert settings.chat_id is not None
    bot.send(settings.chat_id, text)
    return True
