import telebot
import sqlite3
import cv2
import mysql.connector
import numpy as np
from pyzbar.pyzbar import decode
from telebot.types import BotCommand
from telebot import types
import random
import string
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "ibragimkuanbek",
    "database": "water_dispenser"}

API_TOKEN = "7853851460:AAG6bqmN_wn21s1MjeqycUJPgdwFY8gtPU0"
bot = telebot.TeleBot(API_TOKEN)
name = ''
ADMIN_CHAT_ID = 7291413166
def get_db_connection():
    return mysql.connector.connect(**db_config)
def generate_access_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
users_data = {}
def is_registered(user_id):
    conn = sqlite3.connect('employee.sqlite3')
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    conn.close()
    return result is not None


def get_db_connection():
    return mysql.connector.connect(**db_config)


def update_qr_status(qr_code_text):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Проверяем, есть ли такой QR-код и активен ли он
        cursor.execute("SELECT * FROM qr_codes WHERE qr_code = %s AND status = 'active'", (qr_code_text,))
        qr_entry = cursor.fetchone()

        if qr_entry:
            user_id = qr_entry["user_id"]
            bonus_count = qr_entry["bonus_count"]

            # Обновляем статус QR-кода на "used"
            cursor.execute("UPDATE qr_codes SET status = 'used' WHERE qr_code = %s", (qr_code_text,))

            # Вычитаем бонусы из таблицы bonuses
            cursor.execute("UPDATE bonuses SET bonus_count = bonus_count - %s WHERE user_id = %s",
                           (bonus_count, user_id))

            conn.commit()
            return True, bonus_count  # QR-код успешно использован
        else:
            return False, 0  # QR-код не найден или уже использован

    except Exception as e:
        print(f"Ошибка базы данных: {e}")
        return False, 0
    finally:
        cursor.close()
        conn.close()


@bot.message_handler(commands=['scan_qr'])
def request_qr_code(message):
    bot.send_message(message.chat.id, "📸 Отправьте изображение с QR-кодом.")


@bot.message_handler(content_types=['photo'])
def scan_qr_code(message):
    try:
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        file_path = file_info.file_path
        downloaded_file = bot.download_file(file_path)
        np_arr = np.frombuffer(downloaded_file, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        qr_codes = decode(image)

        if not qr_codes:
            bot.send_message(message.chat.id, "❌ QR-код не найден! Попробуйте другое изображение.")
            return

        for qr in qr_codes:
            qr_text = qr.data.decode("utf-8")

            # Проверяем и обновляем статус QR-кода
            success, deducted_bonus = update_qr_status(qr_text)

            if success:
                bot.send_message(message.chat.id, f"✅ QR-код использован! Вычтено {deducted_bonus} бонусов.")
            else:
                bot.send_message(message.chat.id, "⚠️ QR-код уже использован или не найден в базе!")

    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Ошибка при обработке QR-кода: {e}")




@bot.message_handler(commands=['enter'])
def ask_password(message):
    chat_id = message.chat.id
    conn = sqlite3.connect('employee.sqlite3')
    cur = conn.cursor()
    cur.execute("SELECT pass FROM users WHERE user_id = ?", (chat_id,))
    user_data = cur.fetchone()
    cur.close()
    conn.close()
    if user_data:
        bot.send_message(chat_id, "🔑 Введите ваш пароль для входа:")
        bot.register_next_step_handler(message, check_password, user_data[0])
    else:
        bot.send_message(chat_id, "❌ Вы не зарегистрированы. Используйте /register для регистрации.")
def check_password(message, correct_password):
    chat_id = message.chat.id
    entered_password = message.text.strip()
    if entered_password == correct_password:
        conn = sqlite3.connect('employee.sqlite3')
        cur = conn.cursor()
        cur.execute("UPDATE users SET registration = 1 WHERE user_id = ?", (chat_id,))
        conn.commit()
        cur.close()
        conn.close()
        bot.send_message(chat_id, "✅ Успешный вход в систему! 🎉")
    else:
        bot.send_message(chat_id, "❌ Неверный пароль. Попробуйте снова, используя /enter.")
@bot.message_handler(commands=['admin'])
def admin_login(message):
    if message.chat.id != ADMIN_CHAT_ID:
        bot.send_message(message.chat.id, "❌ У вас нет прав доступа!")
        return
    conn = sqlite3.connect('employee.sqlite3')
    cur = conn.cursor()
    cur.execute('SELECT user_id, name, pass, phone, code_enter, registration, language FROM users')
    users = cur.fetchall()
    cur.close()
    conn.close()
    if not users:
        bot.send_message(message.chat.id, "📭 В базе данных нет пользователей!")
        return
    info = "📋 Список пользователей: \n\n"
    for user_id, name, password, phone, access_key, registration, language in users:
        status = "✅ Зарегистрирован" if registration == 1 else "❌ Не зарегистрирован"
        info += (f"👤 Имя: {name}\n"
                 f"🆔 ID: {user_id}\n"
                 f"🔑 Пароль: {password}\n"
                 f"📱 Телефон: {phone}\n"
                 f"🔐 Код доступа: {access_key}\n"
                 f"📌 Статус: {status}\n"
                 f"🌍 Язык: {language if language else 'Не указан'}\n"
                 "----------------------\n")
        try:
            bot.send_message(user_id, f"🔑 Ваш код доступа: {access_key}", parse_mode="Markdown")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Не удалось отправить сообщение {name}: {e}")
    bot.send_message(message.chat.id, info, parse_mode="Markdown")
@bot.message_handler(commands=['start'])
def start(message):
    conn = sqlite3.connect('employee.sqlite3')  # Было 'employee.sql'
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            pass TEXT,
            code_enter TEXT,
            phone TEXT,
            registration INTEGER,
            language TEXT,
            user_id INTEGER UNIQUE
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()
    bot.send_message(message.chat.id, 'Привет! 👋 Я - чат бот, созданный для сотрудников 😁\n'
                                      'Если ты хочешь получить помощь по командам, напиши мне <b>/help</b> 🤓\n'
                                      'Если ты захочешь поменять язык, то напиши <b>/language</b>', parse_mode='html')
    bot.send_message(message.chat.id,
                     'Я занёс тебя в базу, теперь ты можешь воспользоваться командой <b>/register</b>😜\n',
                     parse_mode='html')
@bot.message_handler(commands=['register'])
def ask_name(message):
    chat_id = message.chat.id
    conn = sqlite3.connect('employee.sqlite3')
    cur = conn.cursor()
    cur.execute("SELECT registration FROM users WHERE user_id = ?", (chat_id,))
    register = cur.fetchone()
    cur.close()
    conn.close()
    if register and register[0] == 1:
        bot.send_message(chat_id, "✅ Вы уже зарегистрированы в системе!")
    else:
        users_data[chat_id] = {}
        bot.send_message(chat_id, "📝 Пожалуйста, введите ваше имя:")
        bot.register_next_step_handler(message, ask_password1)
def ask_password1(message):
    chat_id = message.chat.id
    users_data[chat_id]['name'] = message.text
    bot.send_message(chat_id, "🔑 Введите пароль:")
    bot.register_next_step_handler(message, ask_password_confirmation)
def ask_password_confirmation(message):
    chat_id = message.chat.id
    users_data[chat_id]['password'] = message.text
    bot.send_message(chat_id, "🔁 Повторите пароль:")
    bot.register_next_step_handler(message, check_password_match)
def check_password_match(message):
    chat_id = message.chat.id
    if message.text != users_data[chat_id]['password']:
        bot.send_message(chat_id, "❌ Пароли не совпадают! Попробуйте снова.")
        bot.send_message(chat_id, "🔑 Введите пароль:")
        bot.register_next_step_handler(message, ask_password_confirmation)
    else:
        bot.send_message(chat_id, "✅ Пароль подтвержден!\n📱 Введите ваш номер телефона:")
        bot.register_next_step_handler(message, register_user)
def register_user(message):
    chat_id = message.chat.id
    users_data[chat_id]['phone'] = message.text
    access_key = generate_access_key()
    conn = sqlite3.connect('employee.sqlite3')
    cur = conn.cursor()
    cur.execute("INSERT INTO users (user_id, name, pass, phone, code_enter, registration) VALUES (?, ?, ?, ?, ?, ?)",
                (chat_id, users_data[chat_id]['name'], users_data[chat_id]['password'], users_data[chat_id]['phone'], access_key, 1))
    conn.commit()
    cur.close()
    conn.close()
    bot.send_message(chat_id, f"✅ Регистрация завершена!\n🔑 Ваш код доступа: {access_key}", parse_mode="Markdown")
@bot.message_handler(commands=['logout'])
def logout(message):
    chat_id = message.chat.id
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("Да", "Нет")
    bot.send_message(chat_id, "Вы действительно хотите выйти из аккаунта? Да/Нет", reply_markup=markup)
    bot.register_next_step_handler(message, process_logout)
def process_logout(message):
    chat_id = message.chat.id
    if message.text == "Да":
        conn = sqlite3.connect('employee.sqlite3')
        cur = conn.cursor()
        cur.execute("UPDATE users SET registration = 0 WHERE user_id = ?", (chat_id,))
        conn.commit()
        cur.close()
        conn.close()
        bot.send_message(chat_id, "✅ Вы успешно вышли из аккаунта!")
    else:
        bot.send_message(chat_id, "👌 Вы остались в системе!")
@bot.message_handler(commands = ['info'])
def info(message):
    conn = sqlite3.connect('employee.sqlite3')  # Было 'employee.sql'
    cur = conn.cursor()
    cur.execute('SELECT registration FROM users where user_id = ?', (message.from_user.id,))
    register = cur.fetchone()
    cur.close()
    conn.close()
    if register and register[0] == 1:
        conn = sqlite3.connect('employee.sqlite3')
        cur = conn.cursor()
        cur.execute('SELECT name, pass FROM users')
        users = cur.fetchall()
        cur.close()
        conn.close()
        info = ''
        for el in users:
            info += f'Имя: {el[0]}'
        bot.send_message(message.chat.id, info)
    else:
        bot.send_message(message.chat.id, "Вы не зарегестрированы в системе!")
@bot.message_handler(commands=['delete_account'])
def delete_account(message):
    chat_id = message.chat.id

    conn = sqlite3.connect('employee.sqlite3')
    cur = conn.cursor()
    cur.execute('SELECT registration FROM users WHERE user_id = ?', (chat_id,))
    register = cur.fetchone()
    cur.close()
    conn.close()
    if register and register[0] == 1:
        bot.send_message(chat_id, "⚠️ Вы действительно хотите удалить аккаунт? Введите ваш пароль для подтверждения.")
        bot.register_next_step_handler(message, confirm_delete)
    else:
        bot.send_message(chat_id, "❌ Вы не зарегистрированы и не можете удалить аккаунт!")
def confirm_delete(message):
    chat_id = message.chat.id
    entered_password = message.text.strip()
    conn = sqlite3.connect('employee.sqlite3')
    cur = conn.cursor()
    cur.execute('SELECT pass FROM users WHERE user_id = ?', (chat_id,))
    user_data = cur.fetchone()

    if user_data and user_data[0] == entered_password:
        cur.execute('DELETE FROM users WHERE user_id = ?', (chat_id,))
        conn.commit()
        bot.send_message(chat_id, "✅ Ваш аккаунт был успешно удален!")
    else:
        bot.send_message(chat_id, "❌ Неверный пароль! Удаление отменено.")

    cur.close()
    conn.close()
@bot.message_handler(commands = ['help'])
def help(message):
        bot.send_message(message.chat.id, 'Вот список команд с которыми ты можешь работать: \n'
                                          '<em>"/start - для новых пользователей"\n"/register - регистрация"\n'
                                          '"/language - смена языка"</em>\n<b>'
                                          'О боте:</b> бот предоставляет каждому'
                                          'зарегестрированному сотруднику возможность сканировать код для анализа'
                                          'и просмотра обслуженных клиентов.', parse_mode='html')

@bot.message_handler()
def main(message):
    bot.send_message(message.chat.id,'Привет! 👋 Я - чат бот, созданный для сотрудников 😁\n'
                      'Если ты хочешь получить помощь по командам, напиши мне <b>/help</b> 🤓\n'
                      'Если ты захочешь поменять язык, то напиши <b>/language</b>', parse_mode='html')

bot.set_my_commands([
    BotCommand("start", "Занесение в базу пользователей"),
    BotCommand("info", "Список пользователей"),
    BotCommand("help", "Справка по командам"),
    BotCommand("register", "Регистрация пользователя"),
    BotCommand("language", "Смена языка")

])

bot.polling(none_stop=True)