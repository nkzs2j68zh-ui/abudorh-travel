import os
import re
import time
import sqlite3
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
)
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()
BRAND_NAME = os.getenv("BRAND_NAME", "بوت أبو دره الشريف").strip()

if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

DB_PATH = "abudorh_bot.db"
FLOOD_LIMIT = 6
FLOOD_WINDOW = 10
MAX_WARNINGS = 2
MUTE_MINUTES = 60
flood_cache = defaultdict(lambda: deque(maxlen=30))

SEXUAL_RE = re.compile(
    r"(?:porn|porno|xxx|sex|nude|onlyfans|"
    r"اباحي|إباحي|اباحية|إباحية|جنسي|جنسية|سكس|عاري|عارية)",
    re.I
)

AD_RE = re.compile(
    r"(?:اعلان|إعلان|دعاية|ترويج|عرض خاص|خصم حصري|"
    r"احجز الآن|راسلني خاص|تواصل خاص|واتساب|واتس اب|"
    r"للبيع|للإيجار|قناتنا|مجموعتنا|تابعنا)",
    re.I
)

URL_RE = re.compile(r"https?://\S+|www\.\S+|t\.me/\S+", re.I)

TOURISM = {
    "البوسنة": "البوسنة ممتازة للطبيعة والأنهار والجبال. من أشهر الوجهات: سراييفو، موستار، يايتسى وبيهاتش.",
    "تركيا": "تركيا مناسبة للعائلات والتسوق والطبيعة. من أشهر الوجهات: إسطنبول، طرابزون، بورصة وأنطاليا.",
    "جورجيا": "جورجيا مناسبة للطبيعة والجبال. من أشهر الوجهات: تبليسي، باتومي وكازبيجي.",
    "كازاخستان": "كازاخستان مميزة بالطبيعة والجبال، وألماتي من أبرز المدن السياحية.",
}

SERVICES = [
    "🚗 تأجير سيارة",
    "🏡 سكن / فيلا / شقة",
    "🏨 فندق",
    "🗺 برنامج سياحي",
    "🚐 سائق / نقل",
    "🛂 تأشيرة",
    "📱 شريحة eSIM",
    "✈️ تذاكر سفر",
]

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS members(
            chat_id INTEGER,
            user_id INTEGER,
            warnings INTEGER DEFAULT 0,
            PRIMARY KEY(chat_id, user_id)
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            created_at TEXT
        )
        """)
        conn.commit()

async def is_admin(message: Message):
    try:
        m = await bot.get_chat_member(message.chat.id, message.from_user.id)
        return m.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}
    except Exception:
        return False

def is_flood(message: Message):
    key = (message.chat.id, message.from_user.id)
    now = time.time()
    q = flood_cache[key]
    q.append(now)
    while q and now - q[0] > FLOOD_WINDOW:
        q.popleft()
    return len(q) >= FLOOD_LIMIT

def add_warning(chat_id: int, user_id: int):
    with db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO members(chat_id,user_id,warnings) VALUES(?,?,0)",
            (chat_id, user_id)
        )
        conn.execute(
            "UPDATE members SET warnings=warnings+1 WHERE chat_id=? AND user_id=?",
            (chat_id, user_id)
        )
        conn.commit()
        return conn.execute(
            "SELECT warnings FROM members WHERE chat_id=? AND user_id=?",
            (chat_id, user_id)
        ).fetchone()["warnings"]

async def punish(message: Message, reason: str):
    try:
        await message.delete()
    except Exception:
        pass

    warnings = add_warning(message.chat.id, message.from_user.id)

    try:
        if warnings >= MAX_WARNINGS:
            await bot.ban_chat_member(message.chat.id, message.from_user.id)
            action = "حظر"
        else:
            until = datetime.now(timezone.utc) + timedelta(minutes=MUTE_MINUTES)
            await bot.restrict_chat_member(
                message.chat.id,
                message.from_user.id,
                ChatPermissions(can_send_messages=False),
                until_date=until
            )
            action = f"كتم {MUTE_MINUTES} دقيقة"
    except Exception:
        action = "حذف الرسالة"

    if ADMIN_CHAT_ID:
        try:
            await bot.send_message(
                int(ADMIN_CHAT_ID),
                f"🛡 <b>مخالفة</b>\n"
                f"العضو: {message.from_user.full_name}\n"
                f"السبب: {reason}\n"
                f"الإجراء: {action}"
            )
        except Exception:
            pass

def tourism_answer(text: str):
    low = text.lower()
    for country, answer in TOURISM.items():
        if country in low:
            return f"🌍 <b>{country}</b>\n{answer}"

    if any(x in low for x in ["وين اسافر", "وين أسافر", "اقترح وجهة", "أفضل دولة"]):
        return (
            "✈️ أرسل لي: شهر السفر، عدد الأيام، عدد المسافرين، "
            "الميزانية، وهل تفضل طبيعة أو مدن أو شواطئ."
        )
    return None

@router.message(CommandStart())
async def start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📩 طلب خدمة سياحية", callback_data="request_service")]
    ])
    await message.answer(
        f"أهلًا بك في <b>{BRAND_NAME}</b> ✈️\n\n"
        "مساعد سياحي عام، ويعمل في المجموعات كنظام حماية من "
        "الدعايات والمحتوى الإباحي والسبام.",
        reply_markup=kb
    )

@router.callback_query(F.data == "request_service")
async def request_service(cb):
    await cb.message.answer(
        "اكتب طلبك في رسالة واحدة مع:\n"
        "• نوع الخدمة\n• الدولة/المدينة\n• تاريخ السفر\n"
        "• عدد المسافرين\n• رقم الجوال\n\n"
        "وسأحفظ الطلب للإدارة."
    )
    await cb.answer()

@router.message(Command("services"))
async def services(message: Message):
    await message.answer("<b>الخدمات:</b>\n" + "\n".join(SERVICES))

@router.message(Command("request"))
async def request_cmd(message: Message):
    await message.answer(
        "أرسل طلبك في رسالة واحدة، مثال:\n"
        "فندق في سراييفو - 20 أكتوبر - 4 أشخاص - 05xxxxxxxx"
    )

@router.message()
async def handle_all(message: Message):
    if not message.from_user or message.from_user.is_bot:
        return

    text = (message.text or message.caption or "").strip()

    if message.chat.type in {"group", "supergroup"} and not await is_admin(message):
        if SEXUAL_RE.search(text):
            return await punish(message, "محتوى أو إيحاء جنسي/إباحي")
        if AD_RE.search(text):
            return await punish(message, "إعلان أو ترويج غير مصرح")
        if "t.me/" in text.lower():
            return await punish(message, "رابط قناة أو مجموعة دعائي")
        if is_flood(message):
            return await punish(message, "Spam / Flood")

    if text:
        answer = tourism_answer(text)
        if answer:
            return await message.reply(answer)

        # التقاط طلب سياحي بسيط
        keywords = ["حجز", "فندق", "سيارة", "سائق", "فيلا", "تأشيرة", "esim", "تذكرة"]
        if message.chat.type == "private" and any(k in text.lower() for k in keywords):
            with db() as conn:
                cur = conn.execute(
                    "INSERT INTO requests(user_id,text,created_at) VALUES(?,?,?)",
                    (message.from_user.id, text, datetime.now().isoformat())
                )
                conn.commit()
                req_no = f"AD-{cur.lastrowid:05d}"
            await message.answer(f"✅ تم استلام طلبك\nرقم الطلب: <code>{req_no}</code>")
            if ADMIN_CHAT_ID:
                try:
                    await bot.send_message(
                        int(ADMIN_CHAT_ID),
                        f"📩 طلب جديد {req_no}\n\n{text}"
                    )
                except Exception:
                    pass

async def main():
    init_db()
    print("Abudorh bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
