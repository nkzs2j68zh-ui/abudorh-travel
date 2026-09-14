import os, re, time, sqlite3
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
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
FLOOD_LIMIT = 7
FLOOD_WINDOW = 10
MUTE_MINUTES = 30
BAN_AFTER_WARNINGS = 6
flood_cache = defaultdict(lambda: deque(maxlen=30))

SEXUAL_RE = re.compile(r"(?:porn|porno|xxx|sex|nude|onlyfans|اباحي|إباحي|اباحية|إباحية|جنسي|جنسية|سكس|عاري|عارية)", re.I)
AD_RE = re.compile(r"(?:اعلان مدفوع|إعلان مدفوع|دعاية تجارية|ترويج مدفوع|عرض خاص|خصم حصري|احجز الآن|للبيع|للإيجار|قناتنا|مجموعتنا|تابعنا)", re.I)

CAR_REPLY = '''🚘 <b>للسيارات بسائق أو بدون سائق</b>

التواصل واتساب أبو دره:
wa.me/966543171395

أو أ/ أحمد الزهراني:
0966566117011 📞'''

SARAJEVO_HOSPITAL_REPLY = '''🏨 <b>مستشفيات سراييفو</b>

🔺 مستشفى الدكتور عبدالله وكاش العام – 24 ساعة
https://maps.app.goo.gl/PsDzNkZiJ5zHTrtE8?g_st=iwb

🔺 مستشفى أطفال AV paediatric
https://maps.app.goo.gl/G6QYiiGzXUvFZnzf8?g_st=iw

🔺 مستشفى للكبار والأطفال
https://maps.app.goo.gl/L6uTMyeALyBEV5nL7?g_st=ic

🔺 مستشفى ساناسا – إليجا
https://maps.app.goo.gl/Z5hXMDFoQf5gzex3A?g_st=ic'''

EXCHANGE_REPLY = '''💸📍 <b>مواقع خدمة تبديل العملة في سراييفو</b>

🔺 البلدة القديمة:
1) https://maps.app.goo.gl/deyfQtNPKGsFJBQg8
2) https://maps.app.goo.gl/dEqcgtAuPKzYh1eh6
3) https://maps.app.goo.gl/7XNh1ZTMWCERntLA6
4) https://maps.app.goo.gl/BHos58nXiPPXXQZq8
5) https://maps.app.goo.gl/M9wrfCGt1LuR4AnM7

🔺 بالقرب من البلدة القديمة:
• ألتا مول:
https://maps.app.goo.gl/zfSfhKXgayHShCyLA
• BBI مول:
https://maps.app.goo.gl/WwG9cPcuHrhAfmME7
• سراييفو سيتي سنتر:
https://maps.app.goo.gl/igwnoxJJta8xYubS7

🔺 بين السنتر وإليجا:
• Bingo City Centre:
https://maps.app.goo.gl/99RhWhwuhUDDpiYg6

🔺 إليجا:
• مركز سارة:
https://maps.app.goo.gl/33qufLYyw6RGUMfC6
• جراند سنتر:
https://maps.app.goo.gl/c5fPDed3DFcpfVXPA

🔺 مطار سراييفو:
https://maps.app.goo.gl/bSpSbFH2yHSpEhZf6?g_st=ic

🔺 بالقرب من إليجا – Penny Plus:
https://g.co/kgs/Kev7yqZ

ملاحظة: أسعار الصرف والعمولات تختلف من صراف لآخر.'''

SARAJEVO_TERMS = ["سراييفو", "سرايفو", "sarajevo"]
BIHAC_TERMS = ["بيهاتش", "بيهاج", "bihac", "bihać"]

HOSPITAL_PATTERNS = [r"مستشفى", r"مستشفيات", r"طوارئ", r"مستشفى اطفال", r"مستشفى أطفال"]
EXCHANGE_PATTERNS = [r"صراف", r"صرافين", r"صرف عملة", r"تبديل عملة", r"وين اصرف", r"وين أصرف", r"تحويل عملة"]
CAR_PATTERNS = [
    r"ابغى شركة تأجير", r"أبغى شركة تأجير", r"احتاج شركة تأجير", r"أحتاج شركة تأجير",
    r"شركة تأجير سيارات", r"ابغى سيارة بسائق", r"أبغى سيارة بسائق", r"احتاج سيارة بسائق",
    r"أحتاج سيارة بسائق", r"ابغى سيارة بدون سائق", r"أبغى سيارة بدون سائق",
    r"احتاج سيارة بدون سائق", r"أحتاج سيارة بدون سائق", r"ابغى سائق", r"أبغى سائق",
    r"احتاج سائق", r"أحتاج سائق", r"ابغى سايق", r"أبغى سايق", r"احتاج سايق",
    r"أحتاج سايق", r"مين يوفر سيارة", r"من يوفر سيارة", r"مين عنده شركة سيارات",
    r"شركة سيارات", r"ابغى شركة سياحية", r"أبغى شركة سياحية", r"احتاج شركة سياحية",
    r"أحتاج شركة سياحية", r"شركة سياحية"
]
hospital_rx = [re.compile(p, re.I) for p in HOSPITAL_PATTERNS]
exchange_rx = [re.compile(p, re.I) for p in EXCHANGE_PATTERNS]
car_rx = [re.compile(p, re.I) for p in CAR_PATTERNS]

def contains_any(text, terms):
    low = text.lower()
    return any(t.lower() in low for t in terms)

def matches_any(text, pats):
    return any(p.search(text) for p in pats)

def detect_service_request(text):
    low = text.lower().strip()
    if matches_any(low, hospital_rx):
        if contains_any(low, SARAJEVO_TERMS):
            return "hospital_sarajevo"
        if contains_any(low, BIHAC_TERMS):
            return None
        return None
    if matches_any(low, exchange_rx):
        if contains_any(low, BIHAC_TERMS):
            return None
        return "exchange_sarajevo"
    if matches_any(low, car_rx):
        return "car_service"
    return None

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS members(chat_id INTEGER, user_id INTEGER, warnings INTEGER DEFAULT 0, PRIMARY KEY(chat_id,user_id))")
        conn.commit()

async def is_admin(message):
    try:
        m = await bot.get_chat_member(message.chat.id, message.from_user.id)
        return m.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}
    except Exception:
        return False

def is_flood(message):
    key = (message.chat.id, message.from_user.id)
    now = time.time()
    q = flood_cache[key]
    q.append(now)
    while q and now - q[0] > FLOOD_WINDOW:
        q.popleft()
    return len(q) >= FLOOD_LIMIT

def add_warning(chat_id, user_id):
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO members(chat_id,user_id,warnings) VALUES(?,?,0)", (chat_id,user_id))
        conn.execute("UPDATE members SET warnings=warnings+1 WHERE chat_id=? AND user_id=?", (chat_id,user_id))
        conn.commit()
        return conn.execute("SELECT warnings FROM members WHERE chat_id=? AND user_id=?", (chat_id,user_id)).fetchone()["warnings"]

async def moderate(message, reason, severe=False):
    try:
        await message.delete()
    except Exception:
        pass
    warnings = add_warning(message.chat.id, message.from_user.id)
    action = "حذف الرسالة"
    try:
        if severe:
            if warnings >= BAN_AFTER_WARNINGS:
                await bot.ban_chat_member(message.chat.id, message.from_user.id)
                action = "حظر بعد تكرار المخالفات"
            elif warnings >= 2:
                until = datetime.now(timezone.utc) + timedelta(minutes=MUTE_MINUTES)
                await bot.restrict_chat_member(message.chat.id, message.from_user.id, ChatPermissions(can_send_messages=False), until_date=until)
                action = f"كتم {MUTE_MINUTES} دقيقة"
        elif warnings >= 5:
            until = datetime.now(timezone.utc) + timedelta(minutes=MUTE_MINUTES)
            await bot.restrict_chat_member(message.chat.id, message.from_user.id, ChatPermissions(can_send_messages=False), until_date=until)
            action = f"كتم {MUTE_MINUTES} دقيقة"
    except Exception:
        action = "حذف الرسالة"
    if ADMIN_CHAT_ID:
        try:
            await bot.send_message(int(ADMIN_CHAT_ID), f"🛡 <b>مخالفة</b>\nالعضو: {message.from_user.full_name}\nالسبب: {reason}\nالإجراء: {action}")
        except Exception:
            pass

@router.message(CommandStart())
async def start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚘 طلب سيارة / سائق", callback_data="car_service")]])
    await message.answer(
        f"أهلًا بك في <b>{BRAND_NAME}</b> ✈️\n\n"
        "داخل المجموعة أتدخل فقط في:\n"
        "• مستشفيات سراييفو\n"
        "• صرافين سراييفو\n"
        "• طلب سيارة / سائق / شركة سياحية\n\n"
        "وباقي الأسئلة نتركها لتفاعل أعضاء المجموعة.",
        reply_markup=kb
    )

@router.callback_query(lambda c: c.data == "car_service")
async def car_service_callback(cb):
    await cb.message.answer(CAR_REPLY)
    await cb.answer()

@router.message(Command("services"))
async def services(message: Message):
    await message.answer("🏨 مستشفيات سراييفو\n💸 صرافين سراييفو\n🚘 سيارة بسائق أو بدون سائق / شركة سياحية")

@router.message()
async def handle_all(message: Message):
    if not message.from_user or message.from_user.is_bot:
        return
    text = (message.text or message.caption or "").strip()
    if not text:
        return

    if message.chat.type in {"group","supergroup"} and not await is_admin(message):
        if SEXUAL_RE.search(text):
            return await moderate(message, "محتوى أو إيحاء جنسي/إباحي", severe=True)
        if AD_RE.search(text):
            return await moderate(message, "إعلان أو ترويج غير مصرح", severe=False)
        if "t.me/" in text.lower():
            return await moderate(message, "رابط قناة أو مجموعة دعائي", severe=False)
        if is_flood(message):
            return await moderate(message, "Spam / Flood", severe=False)

    service = detect_service_request(text)

    if service == "hospital_sarajevo":
        return await message.reply(SARAJEVO_HOSPITAL_REPLY)
    if service == "exchange_sarajevo":
        return await message.reply(EXCHANGE_REPLY)
    if service == "car_service":
        return await message.reply(CAR_REPLY)

    if message.chat.type in {"group","supergroup"}:
        return

    await message.answer(
        "✈️ اكتب طلبك بشكل واضح، مثل:\n"
        "• أحتاج مستشفى في سراييفو\n"
        "• وين أصرف في سراييفو؟\n"
        "• أبغى سيارة بسائق\n"
        "• أبغى شركة سياحية"
    )

async def main():
    init_db()
    print("Abudorh bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
