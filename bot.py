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
from aiogram.types import Message, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', '').strip()
BRAND_NAME = os.getenv('BRAND_NAME', 'بوت أبو دره الشريف').strip()

if not TOKEN:
    raise RuntimeError('TELEGRAM_BOT_TOKEN is missing')

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

DB_PATH = 'abudorh_bot.db'
FLOOD_LIMIT = 6
FLOOD_WINDOW = 10
MAX_WARNINGS = 2
MUTE_MINUTES = 60
flood_cache = defaultdict(lambda: deque(maxlen=30))

SEXUAL_RE = re.compile(r'(?:porn|porno|xxx|sex|nude|onlyfans|اباحي|إباحي|اباحية|إباحية|جنسي|جنسية|سكس|عاري|عارية)', re.I)
AD_RE = re.compile(r'(?:اعلان|إعلان|دعاية|ترويج|عرض خاص|خصم حصري|احجز الآن|راسلني خاص|تواصل خاص|واتساب|واتس اب|للبيع|للإيجار|قناتنا|مجموعتنا|تابعنا)', re.I)

TOURISM = {
    'البوسنة': 'البوسنة من أفضل الوجهات للعائلات ومحبي الطبيعة. أبرز المدن: سراييفو، موستار، بيهاتش، يايتسى، ترافنيك وفلاشيتش.',
    'تركيا': 'تركيا مناسبة للعائلات والتسوق والطبيعة. من أشهر الوجهات: إسطنبول، طرابزون، بورصة وأنطاليا.',
    'جورجيا': 'جورجيا مناسبة للطبيعة والجبال. من أشهر الوجهات: تبليسي، باتومي وكازبيجي.',
    'كازاخستان': 'كازاخستان مميزة بالطبيعة والجبال، وألماتي من أبرز المدن السياحية.',
}

CITY_INFO = {
    'سراييفو': 'من أبرز الأماكن: باشچارشيا، التلفريك، نفق الحياة، فريلو بوسنة، جبل تريبفيتش وصني لاند.',
    'بيهاتش': 'بيهاتش ممتازة للطبيعة ونهر أونا. من أبرز الرحلات: شلال شترباتشكي بوك ومارتن برود، وتناسب غالبًا 2 إلى 3 ليالٍ.',
    'موستار': 'من أبرز الأماكن: الجسر القديم، المدينة القديمة، بلاغاي، بوتشيتلي وشلالات كرافيتسا.',
    'يايتسى': 'يايتسى معروفة بالشلال وسط المدينة وبحيرات بليفا والطواحين الخشبية، وتناسب ليلة أو زيارة يوم كامل.',
    'يايتسه': 'يايتسى معروفة بالشلال وسط المدينة وبحيرات بليفا والطواحين الخشبية، وتناسب ليلة أو زيارة يوم كامل.',
    'ترافنيك': 'ترافنيك مناسبة لزيارة القلعة والمدينة القديمة، ويمكن دمجها مع فلاشيتش في نفس المسار.',
    'فلاشيتش': 'فلاشيتش منطقة جبلية مناسبة للطبيعة والهدوء والأجواء الباردة، ومناسبة للعائلات.',
    'كونيتس': 'كونيتس بلدة جميلة على نهر نيريتفا، وتناسب التوقف بين سراييفو وموستار والأنشطة النهرية.',
    'توزلا': 'توزلا مدينة هادئة تشتهر ببحيرات الملح، وتناسب من يريد إضافة وجهة مختلفة داخل البوسنة.',
}

ROUTES = {
    ('سراييفو', 'موستار'): 'المسافة تقريبًا 130 كم، والقيادة غالبًا ساعتان إلى ساعتين ونصف بحسب الطريق والتوقفات.',
    ('سراييفو', 'بيهاتش'): 'المسافة تقريبًا 300–315 كم، والقيادة غالبًا 4.5 إلى 5 ساعات.',
    ('سراييفو', 'ترافنيك'): 'المسافة تقريبًا 90 كم، والقيادة غالبًا قرابة ساعة ونصف.',
    ('سراييفو', 'يايتسى'): 'المسافة تقريبًا 160 كم، والقيادة غالبًا 2.5 إلى 3 ساعات.',
    ('سراييفو', 'يايتسه'): 'المسافة تقريبًا 160 كم، والقيادة غالبًا 2.5 إلى 3 ساعات.',
    ('موستار', 'سراييفو'): 'المسافة تقريبًا 130 كم، والقيادة غالبًا ساعتان إلى ساعتين ونصف.',
    ('بيهاتش', 'سراييفو'): 'المسافة تقريبًا 300–315 كم، والقيادة غالبًا 4.5 إلى 5 ساعات.',
}

SERVICES = ['🚗 تأجير سيارة','🏡 سكن / فيلا / شقة','🏨 فندق','🗺 برنامج سياحي','🚐 سائق / نقل','🛂 تأشيرة','📱 شريحة eSIM','✈️ تذاكر سفر']
QUESTION_WORDS = ['وين','أين','اين','كيف','كم','وش','ماهي','ما هي','افضل','أفضل','تنصح','هل','متى','طريق','المسافة','أماكن','اماكن','فعاليات','سكن','فندق','سيارة','سائق','تأشيرة','برنامج','رحلة','مطعم','مطاعم']

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS members(chat_id INTEGER,user_id INTEGER,warnings INTEGER DEFAULT 0,PRIMARY KEY(chat_id,user_id))')
        conn.execute('CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,text TEXT,created_at TEXT)')
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
        conn.execute('INSERT OR IGNORE INTO members(chat_id,user_id,warnings) VALUES(?,?,0)', (chat_id, user_id))
        conn.execute('UPDATE members SET warnings=warnings+1 WHERE chat_id=? AND user_id=?', (chat_id, user_id))
        conn.commit()
        return conn.execute('SELECT warnings FROM members WHERE chat_id=? AND user_id=?', (chat_id, user_id)).fetchone()['warnings']

async def punish(message: Message, reason: str):
    try:
        await message.delete()
    except Exception:
        pass
    warnings = add_warning(message.chat.id, message.from_user.id)
    try:
        if warnings >= MAX_WARNINGS:
            await bot.ban_chat_member(message.chat.id, message.from_user.id)
            action = 'حظر'
        else:
            until = datetime.now(timezone.utc) + timedelta(minutes=MUTE_MINUTES)
            await bot.restrict_chat_member(message.chat.id, message.from_user.id, ChatPermissions(can_send_messages=False), until_date=until)
            action = f'كتم {MUTE_MINUTES} دقيقة'
    except Exception:
        action = 'حذف الرسالة'
    if ADMIN_CHAT_ID:
        try:
            await bot.send_message(int(ADMIN_CHAT_ID), f'🛡 <b>مخالفة</b>\nالعضو: {message.from_user.full_name}\nالسبب: {reason}\nالإجراء: {action}')
        except Exception:
            pass

def route_answer(text: str):
    low = text.lower()
    for (a, b), answer in ROUTES.items():
        if a in low and b in low:
            return f'🚗 <b>{a} ← {b}</b>\n{answer}'
    return None

def tourism_answer(text: str):
    low = text.lower().strip()
    route = route_answer(low)
    if route:
        return route
    for city, answer in CITY_INFO.items():
        if city in low:
            return f'📍 <b>{city}</b>\n{answer}'
    for country, answer in TOURISM.items():
        if country in low:
            return f'🌍 <b>{country}</b>\n{answer}'
    if any(x in low for x in ['وين اسافر','وين أسافر','اقترح وجهة','أفضل دولة','افضل دولة']):
        return '✈️ أرسل لي شهر السفر، عدد الأيام، عدد المسافرين، الميزانية، وهل تفضل طبيعة أو مدن أو شواطئ.'
    if any(x in low for x in ['طريق','كيف اروح','كيف أروح','المسافة','كم ساعة','كم تبعد']):
        return '🚗 اكتب اسم المدينتين في نفس الرسالة، مثال:\nكم تبعد سراييفو عن موستار؟'
    if any(x in low for x in ['افضل مكان','أفضل مكان','أماكن','اماكن','فعاليات','وين نروح']):
        return '📍 اكتب اسم المدينة التي تقصدها، مثال:\nأفضل الأماكن في بيهاتش؟'
    return None

def looks_like_tourism_question(text: str):
    low = text.lower().strip()
    if not low:
        return False
    if '؟' in text or '?' in text:
        return True
    return any(word in low for word in QUESTION_WORDS)

@router.message(CommandStart())
async def start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📩 طلب خدمة سياحية', callback_data='request_service')]])
    await message.answer(f'أهلًا بك في <b>{BRAND_NAME}</b> ✈️\n\nمساعد سياحي عام، ويعمل في المجموعات كنظام حماية من الدعايات والمحتوى الإباحي والسبام.', reply_markup=kb)

@router.callback_query(F.data == 'request_service')
async def request_service(cb):
    await cb.message.answer('اكتب طلبك في رسالة واحدة مع:\n• نوع الخدمة\n• الدولة/المدينة\n• تاريخ السفر\n• عدد المسافرين\n• رقم الجوال\n\nوسأحفظ الطلب للإدارة.')
    await cb.answer()

@router.message(Command('services'))
async def services(message: Message):
    await message.answer('<b>الخدمات:</b>\n' + '\n'.join(SERVICES))

@router.message(Command('request'))
async def request_cmd(message: Message):
    await message.answer('أرسل طلبك في رسالة واحدة، مثال:\nفندق في سراييفو - 20 أكتوبر - 4 أشخاص - 05xxxxxxxx')

@router.message()
async def handle_all(message: Message):
    # يرد على البشر فقط، ويتجاهل البوتات الأخرى
    if not message.from_user or message.from_user.is_bot:
        return

    text = (message.text or message.caption or '').strip()

    if message.chat.type in {'group', 'supergroup'} and not await is_admin(message):
        if SEXUAL_RE.search(text):
            return await punish(message, 'محتوى أو إيحاء جنسي/إباحي')
        if AD_RE.search(text):
            return await punish(message, 'إعلان أو ترويج غير مصرح')
        if 't.me/' in text.lower():
            return await punish(message, 'رابط قناة أو مجموعة دعائي')
        if is_flood(message):
            return await punish(message, 'Spam / Flood')

    if not text:
        return

    answer = tourism_answer(text)
    if answer:
        return await message.reply(answer)

    # أي سؤال بشري داخل المجموعة يحصل على رد مساعد بدل تجاهله
    if message.chat.type in {'group', 'supergroup'} and looks_like_tourism_question(text):
        return await message.reply('✈️ حاضر، أقدر أساعدك.\nاكتب اسم الدولة أو المدينة وتفاصيل سؤالك، مثل:\n• أفضل الأماكن في بيهاتش؟\n• كم تبعد سراييفو عن موستار؟\n• أبغى برنامج للبوسنة 8 أيام.')

    keywords = ['حجز','فندق','سيارة','سائق','فيلا','تأشيرة','esim','تذكرة','برنامج','سكن']
    if message.chat.type == 'private' and any(k in text.lower() for k in keywords):
        with db() as conn:
            cur = conn.execute('INSERT INTO requests(user_id,text,created_at) VALUES(?,?,?)', (message.from_user.id, text, datetime.now().isoformat()))
            conn.commit()
            req_no = f'AD-{cur.lastrowid:05d}'
        await message.answer(f'✅ تم استلام طلبك\nرقم الطلب: <code>{req_no}</code>')
        if ADMIN_CHAT_ID:
            try:
                await bot.send_message(int(ADMIN_CHAT_ID), f'📩 طلب جديد {req_no}\n\n{text}')
            except Exception:
                pass
        return

    if message.chat.type == 'private':
        await message.answer('✈️ اكتب سؤالك السياحي، أو اذكر الدولة/المدينة التي تريد معلومات عنها.\nمثال: أفضل الأماكن في سراييفو؟')

async def main():
    init_db()
    print('Abudorh bot is running...')
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
