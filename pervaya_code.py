import random, re, logging, mysql.connector, qrcode
from io import BytesIO
from telegram import Update
from telegram.ext import ( Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, CallbackContext)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta

TOKEN = "7764676868:AAHj8c7NCg78j6rRO4GSxb2teSmrjZo-XFI"

db_config = {
    "host": "localhost",
    "user": "root",
    "password": "ibragimkuanbek",
    "database": "water_dispenser"}

FULL_NAME, ADDRESS, PHONE, CODE, ADULTS, CHILDREN, TENANTS = range(7)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    return mysql.connector.connect(**db_config)

async def start(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\n"
        "Я бот для регистрации жильцов и начисления бонусов за воду.\n\n"
        "Впиши /help для получения списка команд!")

async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "📌 Список доступных команд:\n\n"
        "🚀 /start – Запуск бота:\n"
        "⚙️ /register – Регистрация жильца\n"
        "🔄🏃🏃🏃 /update_residents – Обновление информации о жильцах\n"
        "💰 /check_bonus – Проверить баланс бонусов\n"
        "💧 /use_bonus – Получить QR-код на воду\n"
        "🔎 /check_qrcode – Проверить срок QR-код\n"
        "🛠️ /support – Обращение тех-поддержку\n"
        "❓ /help – Список команд\n")


async def register(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    context.user_data["id"] = user_id

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id = %s", (user_id,))
    if cursor.fetchone():
        await update.message.reply_text("Вы уже зарегистрированы!")
        cursor.close()
        conn.close()
        return ConversationHandler.END

    cursor.close()
    conn.close()
    await update.message.reply_text("Введите ваше ФИО:")
    return FULL_NAME


async def get_full_name(update: Update, context: CallbackContext) -> int:
    context.user_data["full_name"] = update.message.text.strip()
    await update.message.reply_text("Введите ваш адрес:")
    return ADDRESS

async def get_address(update: Update, context: CallbackContext) -> int:
    context.user_data["address"] = update.message.text.strip()
    await update.message.reply_text("Введите ваш номер телефона:")
    return PHONE

async def get_phone(update: Update, context: CallbackContext) -> int:
    phone = update.message.text.strip()
    if not re.fullmatch(r"\d{11}", phone):
        await update.message.reply_text("Некорректный номер! Введите 11-значный номер телефона.")
        return PHONE
    context.user_data["phone"] = phone
    context.user_data["code"] = str(random.randint(1000, 9999))
    await update.message.reply_text(f"Введите код подтверждения (пример: {context.user_data['code']})")
    return CODE

async def get_code(update: Update, context: CallbackContext) -> int:
    if update.message.text.strip() != context.user_data["code"]:
        await update.message.reply_text("Неверный код! Попробуйте снова.")
        return CODE
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (telegram_id, full_name, address, phone_number) VALUES (%s, %s, %s, %s)",
        (context.user_data["id"], context.user_data["full_name"], context.user_data["address"],
         context.user_data["phone"]))
    conn.commit()
    cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (context.user_data["id"],))
    user_db_id = cursor.fetchone()[0]
    cursor.execute("INSERT INTO bonuses (user_id, bonus_count) VALUES (%s, 0)", (user_db_id,))
    conn.commit()
    cursor.close()
    conn.close()

    await update.message.reply_text("Регистрация завершена! Теперь укажите количество взрослых.")
    return ADULTS

async def update_residents(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (user_id,))
    result = cursor.fetchone()
    if not result:
        await update.message.reply_text("⚠️ Вы не зарегистрированы.\nПожалуйста, зарегистрируйтесь командой /register.")
        cursor.close()
        conn.close()
        return ConversationHandler.END
    context.user_data["id"] = user_id
    cursor.close()
    conn.close()
    await update.message.reply_text("Введите количество взрослых:")
    return ADULTS

async def get_adults(update: Update, context: CallbackContext) -> int:
    context.user_data["adults"] = int(update.message.text)
    await update.message.reply_text("Введите количество детей:")
    return CHILDREN

async def get_children(update: Update, context: CallbackContext) -> int:
    context.user_data["children"] = int(update.message.text)
    await update.message.reply_text("Введите количество арендаторов:")
    return TENANTS

async def get_tenants(update: Update, context: CallbackContext) -> int:
    context.user_data["tenants"] = int(update.message.text)
    user_id = context.user_data["id"]
    total_residents = context.user_data["adults"] + context.user_data["children"] + context.user_data["tenants"]
    bonus = total_residents * 4
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE users SET adults = %s, children = %s, tenants = %s WHERE telegram_id = %s""",
        (context.user_data["adults"], context.user_data["children"], context.user_data["tenants"], user_id))
    cursor.execute("DELETE FROM bonuses WHERE bonus_expiry < NOW() AND user_id = (SELECT id FROM users WHERE telegram_id = %s)", (user_id,))
    expiry_time = datetime.now() + timedelta(days=3)
    cursor.execute(
        "INSERT INTO bonuses (user_id, bonus_count, bonus_expiry) VALUES ((SELECT id FROM users WHERE telegram_id = %s), %s, %s)",
        (user_id, bonus, expiry_time))
    conn.commit()
    cursor.close()
    conn.close()
    await update.message.reply_text(f"✅ Информация обновлена!\n💰 Ваш новый бонус: {bonus} бутылок воды (срок 3 дня).")
    return ConversationHandler.END

#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!ПОД ВОПРОСОМ!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!ТЕПЕРЬ НЕТ)))))))))))))
update_residents_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("update_residents", update_residents)],
    states={
        ADULTS: [MessageHandler(filters.TEXT & filters.Regex("^\\d+$"), get_adults)],
        CHILDREN: [MessageHandler(filters.TEXT & filters.Regex("^\\d+$"), get_children)],
        TENANTS: [MessageHandler(filters.TEXT & filters.Regex("^\\d+$"), get_tenants)],
    },
    fallbacks=[],)

register_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("register", register)],
    states={
        FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_full_name)],
        ADDRESS: [MessageHandler(filters.TEXT, get_address)],
        PHONE: [MessageHandler(filters.TEXT, get_phone)],
        CODE: [MessageHandler(filters.TEXT, get_code)],
        ADULTS: [MessageHandler(filters.TEXT & filters.Regex("^\\d+$"), get_adults)],
        CHILDREN: [MessageHandler(filters.TEXT & filters.Regex("^\\d+$"), get_children)],
        TENANTS: [MessageHandler(filters.TEXT & filters.Regex("^\\d+$"), get_tenants)],
    },
    fallbacks=[],)

#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

async def check_qrcode(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        await update.message.reply_text("⚠️ Вы не зарегистрированы.\nПожалуйста, зарегистрируйтесь командой /register.")
        cursor.close()
        conn.close()
        return

    user_id_db = user[0]

    cursor.execute(
        "SELECT id, expiration_time, status FROM qr_codes WHERE user_id = %s AND status = 'active' ORDER BY expiration_time DESC LIMIT 1",
        (user_id_db,)
    )
    result = cursor.fetchone()

    if not result:
        await update.message.reply_text("У вас нет активных QR-кодов.")
        cursor.close()
        conn.close()
        return

    qr_id, expiration_time, status = result
    expiration_time = expiration_time.replace(tzinfo=None)
    remaining_time = expiration_time - datetime.now()

    if remaining_time.total_seconds() <= 0:
        cursor.execute("UPDATE qr_codes SET status = 'expired' WHERE id = %s", (qr_id,))
        conn.commit()
        await update.message.reply_text("⏳ Ваш QR-код истек и больше не действителен.")
    else:
        minutes_left = int(remaining_time.total_seconds() // 60)
        await update.message.reply_text(f"⏳ Ваш QR-код действителен еще {minutes_left} минут.")

    cursor.close()
    conn.close()

async def check_bonus(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        await update.message.reply_text("⚠️ Вы не зарегистрированы.\nПожалуйста, зарегистрируйтесь командой /register.")
        cursor.close()
        conn.close()
        return

    cursor.execute(
        "DELETE FROM bonuses WHERE bonus_expiry < NOW() AND user_id = %s", (user[0],))
    conn.commit()
    cursor.execute(
        "SELECT COALESCE(SUM(bonus_count), 0) FROM bonuses WHERE user_id = %s", (user[0],))
    bonus_balance = cursor.fetchone()[0]
    cursor.execute(
        "SELECT MIN(bonus_expiry) FROM bonuses WHERE user_id = %s", (user[0],))
    expiry_result = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    if expiry_result:
        remaining_time = expiry_result - datetime.now()
        days_left = remaining_time.days
        hours_left = remaining_time.seconds // 3600
        expiry_text = f"(срок {days_left} дн. {hours_left} ч.)"
    else:
        expiry_text = "(нет активных бонусов)"

    await update.message.reply_text(f"💰 Ваш баланс бонусов: {bonus_balance} бутылок воды {expiry_text}.")


async def use_bonus(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, telegram_id FROM users WHERE telegram_id = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        await update.message.reply_text("⚠️ Вы не зарегистрированы. Пожалуйста, зарегистрируйтесь командой /register.")
        cursor.close()
        conn.close()
        return ConversationHandler.END

    cursor.execute("DELETE FROM bonuses WHERE bonus_expiry < NOW() AND user_id = %s", (user[0],))
    conn.commit()
    cursor.execute(
        "SELECT status FROM qr_codes WHERE telegram_id = %s AND status = 'active' ORDER BY id DESC LIMIT 1",
        (user[1],)
    )
    result = cursor.fetchone()
    if result:
        await update.message.reply_text("⏳ У вас уже есть активный QR-код. Используйте его.")
        cursor.close()
        conn.close()
        return ConversationHandler.END

    await update.message.reply_text("Сколько бутылок воды вы хотите получить?")
    return "WAIT_FOR_BOTTLES"

async def wait_for_bottles(update: Update, context: CallbackContext) -> int:
    try:
        bottles = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите корректное количество бутылок.")
        return "WAIT_FOR_BOTTLES"
    user_id = update.message.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, telegram_id FROM users WHERE telegram_id = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        await update.message.reply_text("⚠️ Вы не зарегистрированы.\nПожалуйста, зарегистрируйтесь командой /register.")
        cursor.close()
        conn.close()
        return ConversationHandler.END

    cursor.execute("SELECT SUM(bonus_count) FROM bonuses WHERE user_id = %s", (user[0],))
    result = cursor.fetchone()
    bonus_count = result[0] if result and result[0] else 0

    if bonus_count < bottles:
        await update.message.reply_text(f"У вас недостаточно бонусов для получения {bottles} бутылок воды.")
        cursor.close()
        conn.close()
        return ConversationHandler.END
    cursor.execute(
        "UPDATE bonuses SET bonus_count = bonus_count - %s WHERE user_id = %s AND bonus_count >= %s",
        (bottles, user[0], bottles)
    )
    conn.commit()
    qr_data = f"user_id:{user[0]}, telegram_id:{user[1]}, bottles:{bottles}"
    qr = qrcode.make(qr_data)
    bio = BytesIO()
    qr.save(bio, format="PNG")
    bio.seek(0)
    cursor.execute(
        "INSERT INTO qr_codes (user_id, telegram_id, qr_code, bonus_count, status) VALUES (%s, %s, %s, %s, 'active')",
        (user[0], user[1], qr_data, bottles)
    )
    conn.commit()
    cursor.close()
    conn.close()

    await update.message.reply_photo(photo=bio, caption=f"🚰 Вот ваш QR-код на {bottles} бутылок воды!")
    return ConversationHandler.END

use_bonus_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("use_bonus", use_bonus)],
    states={
        "WAIT_FOR_BOTTLES": [MessageHandler(filters.TEXT & filters.Regex("^\\d+$"), wait_for_bottles)],
    },
    fallbacks=[],)

async def support(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("💰 Бонусы не начисляются", callback_data="support_bonus")],
        [InlineKeyboardButton("📲 Не работает QR-код", callback_data="support_qr")],
        [InlineKeyboardButton("🤖 Бот не запускается", callback_data="support_bot")],
        [InlineKeyboardButton("🏢 Не могу обновлять жильцов", callback_data="support_residents")],
        [InlineKeyboardButton("❓ Другое", callback_data="support_other")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📞 Выберите вашу проблему:", reply_markup=reply_markup)

async def handle_support_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    issue_map = {
        "support_bonus": "💰 Проблема с начислением бонусов",
        "support_qr": "📲 QR-код не работает",
        "support_bot": "🤖 Бот не запускается",
        "support_residents": "🏢 Проблема с обновлением жильцов",
        "support_other": "❓ Другая проблема"
    }
    issue_text = issue_map.get(query.data, "❓ Неизвестная проблема")
    support_email = "n.chernov@aues.kz"
    await query.message.reply_text(f"{issue_text}\n📩 Свяжитесь с техподдержкой: {support_email}")

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(register_conv_handler)
    application.add_handler(update_residents_conv_handler)
    application.add_handler(use_bonus_conv_handler)
    application.add_handler(CommandHandler("support", support))
    application.add_handler(CallbackQueryHandler(handle_support_callback, pattern="^support_"))
    application.add_handler(CommandHandler("update_residents", update_residents))
    application.add_handler(CommandHandler("check_bonus", check_bonus))
    application.add_handler(CommandHandler("use_bonus", use_bonus))
    application.add_handler(CommandHandler("check_qrcode", check_qrcode))
    application.run_polling()

if __name__ == "__main__":
    main()