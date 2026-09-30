
import logging
import os
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "cashbox-secret")
WEBHOOK_PATH = "/telegram/webhook"
DB_PATH = "cash_box.db"
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
bot = Bot(BOT_TOKEN)
dp = Dispatcher()
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        name TEXT
    );
    CREATE TABLE IF NOT EXISTS offers (
        bank TEXT PRIMARY KEY,
        name TEXT,
        url TEXT,
        payout TEXT
    );
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        bank TEXT,
        status TEXT DEFAULT 'waiting',
        UNIQUE(user_id, bank)
    );
    """)
    conn.execute(
        "INSERT OR IGNORE INTO offers VALUES (?, ?, ?, ?)",
        ("alfa", "🏦 Альфа-Банк", "", "до 300 ₽")
    )
    conn.execute(
        "INSERT OR IGNORE INTO offers VALUES (?, ?, ?, ?)",
        ("tbank", "💳 Т-Банк", "", "до 150 ₽")
    )
    conn.commit()
    conn.close()
def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏦 Альфа-Банк",
                    callback_data="offer:alfa"
                ),
                InlineKeyboardButton(
                    text="💳 Т-Банк",
                    callback_data="offer:tbank"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❓ Как это работает",
                    callback_data="how"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💸 Мои выплаты",
                    callback_data="payouts"
                ),
                InlineKeyboardButton(
                    text="📜 Правила",
                    callback_data="rules"
                )
            ]
        ]
    )
def back_button():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="back"
                )
            ]
        ]
    )
def save_user(message: Message):
    conn = db()
    conn.execute(
        """
        INSERT INTO users (id, username, name)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
        username = excluded.username,
        name = excluded.name
        """,
        (
            message.from_user.id,
            message.from_user.username or "",
            message.from_user.first_name or ""
        )
    )
    conn.commit()
    conn.close()
@dp.message(CommandStart())
async def start(message: Message):
    save_user(message)
    await message.answer(
        "💰 <b>CASH BOX</b>\n\n"
        "Здесь ты можешь получить часть моего "
        "реферального бонуса за оформление "
        "банковского продукта.\n\n"
        "Выбирай предложение 👇",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )
@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.answer()
    await call.message.edit_text(
        "💰 <b>CASH BOX</b>\n\n"
        "Выбирай предложение 👇",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )
@dp.callback_query(F.data.startswith("offer:"))
async def offer(call: CallbackQuery):
    await call.answer()
    bank = call.data.split(":")[1]
    conn = db()
    offer_data = conn.execute(
        "SELECT * FROM offers WHERE bank = ?",
        (bank,)
    ).fetchone()
    conn.close()
    if not offer_data:
        return
    text = (
        f"{offer_data['name']}\n\n"
        f"💰 <b>Твой бонус: {offer_data['payout']}</b>\n\n"
        "Как это работает:\n\n"
        "1️⃣ Нажми «Получить бонус»\n"
        "2️⃣ Оформи продукт именно по этой ссылке\n"
        "3️⃣ Выполни условия акции\n"
        "4️⃣ Нажми «Я выполнил условия»\n"
        "5️⃣ После подтверждения моего бонуса "
        "я выплачу тебе твою часть.\n\n"
        "⚠️ Размер и условия акции могут изменяться банком."
    )
    buttons = []
    if offer_data["url"]:
        buttons.append([
            InlineKeyboardButton(
                text="💸 ПОЛУЧИТЬ БОНУС",
                url=offer_data["url"]
            )
        ])
    buttons.append([
        InlineKeyboardButton(
            text="✅ Я выполнил условия",
            callback_data=f"done:{bank}"
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back"
        )
    ])
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
        parse_mode="HTML"
    )
@dp.callback_query(F.data.startswith("done:"))
async def done(call: CallbackQuery):
    bank = call.data.split(":")[1]
    conn = db()
    conn.execute(
        """
        INSERT INTO applications (user_id, bank, status)
        VALUES (?, ?, 'waiting')
        ON CONFLICT(user_id, bank)
        DO UPDATE SET status = 'waiting'
        """,
        (call.from_user.id, bank)
    )
    conn.commit()
    conn.close()
    await call.answer("Заявка отправлена на проверку.")
    await call.message.edit_text(
        "⏳ <b>Заявка отправлена.</b>\n\n"
        "Статус: <b>на проверке</b>.\n\n"
        "После проверки условий и подтверждения "
        "банковского бонуса будет принято решение о выплате.",
        reply_markup=back_button(),
        parse_mode="HTML"
    )
@dp.callback_query(F.data == "how")
async def how(call: CallbackQuery):
    await call.answer()
    await call.message.edit_text(
        "❓ <b>КАК ЭТО РАБОТАЕТ</b>\n\n"
        "1️⃣ Выбираешь банк.\n"
        "2️⃣ Переходишь по моей реферальной ссылке.\n"
        "3️⃣ Оформляешь подходящий продукт.\n"
        "4️⃣ Выполняешь условия банка.\n"
        "5️⃣ Нажимаешь «Я выполнил условия».\n"
        "6️⃣ После подтверждения моего бонуса "
        "я выплачиваю тебе твою часть.\n\n"
        "ℹ️ Ссылка является реферальной. "
        "Автор Cash Box может получить вознаграждение "
        "от банка. Часть этого вознаграждения может "
        "быть передана пользователю.",
        reply_markup=back_button(),
        parse_mode="HTML"
    )
@dp.callback_query(F.data == "rules")
async def rules(call: CallbackQuery):
    await call.answer()
    await call.message.edit_text(
        "📜 <b>ПРАВИЛА</b>\n\n"
        "• Условия и размер банковского бонуса "
        "устанавливает банк.\n"
        "• Выплата производится после проверки "
        "и подтверждения условий.\n"
        "• Нельзя использовать чужие данные "
        "или обходить требования банка.\n"
        "• Cash Box не гарантирует одобрение "
        "банковского продукта.\n"
        "• Перед оформлением проверь актуальные "
        "условия акции.",
        reply_markup=back_button(),
        parse_mode="HTML"
    )
@dp.callback_query(F.data == "payouts")
async def payouts(call: CallbackQuery):
    await call.answer()
    conn = db()
    rows = conn.execute(
        """
        SELECT bank, status
        FROM applications
        WHERE user_id = ?
        """,
        (call.from_user.id,)
    ).fetchall()
    conn.close()
    names = {
        "alfa": "🏦 Альфа-Банк",
        "tbank": "💳 Т-Банк"
    }
    statuses = {
        "waiting": "⏳ на проверке",
        "confirmed": "✅ подтверждено",
        "paid": "💰 выплачено"
    }
    text = "💸 <b>МОИ ВЫПЛАТЫ</b>\n\n"
    if not rows:
        text += "У тебя пока нет заявок."
    else:
        for row in rows:
            text += (
                f"{names.get(row['bank'], row['bank'])}: "
                f"{statuses.get(row['status'], row['status'])}\n"
            )
    await call.message.edit_text(
        text,
        reply_markup=back_button(),
        parse_mode="HTML"
    )
@dp.message(Command("admin"))
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "👑 <b>АДМИН-ПАНЕЛЬ</b>\n\n"
        "/stats — статистика\n"
        "/pending — заявки\n"
        "/confirm ID — подтвердить заявку\n"
        "/paid ID — отметить выплату\n\n"
        "/setalfa ССЫЛКА | СУММА\n"
        "/settbank ССЫЛКА | СУММА",
        parse_mode="HTML"
    )
@dp.message(Command("stats"))
async def stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = db()
    users = conn.execute(
        "SELECT COUNT(*) AS n FROM users"
    ).fetchone()["n"]
    applications = conn.execute(
        "SELECT COUNT(*) AS n FROM applications"
    ).fetchone()["n"]
    waiting = conn.execute(
        "SELECT COUNT(*) AS n FROM applications "
        "WHERE status = 'waiting'"
    ).fetchone()["n"]
    paid = conn.execute(
        "SELECT COUNT(*) AS n FROM applications "
        "WHERE status = 'paid'"
    ).fetchone()["n"]
    conn.close()
    await message.answer(
        f"👑 Пользователей: {users}\n"
        f"Заявок: {applications}\n"
        f"На проверке: {waiting}\n"
        f"Выплачено: {paid}"
    )
@dp.message(Command("pending"))
async def pending(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = db()
    rows = conn.execute(
        """
        SELECT id, user_id, bank
        FROM applications
        WHERE status = 'waiting'
        ORDER BY id DESC
        """
    ).fetchall()
    conn.close()
    if not rows:
        await message.answer("Заявок на проверке нет.")
        return
    text = "📋 <b>ЗАЯВКИ</b>\n\n"
    for row in rows:
        text += (
            f"#{row['id']} | {row['bank']} | "
            f"user {row['user_id']}\n"
        )
    await message.answer(
        text,
        parse_mode="HTML"
    )
async def change_status(
    message: Message,
    status: str
):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer(
            "Например: /confirm 12"
        )
        return
    application_id = int(parts[1])
    conn = db()
    cursor = conn.execute(
        """
        UPDATE applications
        SET status = ?
        WHERE id = ?
        """,
        (status, application_id)
    )
    conn.commit()
    conn.close()
    if cursor.rowcount:
        await message.answer("✅ Готово.")
    else:
        await message.answer("❌ Заявка не найдена.")
@dp.message(Command("confirm"))
async def confirm(message: Message
