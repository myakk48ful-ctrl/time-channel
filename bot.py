#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
   🕐  Telegram Time Channel Title Updater  🕐
   Pure-Python rewrite of the original PHP script
   (https://github.com/myakk48ful-ctrl/time-channel)
   Engine  : aiogram 3 + aiosqlite + pytz
   Feature : 22 premium unicode fonts · multi timezone ·
             flags · member count · date · 🟢 status ·
             special occasions · full admin panel
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone as dt_tz

import aiosqlite
import pytz
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest, TelegramAPIError, TelegramNetworkError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)
from aiogram.types import FSInputFile

# ───────────────────────── 1. SETTINGS ─────────────────────────────────────
# این نسخه برای Railway آماده شده است. همه‌ی تنظیمات از متغیرهای محیطی
# (Environment Variables) خوانده می‌شوند؛ در پنل Railway این متغیرها را بساز:
#
#   BOT_TOKEN = توکن ربات شما
#   ADMIN_IDS = آیدی عددی ادمین (می‌توانی چند آیدی را با ویرگول جدا کنی)
#
# این مقدارها فقط "پیش‌فرض" هستند و اگر متغیر محیطی ست نکنی استفاده می‌شوند:
BOT_TOKEN = os.environ.get("BOT_TOKEN", "TOKEN")
_raw_admins = os.environ.get("ADMIN_IDS", "123456789")
ADMIN_IDS = []
for _part in str(_raw_admins).split(","):
    _part = _part.strip()
    if _part.isdigit():
        ADMIN_IDS.append(int(_part))
DEFAULT_TZ = os.environ.get("DEFAULT_TZ", "Asia/Tehran")
# دیتابیس در Railway روی دیسک موقتی است (Ephemeral)؛ برای ذخیره‌ی دائمی تنظیمات
# می‌توانی یک Railway Volume بسازی و مسیرش را اینجا بدهی (مثلا /data/bot.db)
DB_PATH = os.environ.get("DB_PATH", "bot.db")
DEFAULT_INTERVAL = int(os.environ.get("DEFAULT_INTERVAL", "60"))
# روی Railway نیازی به پروکسی نیست (سرور خارج از فیلترینگ است). خالی بگذار.
PROXY = ""
# ────────────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("time_bot")

# ───────────────────────── 2. FONTS (22 PREMIUM) ─────────────────────────
# هر فونت: نام نمایشی + نقشه‌ی تبدیل کاراکتر (A-Z a-z 0-9 → یونیکد)
def _g(us, ls, ds):
    """مولد نقشه‌ی فونت برای بلوک‌های یونیکد پیوسته."""
    d = {}
    if us:
        for i in range(26):
            d[chr(65 + i)] = chr(us + i)
    if ls:
        for i in range(26):
            d[chr(97 + i)] = chr(ls + i)
    if ds:
        for i in range(10):
            d[chr(48 + i)] = chr(ds + i)
    return d

_ASCII = [chr(c) for c in range(48, 58)] + [chr(c) for c in range(65, 91)] + [chr(c) for c in range(97, 123)]

# فونت‌های ترکیبی (دکورهای پشت کاراکتر)
def _overlay(ch):
    return {c: c + ch for c in _ASCII}

FONTS = {
    "default":          ("Default", {}),
    "math_bold":        ("Math Bold", _g(0x1D400, 0x1D41A, 0x1D7CE)),
    "math_bold_ital":   ("Math Bold Italic", _g(0x1D468, 0x1D482, None)),
    "math_sans":        ("Math Sans", _g(0x1D5A0, 0x1D5BA, 0x1D7E2)),
    "math_sans_bold":   ("Math Sans Bold", _g(0x1D5D4, 0x1D5EE, 0x1D7EC)),
    "math_sans_ital":   ("Math Sans Italic", _g(0x1D608, 0x1D622, None)),
    "math_sans_bital":  ("Math Sans Bold Italic", _g(0x1D63C, 0x1D656, None)),
    "math_mono":        ("Math Monospace", _g(0x1D670, 0x1D68A, 0x1D7F6)),
    "math_fraktur":     ("Math Fraktur", _g(0x1D504, 0x1D51E, None)),
    "math_bold_frak":   ("Math Bold Fraktur", _g(0x1D56C, 0x1D586, None)),
    "math_double":      ("Double Struck", _g(0x1D538, 0x1D552, 0x1D7D8)),
    "script":           ("Script", _g(0x1D49C, 0x1D4B6, None)),
    "bold_script":      ("Bold Script", _g(0x1D4D0, 0x1D4EA, None)),
    "circled":          ("Circled", dict(
        {chr(65+i): chr(0x24B6+i) for i in range(26)},
        **{chr(97+i): chr(0x24D0+i) for i in range(26)},
        **{chr(49+i): chr(0x2460+i) for i in range(9)},  # 1-9
        **{"0": "\u24EA"}),
    ),
    "squared":          ("Squared", _g(0x1F130, None, None)),
    "paren":            ("Parenthesized", _g(0x1F110, None, None)),
    "fullwidth":        ("Fullwidth", _g(0xFF21, 0xFF41, 0xFF10)),
    "smallcaps":        ("Small Caps", {
        'a':'\u1D00','b':'\u0299','c':'\u1D04','d':'\u1D05','e':'\u1D07',
        'f':'\ua730','g':'\u0262','h':'\u029C','i':'\u026A','j':'\u1D0A',
        'k':'\u1D0B','l':'\u029F','m':'\u1D0D','n':'\u0274','o':'\u1D0F',
        'p':'\u1D18','q':'\u01EB','r':'\u0280','s':'s','t':'\u1D1B',
        'u':'\u1D1C','v':'\u1D20','w':'\u1D21','x':'x','y':'\u028F','z':'\u1D22'}),
    "superscript":      ("Superscript", {
        '0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹',
        'a':'ᵃ','b':'ᵇ','c':'ᶜ','d':'ᵈ','e':'ᵉ','f':'ᶠ','g':'ᵍ','h':'ʰ','i':'ⁱ','j':'ʲ',
        'k':'ᵏ','l':'ˡ','m':'ᵐ','n':'ⁿ','o':'ᵒ','p':'ᵖ','r':'ʳ','s':'ˢ','t':'ᵗ','u':'ᵘ',
        'v':'ᵛ','w':'ʷ','x':'ˣ','y':'ʸ','z':'ᶻ',
        'A':'ᴬ','B':'ᴮ','D':'ᴰ','E':'ᴱ','G':'ᴳ','H':'ᴴ','I':'ᴵ','J':'ᴶ','K':'ᴷ','L':'ᴸ',
        'M':'ᴹ','N':'ᴺ','O':'ᴼ','P':'ᴾ','R':'ᴿ','T':'ᵀ','U':'ᵁ','V':'ⱽ','W':'ᵂ'}),
    "subscript":        ("Subscript", {
        '0':'₀','1':'₁','2':'₂','3':'₃','4':'₄','5':'₅','6':'₆','7':'₇','8':'₈','9':'₉',
        'a':'ₐ','e':'ₑ','h':'ₕ','i':'ᵢ','j':'ⱼ','k':'ₖ','l':'ₗ','m':'ₘ','n':'ₙ','o':'ₒ',
        'p':'ₚ','r':'ᵣ','s':'ₛ','t':'ₜ','u':'ᵤ','v':'ᵥ','x':'ₓ'}),
    "upside":           ("Upside Down", {
        'a':'ɐ','b':'q','c':'ɔ','d':'p','e':'ǝ','f':'ɟ','g':'ƃ','h':'ɥ','i':'ᴉ','j':'ɾ',
        'k':'ʞ','l':'l','m':'ɯ','n':'u','o':'o','p':'d','q':'b','r':'ɹ','s':'s','t':'ʇ',
        'u':'n','v':'ʌ','w':'ʍ','x':'x','y':'ʎ','z':'z',
        '0':'0','1':'Ɩ','2':'ᄅ','3':'Ɛ','4':'ㄣ','5':'ϛ','6':'9','7':'ㄥ','8':'8','9':'6'}),
    "overline":         ("Overline", _overlay('\u0305')),
    "strike":           ("Strike", _overlay('\u0336')),
}

def apply_font(text: str, key: str) -> str:
    """تبدیل متن با فونت انتخاب‌شده؛ اگر کاراکتری نبود، همان‌طور می‌ماند."""
    if key not in FONTS:
        key = "default"
    mapping = FONTS[key][1]
    if not mapping:
        return text
    return "".join(mapping.get(ch, ch) for ch in text)

# ───────────────────────── 3. TIMEZONES + FLAGS ─────────────────────────
TIMEZONES = {
    "Asia/Tehran": "🇮🇷",
    "Europe/Istanbul": "🇹🇷",
    "Asia/Baghdad": "🇮🇶",
    "Asia/Riyadh": "🇸🇦",
    "Asia/Kuwait": "🇰🇼",
    "Asia/Dubai": "🇦🇪",
    "Asia/Kabul": "🇦🇫",
    "Asia/Yerevan": "🇦🇲",
    "Asia/Karachi": "🇵🇰",
    "Asia/Kolkata": "🇮🇳",
    "Asia/Shanghai": "🇨🇳",
    "Asia/Tokyo": "🇯🇵",
    "Europe/Moscow": "🇷🇺",
    "Europe/Athens": "🇬🇷",
    "Europe/Berlin": "🇩🇪",
    "Europe/Paris": "🇫🇷",
    "Europe/London": "🇬🇧",
    "America/New_York": "🇺🇸",
    "America/Los_Angeles": "🇺🇸",
    "Australia/Sydney": "🇦🇺",
}

TZ_NAMES = {
    "Asia/Tehran": "تهران", "Europe/Istanbul": "استانبول", "Asia/Baghdad": "بغداد",
    "Asia/Riyadh": "ریاض", "Asia/Kuwait": "کویت", "Asia/Dubai": "دبی",
    "Asia/Kabul": "کابل", "Asia/Yerevan": "ایروان", "Asia/Karachi": "کراچی",
    "Asia/Kolkata": "دهلی نو", "Asia/Shanghai": "شانگهای", "Asia/Tokyo": "توکیو",
    "Europe/Moscow": "مسکو", "Europe/Athens": "آتن", "Europe/Berlin": "برلین",
    "Europe/Paris": "پاریس", "Europe/London": "لندن",
    "America/New_York": "نیویورک", "America/Los_Angeles": "لس‌آنجلس", "Australia/Sydney": "سیدنی",
}

# ───────────────────────── 4. JALALI + OCCASIONS ─────────────────────────
PERSIAN_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
PERSIAN_DAYS = ["یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه", "ده",
                "یازده", "دوازده", "سیزده", "چهارده", "پانزده", "شانزده",
                "هفده", "هجده", "نوزده", "بیست", "بیست و یک", "بیست و دو",
                "بیست و سه", "بیست و چهار", "بیست و پنج", "بیست و شش",
                "بیست و هفت", "بیست و هشت", "بیست و نه", "سی", "سی و یک"]

def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = (gm > 2) and (gy + 1) or gy
    days = (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + (days % 31)
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd

def jalali_date_str(dt):
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    return f"{jd} {PERSIAN_MONTHS[jm - 1]} {jy}"

def get_occasion(dt):
    """مناسبت‌های خاص؛ برمی‌گرداند متن فارسی یا رشته خالی."""
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    m, d = dt.month, dt.day
    # نوروز
    if jm == 1 and 1 <= jd <= 3:
        return "🎉 نوروز"
    if jm == 1 and jd == 13:
        return "🌳 سیزده‌به‌در"
    if jm == 12 and jd == 29:
        return "🎆 چهارشنبه‌سوری"
    if jm == 12 and jd == 30:
        return "🧹 آخرین روز سال"
    # مناسبت‌های میلادی
    if m == 12 and d == 25:
        return "🎄 کریسمس"
    if m == 12 and d == 31:
        return "🎆 سال نوی میلادی"
    if m == 1 and d == 1:
        return "✨ سال نو"
    if m == 1 and d == 6:
        return "🎁 کریسمس ارتدوکس"
    if m == 10 and d == 31:
        return "🎃 هالووین"
    if m == 2 and d == 14:
        return "💝 ولنتاین"
    if m == 3 and d == 8:
        return "🌸 روز زن"
    if m == 5 and d == 1:
        return "🛠 روز کارگر"
    return ""

# ───────────────────────── 5. DEFAULT CONFIG ─────────────────────────
def default_config(chat_id: int, base_title: str = "") -> dict:
    return {
        "chat_id": chat_id,
        "base_title": base_title or "",
        "enabled": True,
        "interval": DEFAULT_INTERVAL,
        "font": "default",
        "timezones": [DEFAULT_TZ],
        "flags": True,
        "show_time": True,
        "show_date": True,
        "show_status": True,
        "show_members": False,
        "show_occasion": True,
        "last_members": None,
        "last_update": 0,
    }

# ───────────────────────── 6. DATABASE (aiosqlite) ─────────────────────────
class DB:
    def __init__(self):
        self.conn = None

    async def init(self):
        self.conn = await aiosqlite.connect(DB_PATH)
        await self.conn.execute(
            "CREATE TABLE IF NOT EXISTS chats (chat_id INTEGER PRIMARY KEY, config TEXT)"
        )
        await self.conn.commit()

    async def get_all(self) -> list:
        cur = await self.conn.execute("SELECT chat_id, config FROM chats")
        rows = await cur.fetchall()
        out = []
        for cid, cfg in rows:
            try:
                d = json.loads(cfg)
            except Exception:
                d = {}
            d.setdefault("chat_id", cid)
            out.append(d)
        return out

    async def get(self, chat_id: int):
        cur = await self.conn.execute("SELECT config FROM chats WHERE chat_id=?", (chat_id,))
        row = await cur.fetchone()
        if not row:
            return None
        try:
            d = json.loads(row[0])
        except Exception:
            d = {}
        d.setdefault("chat_id", chat_id)
        return d

    async def save(self, cfg: dict):
        cfg.setdefault("chat_id")
        await self.conn.execute(
            "INSERT INTO chats (chat_id, config) VALUES (?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET config=excluded.config",
            (cfg["chat_id"], json.dumps(cfg, ensure_ascii=False)),
        )
        await self.conn.commit()

    async def delete(self, chat_id: int):
        await self.conn.execute("DELETE FROM chats WHERE chat_id=?", (chat_id,))
        await self.conn.commit()

db = DB()

# ───────────────────────── 7. BOT / DISPATCHER ─────────────────────────
def build_session():
    """ساخت سشن با پروکسی در صورت تنظیم."""
    if PROXY and str(PROXY).strip():
        log.info(f"Using proxy: {PROXY}")
        return AiohttpSession(proxy=PROXY, limit=50)
    return AiohttpSession(limit=50)

bot = Bot(token=BOT_TOKEN, session=build_session())
dp = Dispatcher()
router = Router()
dp.include_router(router)

class Form(StatesGroup):
    add_chat = State()        # دریافت چت جدید
    set_title = State()       # دریافت عنوان پایه

# ───────────────────────── 8. TITLE BUILDER ─────────────────────────
def is_admin(user_id) -> bool:
    return user_id in ADMIN_IDS

def _tz_time(tz_name):
    try:
        return datetime.now(pytz.timezone(tz_name))
    except Exception:
        return datetime.now(pytz.timezone(DEFAULT_TZ))

def build_title(cfg: dict) -> str:
    """ساخت عنوان نهایی بر اساس تنظیمات چت."""
    base = (cfg.get("base_title") or "").strip()
    tzs = cfg.get("timezones") or [DEFAULT_TZ]
    parts = []

    if cfg.get("show_time"):
        chunks = []
        for tz in tzs:
            dt = _tz_time(tz)
            flag = TIMEZONES.get(tz, "") if cfg.get("flags") else ""
            chunks.append(f"{flag}{dt.strftime('%H:%M')}")
        parts.append(" | ".join(chunks))

    if cfg.get("show_date"):
        dt = _tz_time(tzs[0])
        parts.append(f"📅 {jalali_date_str(dt)}")

    if cfg.get("show_status"):
        parts.append("🟢")

    if cfg.get("show_members") and cfg.get("last_members"):
        parts.append(f"👥 {cfg['last_members']:,}")

    if cfg.get("show_occasion"):
        dt = _tz_time(tzs[0])
        occ = get_occasion(dt)
        if occ:
            parts.append(occ)

    title = base
    if parts:
        title = f"{base} | {' | '.join(parts)}" if base else " | ".join(parts)

    return apply_font(title, cfg.get("font", "default"))

# ───────────────────────── 9. RATE-LIMIT SAFE CALL ─────────────────────────
async def safe_call(coro, chat_id=None, disable_on_forbidden=True):
    """اجرای امن درخواست با مدیریت Rate Limit و خطا."""
    wait = 1
    for attempt in range(6):
        try:
            return await coro
        except TelegramRetryAfter as e:
            s = getattr(e, "retry_after", wait)
            log.warning(f"Rate limit: sleeping {s}s (chat={chat_id})")
            await asyncio.sleep(s + 1)
            wait = s
        except TelegramForbiddenError:
            log.warning(f"Bot forbidden in chat {chat_id}")
            if disable_on_forbidden and chat_id is not None:
                cfg = await db.get(chat_id)
                if cfg:
                    cfg["enabled"] = False
                    await db.save(cfg)
            return None
        except TelegramBadRequest as e:
            # مثلاً بدون دسترسی ادمین برای تغییر عنوان
            log.warning(f"BadRequest (chat={chat_id}): {e}")
            if chat_id is not None and "not enough rights" in str(e).lower():
                cfg = await db.get(chat_id)
                if cfg:
                    cfg["enabled"] = False
                    await db.save(cfg)
            await asyncio.sleep(wait)
        except TelegramAPIError as e:
            log.warning(f"API error (chat={chat_id}): {e}")
            await asyncio.sleep(wait)
        wait = min(wait * 2, 30)
    return None

async def update_chat_title(cfg: dict):
    """آپدیت عنوان یک چت."""
    chat_id = cfg["chat_id"]
    if cfg.get("show_members"):
        try:
            cnt = await safe_call(bot.get_chat_member_count(chat_id), chat_id=chat_id,
                                  disable_on_forbidden=True)
            if cnt:
                cfg["last_members"] = cnt
        except Exception:
            pass
    title = build_title(cfg)
    await safe_call(bot.set_chat_title(chat_id=chat_id, title=title), chat_id=chat_id)
    cfg["last_update"] = time.time()
    await db.save(cfg)
    return title

# ───────────────────────── 10. BACKGROUND UPDATER ─────────────────────────
async def updater_loop():
    log.info("Updater loop started.")
    while True:
        await asyncio.sleep(1)
        try:
            chats = await db.get_all()
            now = time.time()
            for cfg in chats:
                if not cfg.get("enabled"):
                    continue
                interval = max(5, int(cfg.get("interval", DEFAULT_INTERVAL)))
                if now - cfg.get("last_update", 0) >= interval:
                    try:
                        await update_chat_title(cfg)
                    except Exception as e:
                        log.exception(f"Update failed for chat {cfg.get('chat_id')}: {e}")
                    await asyncio.sleep(1)  # فاصله برای جلوگیری از Flood
        except Exception as e:
            log.exception(f"Updater error: {e}")

# ───────────────────────── 11. KEYBOARD BUILDERS ─────────────────────────
def main_menu(chats):
    kb = [[InlineKeyboardButton(text="➕ افزودن چت جدید", callback_data="add_chat")]]
    for c in chats:
        t = (c.get("base_title") or c["chat_id"]).strip()
        st = "✅" if c.get("enabled") else "⛔️"
        kb.append([InlineKeyboardButton(text=f"{st} 🕐 {t}", callback_data=f"chat:{c['chat_id']}")])
    kb.append([InlineKeyboardButton(text="⚡️ آپدیت همه چت‌ها", callback_data="updall")])
    kb.append([InlineKeyboardButton(text="🔄 بروزرسانی لیست", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def chat_panel_kb(cfg):
    cid = cfg["chat_id"]
    on = cfg.get("enabled", True)
    kb = [
        [
            InlineKeyboardButton(text="✅ فعال" if on else "⛔️ غیرفعال", callback_data=f"tog:{cid}:enabled"),
            InlineKeyboardButton(text=f"⏱ {cfg.get('interval',60)}ث", callback_data=f"ivl:{cid}"),
        ],
        [
            InlineKeyboardButton(text="📝 عنوان پایه", callback_data=f"settitle:{cid}"),
            InlineKeyboardButton(text="🔤 فونت", callback_data=f"fnt:{cid}"),
        ],
        [InlineKeyboardButton(text="🌍 تایم‌زون‌ها", callback_data=f"tz:{cid}")],
        [
            InlineKeyboardButton(text=("✅" if cfg.get("show_time") else "❌") + " 🕐 زمان", callback_data=f"tog:{cid}:show_time"),
            InlineKeyboardButton(text=("✅" if cfg.get("show_date") else "❌") + " 📅 تاریخ", callback_data=f"tog:{cid}:show_date"),
        ],
        [
            InlineKeyboardButton(text=("✅" if cfg.get("show_status") else "❌") + " 🟢 وضعیت", callback_data=f"tog:{cid}:show_status"),
            InlineKeyboardButton(text=("✅" if cfg.get("show_members") else "❌") + " 👥 اعضا", callback_data=f"tog:{cid}:show_members"),
        ],
        [
            InlineKeyboardButton(text=("✅" if cfg.get("show_occasion") else "❌") + " 🎉 مناسبت", callback_data=f"tog:{cid}:show_occasion"),
            InlineKeyboardButton(text=("✅" if cfg.get("flags") else "❌") + " 🚩 پرچم", callback_data=f"tog:{cid}:flags"),
        ],
        [
            InlineKeyboardButton(text="⚡️ آپدیت چت", callback_data=f"upd:{cid}"),
            InlineKeyboardButton(text="👀 پیش‌نمایش", callback_data=f"preview:{cid}"),
        ],
        [
            InlineKeyboardButton(text="↩️ بازگشت", callback_data="menu"),
            InlineKeyboardButton(text="🗑 حذف چت", callback_data=f"del:{cid}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def font_kb(cfg):
    cid = cfg["chat_id"]
    sel = cfg.get("font", "default")
    kb = []
    items = list(FONTS.items())
    for i in range(0, len(items), 2):
        row = []
        for key, (name, _m) in items[i:i + 2]:
            mark = "✅ " if key == sel else ""
            sample = apply_font("Aa", key)
            row.append(InlineKeyboardButton(text=f"{mark}{sample}", callback_data=f"fsel:{cid}:{key}"))
        kb.append(row)
    kb.append([InlineKeyboardButton(text="↩️ بازگشت به پنل", callback_data=f"chat:{cid}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def tz_kb(cfg, page=0):
    cid = cfg["chat_id"]
    selected = set(cfg.get("timezones") or [])
    per_page = 8
    names = list(TIMEZONES.keys())
    pages = (len(names) + per_page - 1) // per_page
    page = max(0, min(page, pages - 1))
    chunk = names[page * per_page: (page + 1) * per_page]
    kb = []
    for tz in chunk:
        mark = "✅" if tz in selected else "⬜"
        flag = TIMEZONES.get(tz, "")
        label = TZ_NAMES.get(tz, tz)
        kb.append([InlineKeyboardButton(text=f"{mark} {flag} {label}", callback_data=f"tzsel:{cid}:{tz}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"tzpg:{cid}:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page+1}/{pages}", callback_data="noop"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"tzpg:{cid}:{page+1}"))
    kb.append(nav)
    kb.append([InlineKeyboardButton(text="↩️ بازگشت به پنل", callback_data=f"chat:{cid}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ───────────────────────── 12. MESSAGE BUILDERS ─────────────────────────
def panel_text(cfg):
    cid = cfg["chat_id"]
    base = cfg.get("base_title") or "(تعیین نشده)"
    title = build_title(cfg)
    on = cfg.get("enabled", True)
    tzs = cfg.get("timezones") or [DEFAULT_TZ]
    tz_txt = "، ".join((TIMEZONES.get(t, "") + " " + TZ_NAMES.get(t, t)).strip() for t in tzs)
    members = cfg.get("last_members")
    font_name = FONTS.get(cfg.get("font", "default"), ("Default",))[0]

    status = "✅ فعال" if on else "⛔️ غیرفعال"
    txt = (
        "╭───────────────╮\n"
        "│  🕐 پنل مدیریت چت  │\n"
        "╰───────────────╯\n\n"
        f"📌 عنوان پایه: <b>{base}</b>\n"
        f"✨ وضعیت: <b>{status}</b>\n"
        f"⏱ بازه آپدیت: <b>{cfg.get('interval',60)} ثانیه</b>\n"
        f"🔤 فونت: <b>{font_name}</b>\n"
        f"🌍 تایم‌زون: <b>{tz_txt}</b>\n"
        f"👥 اعضا: <b>{members if members is not None else '—'}</b>\n"
        f"🆔 چت: <code>{cid}</code>\n"
        "─────────────────\n"
        "🔍 <u>پیش‌نمایش زنده عنوان:</u>\n"
        f"<b>{title}</b>\n"
        "─────────────────\n"
        "با دکمه‌های زیر بخش‌ها را روشن/خاموش کن 👇"
    )
    return txt

def welcome_text():
    return (
        "╔════════════════════╗\n"
        "   🕐 <b>ربات آپدیت عنوان چت</b>\n"
        "╚════════════════════╝\n\n"
        "سلام ادمین عزیز 👋\n"
        "این ربات عنوان کانال/گروه را به‌صورت خودکار "
        "با ساعت، تاریخ، وضعیت و مناسبت به‌روز می‌کند.\n\n"
        "✨ امکانات:\n"
        "• ۲۲ فونت پرمیوم یونیکد\n"
        "• نمایش همزمان چند تایم‌زون\n"
        "• پرچم کشورها، تاریخ شمسی، تعداد اعضا\n"
        "• 🟢 وضعیت و مناسبت‌های خاص\n\n"
        "🧑‍💻 <b>فقط ادمین</b> دسترسی دارد."
    )

# ───────────────────────── 13. COMMANDS ─────────────────────────
@router.message(CommandStart())
async def cmd_start(msg: Message):
    if not is_admin(msg.from_user.id):
        await msg.answer("⛔️ این ربات فقط برای ادمین است.\n🤖 <b>Time Channel Bot</b>")
        return
    await msg.answer(welcome_text(),
                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                         [InlineKeyboardButton(text="⚙️ پنل مدیریت", callback_data="menu")],
                     ]))

@router.message(Command("panel"))
async def cmd_panel(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("⛔️ فقط ادمین دسترسی دارد.")
    chats = await db.get_all()
    if not chats:
        txt = "📂 هنوز چتی اضافه نشده.\nبا دکمه زیر اولین چت را اضافه کن 👇"
    else:
        txt = "🎛 <b>پنل مدیریت</b>\n" + "─────────────────\n" + \
              f"تعداد چت‌های فعال: {sum(1 for c in chats if c.get('enabled'))} از {len(chats)}\nبرای مدیریت روی چت ضربه بزن 👇"
    await msg.answer(txt, reply_markup=main_menu(chats))

@router.message(Command("add"))
async def cmd_add(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("⛔️ فقط ادمین دسترسی دارد.")
    arg = msg.text.split(maxsplit=1)
    if len(arg) > 1:
        arg = arg[1].strip()
        if arg.lstrip("-").isdigit():
            chat_id = int(arg)
            title = await _probe_title(chat_id)
            cfg = default_config(chat_id, title)
            await db.save(cfg)
            return await msg.answer(f"✅ چت <code>{chat_id}</code> اضافه شد.", reply_markup=chat_panel_kb(cfg))
    await state.set_state(Form.add_chat)
    await msg.answer(
        "📥 <b>افزودن چت</b>\n"
        "برای اضافه‌کردن، یکی از این کارها را انجام بده:\n"
        "1️⃣ یک پیام از آن کانال/گروه را <u>فوروارد</u> کن (ترجیح)\n"
        "2️⃣ یا آیدی عددی چت را بفرست (مثل <code>-1001234567890</code>)\n\n"
        "⚠️ ربات باید در آن چت <b>ادمین</b> باشد."
    )

@router.message(Form.add_chat)
async def add_chat_handler(msg: Message, state: FSMContext):
    chat_id = None
    base_title = ""
    if msg.forward_from_chat:
        chat_id = msg.forward_from_chat.id
        base_title = getattr(msg.forward_from_chat, "title", "") or ""
    elif msg.text and msg.text.strip().lstrip("-").isdigit():
        chat_id = int(msg.text.strip())
        base_title = await _probe_title(chat_id)
    else:
        return await msg.answer("⚠️ پیام نامعتبر است. یا یک پیام فوروارد کن یا آیدی عددی چت را بفرست.")

    if not base_title:
        # عنوان ناشناخته → از ادمین بپرس
        await state.update_data(pending_chat=chat_id)
        await state.set_state(Form.set_title)
        return await msg.answer(f"✅ چت <code>{chat_id}</code> شناخته شد.\n"
                                "📝 حالا <b>عنوان پایه</b> (اسم کانال) را بفرست:")

    cfg = default_config(chat_id, base_title)
    await db.save(cfg)
    await state.clear()
    await msg.answer(f"✅ چت «{base_title}» اضافه شد.", reply_markup=chat_panel_kb(cfg))

@router.message(Form.set_title)
async def set_title_handler(msg: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data.get("pending_chat")
    title = msg.text.strip() if msg.text else ""
    if not title:
        return await msg.answer("⚠️ عنوان نمی‌تواند خالی باشد. دوباره بفرست:")
    cfg = await db.get(chat_id) or default_config(chat_id)
    cfg["base_title"] = title
    await db.save(cfg)
    await state.clear()
    await msg.answer(f"✅ عنوان پایه «{title}» ثبت شد.", reply_markup=chat_panel_kb(cfg))

async def _probe_title(chat_id):
    """تلاش برای گرفتن عنوان فعلی چت."""
    try:
        chat = await bot.get_chat(chat_id)
        return chat.title or chat.username or ""
    except Exception:
        return ""

# ───────────────────────── 14. CALLBACKS ─────────────────────────
@router.callback_query(F.data == "noop")
async def noop(cq: CallbackQuery):
    await cq.answer()

@router.callback_query(F.data == "menu")
async def cb_menu(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔️ فقط ادمین", show_alert=True)
    chats = await db.get_all()
    await cq.message.edit_text("🎛 <b>پنل مدیریت</b>\n─────────────────\n" +
                               f"تعداد چت‌های فعال: {sum(1 for c in chats if c.get('enabled'))} از {len(chats)}\n"
                               "برای مدیریت روی چت ضربه بزن 👇",
                               reply_markup=main_menu(chats))
    await cq.answer()

@router.callback_query(F.data == "add_chat")
async def cb_add_chat(cq: CallbackQuery, state: FSMContext):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔️ فقط ادمین", show_alert=True)
    await state.set_state(Form.add_chat)
    await cq.message.answer(
        "📥 <b>افزودن چت</b>\n"
        "1️⃣ یک پیام از آن کانال/گروه را فوروارد کن (ترجیح)\n"
        "2️⃣ یا آیدی عددی چت را بفرست\n\n"
        "⚠️ ربات باید در آن چت ادمین باشد."
    )
    await cq.answer()

@router.callback_query(F.data.startswith("chat:"))
async def cb_open_chat(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔️ فقط ادمین", show_alert=True)
    cid = int(cq.data.split(":")[1])
    cfg = await db.get(cid)
    if not cfg:
        return await cq.answer("⚠️ چت یافت نشد", show_alert=True)
    await cq.message.edit_text(panel_text(cfg), reply_markup=chat_panel_kb(cfg),
                               disable_web_page_preview=True, parse_mode="HTML")
    await cq.answer()

@router.callback_query(F.data.startswith("tog:"))
async def cb_toggle(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔️ فقط ادمین", show_alert=True)
    _, cid, key = cq.data.split(":")
    cfg = await db.get(int(cid))
    if not cfg:
        return await cq.answer("⚠️ چت یافت نشد", show_alert=True)
    cfg[key] = not cfg.get(key, False)
    await db.save(cfg)
    await cq.message.edit_text(panel_text(cfg), reply_markup=chat_panel_kb(cfg),
                               parse_mode="HTML")
    await cq.answer()

@router.callback_query(F.data.startswith("ivl:"))
async def cb_interval(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔️ فقط ادمین", show_alert=True)
    cid = int(cq.data.split(":")[1])
    cfg = await db.get(cid)
    if not cfg:
        return await cq.answer("⚠️ چت یافت نشد", show_alert=True)
    opts = [10, 30, 60, 120, 300, 600, 1800, 3600]
    cur = cfg.get("interval", 60)
    nxt = opts[(opts.index(cur) + 1) % len(opts)] if cur in opts else 60
    cfg["interval"] = nxt
    await db.save(cfg)
    await cq.answer(f"⏱ بازه: {nxt} ثانیه", show_alert=False)
    await cq.message.edit_text(panel_text(cfg), reply_markup=chat_panel_kb(cfg), parse_mode="HTML")

@router.callback_query(F.data.startswith("settitle:"))
async def cb_set_title(cq: CallbackQuery, state: FSMContext):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔️ فقط ادمین", show_alert=True)
    cid = int(cq.data.split(":")[1])
    await state.set_state(Form.set_title)
    await state.update_data(pending_chat=cid)
    await cq.message.answer("📝 <b>عنوان پایه</b> جدید (اسم کانال) را بفرست:")
    await cq.answer()

@router.callback_query(F.data.startswith("fnt:"))
async def cb_open_font(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔️ فقط ادمین", show_alert=True)
    cid = int(cq.data.split(":")[1])
    cfg = await db.get(cid)
    if not cfg:
        return await cq.answer("⚠️ چت یافت نشد", show_alert=True)
    await cq.message.edit_text(
        "🔤 <b>انتخاب فونت (۲۲ فونت پرمیوم)</b>\n"
        "پیش‌نمایش زنده روی دکمه‌ها نمایش داده شده 👇\n"
        "هر فونت را بزن تا اعمال شود.",
        reply_markup=font_kb(cfg), parse_mode="HTML")
    await cq.answer()

@router.callback_query(F.data.startswith("fsel:"))
async def cb_select_font(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔️ فقط ادمین", show_alert=True)
    _, cid, key = cq.data.split(":", 2)
    cfg = await db.get(int(cid))
    if not cfg:
        return await cq.answer("⚠️ چت یافت نشد", show_alert=True)
    cfg["font"] = key
    await db.save(cfg)
    name = FONTS[key][0]
    await cq.answer(f"✅ فونت «{name}» انتخاب شد")
    await cq.message.edit_text(panel_text(cfg), reply_markup=chat_panel_kb(cfg), parse_mode="HTML")

@router.callback_query(F.data.startswith("tz:"))
async def cb_open_tz(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔️ فقط ادمین", show_alert=True)
    cid = int(cq.data.split(":")[1])
    cfg = await db.get(cid)
    if not cfg:
        return await cq.answer("⚠️ چت یافت نشد", show_alert=True)
    await cq.message.edit_text(
        "🌍 <b>انتخاب تایم‌زون‌ها</b>\n"
        "چند تایم‌زون را می‌توانی همزمان انتخاب کنی (با پرچم).\n"
        "برای روشن/خاموش روی هر کدام ضربه بزن 👇",
        reply_markup=tz_kb(cfg), parse_mode="HTML")
    await cq.answer()

@router.callback_query(F.data.startswith("tzpg:"))
async def cb_tz_page(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔️ فقط ادمین", show_alert=True)
    _, cid, page = cq.data.split(":")
    cfg = await db.get(int(cid))
    if not cfg:
        return await cq.answer("⚠️ چت یافت نشد", show_alert=True)
    await cq.message.edit_text(
        "🌍 <b>انتخاب تایم‌زون‌ها</b>\n"
        "چند تایم‌زون را می‌توانی همزمان انتخاب کنی (با پرچم).",
        reply_markup=tz_kb(cfg, int(page)), parse_mode="HTML")
    await cq.answer()

@router.callback_query(F.data.startswith("tzsel:"))
async def cb_tz_select(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔️ فقط ادمین", show_alert=True)
    parts = cq.data.split(":")
    cid = int(parts[1])
    tz = ":".join(parts[2:])  # نام تایم‌زون ممکن است شامل ':' نباشد ولی امن
    cfg = await db.get(cid)
    if not cfg:
        return await cq.answer("⚠️ چت یافت نشد", show_alert=True)
    tzs = list(cfg.get("timezones") or [])
    if tz in tzs:
        if len(tzs) == 1:
            return await cq.answer("⚠️ حداقل یک تایم‌زون باید فعال باشد", show_alert=True)
        tzs.remove(tz)
    else:
        tzs.append(tz)
    cfg["timezones"] = tzs
    await db.save(cfg)
    await cq.answer()
    await cq.message.edit_text(
        "🌍 <b>انتخاب تایم‌زون‌ها</b>",
        reply_markup=tz_kb(cfg, 0), parse_mode="HTML")

@router.callback_query(F.data.startswith("upd:"))
async def cb_update(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔️ فقط ادمین", show_alert=True)
    cid = int(cq.data.split(":")[1])
    cfg = await db.get(cid)
    if not cfg:
        return await cq.answer("⚠️ چت یافت نشد", show_alert=True)
    await cq.answer("⚡️ در حال آپدیت...")
    try:
        title = await update_chat_title(cfg)
        await cq.message.answer(f"⚡️ عنوان چت آپدیت شد:\n<b>{title}</b>", parse_mode="HTML")
    except Exception as e:
        await cq.message.answer(f"⚠️ خطا در آپدیت: {e}")

@router.callback_query(F.data == "updall")
async def cb_update_all(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔️ فقط ادمین", show_alert=True)
    chats = await db.get_all()
    ok = 0
    await cq.answer("⚡️ آپدیت همه...")
    for cfg in chats:
        try:
            await update_chat_title(cfg)
            ok += 1
        except Exception:
            pass
        await asyncio.sleep(1)
    await cq.message.answer(f"⚡️ <b>{ok}</b> چت با موفقیت آپدیت شد.")

@router.callback_query(F.data.startswith("preview:"))
async def cb_preview(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔️ فقط ادمین", show_alert=True)
    cid = int(cq.data.split(":")[1])
    cfg = await db.get(cid)
    if not cfg:
        return await cq.answer("⚠️ چت یافت نشد", show_alert=True)
    await cq.answer("👀 پیش‌نمایش", show_alert=False)
    await cq.message.edit_text(panel_text(cfg), reply_markup=chat_panel_kb(cfg), parse_mode="HTML")

@router.callback_query(F.data.startswith("del:"))
async def cb_delete(cq: CallbackQuery):
    if not is_admin(cq.from_user.id):
        return await cq.answer("⛔️ فقط ادمین", show_alert=True)
    cid = int(cq.data.split(":")[1])
    cfg = await db.get(cid)
    name = (cfg.get("base_title") or cid) if cfg else cid
    await db.delete(cid)
    await cq.message.edit_text(f"🗑 چت «{name}» حذف شد.", reply_markup=main_menu(await db.get_all()))
    await cq.answer("حذف شد")

# ───────────────────────── 15. MAIN ─────────────────────────
async def _run_polling():
    """اجرای polling با تلاش مجدد هنگام قطعی شبکه."""
    retry = 5
    while True:
        try:
            await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
            return
        except TelegramNetworkError as e:
            log.error(f"Network error: {e}. Reconnecting in {retry}s...")
        except TelegramRetryAfter as e:
            await asyncio.sleep(getattr(e, "retry_after", retry))
        except TelegramAPIError as e:
            log.error(f"API error during polling: {e}. Retrying in {retry}s...")
        except asyncio.CancelledError:
            raise
        await asyncio.sleep(retry)
        retry = min(retry * 2, 60)

async def main():
    await db.init()
    log.info("Database ready. Starting background updater...")
    asyncio.create_task(updater_loop())
    log.info("Polling started.")
    await _run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot stopped by user.")
