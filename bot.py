
import os
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB = "cashik.db"

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

def db():
    return sqlite3.connect(DB)

def init_db():
    con = db()
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        invited_by INTEGER, created_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS offers(
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, category TEXT,
        description TEXT, reward TEXT, time TEXT, url TEXT, active INTEGER DEFAULT 1
    )""")
    con.commit()
    con.close()

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Заработать", callback_data="earn"),
         InlineKeyboardButton(text="🔥 Быстро", callback_data="fast")],
        [InlineKeyboardButton(text="🎁 Бонусы", callback_data="bonuses"),
         InlineKeyboardButton(text="🛍 Продать вещи", callback_data="sell")],
        [InlineKeyboardButton(text="💻 Онлайн-подработка", callback_data="online")],
        [InlineKeyboardButton(text="👥 Пригласить друга", callback_data="invite"),
         InlineKeyboardButton(text="📊 Мой прогресс", callback_data="stats")]
    ])

def offer_kb(url: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Перейти к предложению", url=url)],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="home")]
    ])

async def show_offers(callback: CallbackQuery, category=None):
    con = db()
    cur = con.cursor()
    if category:
        cur.execute("SELECT title,description,reward,time,url FROM offers WHERE active=1 AND category=? ORDER BY id DESC", (category,))
    else:
        cur.execute("SELECT title,description,reward,time,url FROM offers WHERE active=1 ORDER BY id DESC")
    rows = cur.fetchall()
    con.close()
    if not rows:
        await callback.message.edit_text(
            "Пока здесь нет предложений.\n\nАдминистратор может добавить их позже.",
            reply_markup=main_kb())
        return
    for i, (title, desc, reward, time_, url) in enumerate(rows):
        text = f"<b>{title}</b>\n\n{desc}\n\n💰 Потенциальный доход: {reward}\n⏱ Время: {time_}\n\n<i>Условия могут меняться — проверяй их на странице предложения.</i>"
        if i == 0:
            await callback.message.edit_text(text, reply_markup=offer_kb(url))
        else:
            await callback.message.answer(text, reply_markup=offer_kb(url))

@dp.message(CommandStart())
async def start(message: Message):
    init_db()
    payload = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    invited_by = int(payload[3:]) if payload.startswith("ref") and payload[3:].isdigit() else None
    con = db()
    cur = con.cursor()
    cur.execute("SELECT id FROM users WHERE id=?", (message.from_user.id,))
    exists = cur.fetchone()
    if not exists:
        cur.execute("INSERT INTO users VALUES(?,?,?,?,?)",
                    (message.from_user.id, message.from_user.username, message.from_user.first_name,
                     invited_by if invited_by != message.from_user.id else None,
                     datetime.utcnow().isoformat()))
        con.commit()
    con.close()
    await message.answer(
        "💸 <b>ДеньгиGO</b>\n\n"
        "Сервис с идеями для дополнительного заработка: подработки, продажа вещей, бонусные и партнёрские предложения.\n\n"
        "⚠️ Мы не гарантируем доход. Всегда проверяй условия конкретного предложения.",
        reply_markup=main_kb())

@dp.callback_query(F.data == "home")
async def home(c: CallbackQuery):
    await c.message.edit_text("💸 <b>ДеньгиGO</b>\n\nВыбери раздел:", reply_markup=main_kb())
    await c.answer()

@dp.callback_query(F.data == "earn")
async def earn(c: CallbackQuery):
    await show_offers(c)
    await c.answer()

@dp.callback_query(F.data == "fast")
async def fast(c: CallbackQuery):
    await show_offers(c, "fast")
    await c.answer()

@dp.callback_query(F.data == "bonuses")
async def bonuses(c: CallbackQuery):
    await show_offers(c, "bonus")
    await c.answer()

@dp.callback_query(F.data == "online")
async def online(c: CallbackQuery):
    await show_offers(c, "online")
    await c.answer()

@dp.callback_query(F.data == "sell")
async def sell(c: CallbackQuery):
    await c.message.edit_text(
        "🛍 <b>Продажа вещей</b>\n\n"
        "1. Выбери 3–5 хороших фото.\n"
        "2. Напиши бренд, размер и состояние.\n"
        "3. Сравни цены похожих объявлений.\n"
        "4. Размести объявление на подходящей площадке.\n\n"
        "💡 Если хочешь, позже в боте можно добавить автоматическое создание текста объявления.",
        reply_markup=main_kb())
    await c.answer()

@dp.callback_query(F.data == "invite")
async def invite(c: CallbackQuery):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref{c.from_user.id}"
    await c.message.edit_text(
        "👥 <b>Пригласи друга</b>\n\n"
        "Отправь эту ссылку другу:\n"
        f"<code>{link}</code>\n\n"
        "Количество приглашений можно отслеживать в разделе «Мой прогресс».",
        reply_markup=main_kb())
    await c.answer()

@dp.callback_query(F.data == "stats")
async def stats(c: CallbackQuery):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE invited_by=?", (c.from_user.id,))
    invited = cur.fetchone()[0]
    con.close()
    await c.message.edit_text(
        f"📊 <b>Мой прогресс</b>\n\n"
        f"👥 Приглашено друзей: <b>{invited}</b>\n\n"
        "Пока бот не считает реальные выплаты — только действия внутри сервиса.",
        reply_markup=main_kb())
    await c.answer()

@dp.message(Command("add"))
async def add_offer(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    # Format: /add | category | title | description | reward | time | url
    raw = message.text[len("/add"):].strip()
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) != 6:
        await message.answer("Формат:\n/add category | title | description | reward | time | url")
        return
    category, title, description, reward, time_, url = parts
    con = db()
    con.execute("INSERT INTO offers(category,title,description,reward,time,url) VALUES(?,?,?,?,?,?)",
                (category,title,description,reward,time_,url))
    con.commit()
    con.close()
    await message.answer("✅ Предложение добавлено.")

@dp.message(Command("offers"))
async def offers(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    con = db()
    rows = con.execute("SELECT id,category,title,active FROM offers ORDER BY id DESC").fetchall()
    con.close()
    if not rows:
        await message.answer("Предложений пока нет.")
        return
    await message.answer("\n".join(f"{i}. [{cat}] {title} — {'ON' if active else 'OFF'}" for i,cat,title,active in rows))

async def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
