from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram import Bot, Dispatcher, types
from datetime import datetime, timedelta
from typing import Tuple, Optional
import sqlite3
import logging
import asyncio
import random
import time
import pytz
import re

print(" \n                            гусь гей")
API_TOKEN = "7543698934:AAHr7d5JQyX-BPJkkXu_h02Ba3o4HKV6uLI"
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Подключение к базе данных
conn = sqlite3.connect('KOTBioWars.db')
cursor = conn.cursor()

# Создание таблиц
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    bio_experience INTEGER DEFAULT 1,
    bio_resources INTEGER DEFAULT 50,
    registration_date TEXT,
    last_infect_time TEXT,
    skill_level INTEGER DEFAULT 1,
    contagion INTEGER DEFAULT 1,
    immunity INTEGER DEFAULT 0,
    virus_skill INTEGER DEFAULT 1,
    lethality INTEGER DEFAULT 1,
    qualification INTEGER DEFAULT 1,
    pathogens INTEGER DEFAULT 4,
    max_pathogens INTEGER DEFAULT 4,
    pathogen_name TEXT DEFAULT "котячка",
    lab_name TEXT DEFAULT NULL,
    fever_end_time TEXT DEFAULT NULL,
    fever_end_date TEXT DEFAULT NULL,
    is_banned INTEGER DEFAULT 0,
    banned_at TEXT DEFAULT NULL,
    unbanned_at TEXT DEFAULT NULL,
    banned_by INTEGER DEFAULT NULL,
    ban_reason TEXT DEFAULT NULL,
    ban_end_time TEXT DEFAULT NULL,
    next_pathogen_time TEXT
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS infections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attacker_id INTEGER,
    victim_id INTEGER,
    infection_time TEXT,
    lethality INTEGER,
    FOREIGN KEY(attacker_id) REFERENCES users(user_id),
    FOREIGN KEY(victim_id) REFERENCES users(user_id)
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS fallen_victims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    victim_id INTEGER,
    fall_date TEXT,
    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(victim_id) REFERENCES users(user_id)
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS infected (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    victim_id INTEGER,
    infect_date TEXT,
    infect_end_date TEXT,
    victim_experience INTEGER,
    experience_gained INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(victim_id) REFERENCES users(user_id))''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS pathogen_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    reason TEXT,
    punishment_duration INTEGER,
    unpunished_at TEXT,
    timestamp TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    admin_level INTEGER,
    added_by INTEGER,
    added_at TEXT
)''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS labs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    lab_name TEXT,
    reason TEXT,
    punishment_duration INTEGER,
    unpunished_at TEXT,
    timestamp TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)
''')
conn.commit()

# Настроим логирование
logging.basicConfig(level=logging.INFO)

##################################
#код для добавления чего либо в таблицу #

#def add_column_if_not_exists(table_name, column_name, column_type):
#    cursor.execute(f"PRAGMA table_info({table_name})")
#    columns = [column[1] for column in cursor.fetchall()]
    
#    if column_name not in columns:
#        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

# пример добавления
#add_column_if_not_exists('users', 'banned_at', 'TEXT DEFAULT NULL')
#add_column_if_not_exists('users', 'unbanned_at', 'TEXT DEFAULT NULL')
#add_column_if_not_exists('users', 'banned_by', 'INTEGER DEFAULT NULL')
#add_column_if_not_exists('users', 'ban_reason', 'TEXT DEFAULT NULL')

#conn.commit()

##################################
last_premium_hour = -1

async def calculate_premium(user_id, cursor):
    """Рассчитывает премию для пользователя"""
    cursor.execute('''
        SELECT SUM(victim_experience) 
        FROM infected 
        WHERE user_id = ? AND 
        datetime(infect_end_date) > datetime('now')
    ''', (user_id,))
    total_exp = cursor.fetchone()[0]
    return total_exp if total_exp else 0

async def daily_premium(cursor, conn):
    """Выполняет выдачу ежедневной премии"""
    now = datetime.now()
    current_time = now.strftime('%Y-%m-%d %H:%M:%S')

    # Выбираем активных пользователей
    cursor.execute('''
        SELECT DISTINCT user_id 
        FROM infected 
        WHERE datetime(infect_end_date) > datetime('now')
    ''')
    active_users = cursor.fetchall()

    for (user_id,) in active_users:
        premium_exp = await calculate_premium(user_id, cursor)

        if premium_exp > 0:
            bio_resources = int(premium_exp * 0.1)

            cursor.execute('''
                UPDATE users 
                SET bio_resources = bio_resources + ?
                WHERE user_id = ?
            ''', (bio_resources, user_id))

    # Обрабатываем истекшие заражения
    cursor.execute('''
        SELECT user_id, victim_id, victim_experience, infect_end_date 
        FROM infected 
        WHERE datetime(infect_end_date) <= datetime('now')
    ''')
    expired_infections = cursor.fetchall()

    for user_id, victim_id, victim_exp, end_date in expired_infections:
        cursor.execute('''
            INSERT INTO fallen_victims (user_id, victim_id, fall_date) 
            VALUES (?, ?, ?)
        ''', (user_id, victim_id, current_time))
        
        cursor.execute('''
            DELETE FROM infected 
            WHERE user_id = ? AND victim_id = ?
        ''', (user_id, victim_id))
        
    conn.commit()

async def schedule_premium(cursor, conn):
    """Планировщик выдачи премий, проверяет каждую минуту"""
    global last_premium_hour
    while True:
        now = datetime.utcnow() + timedelta(hours=3)  # Коррекция на МСК (UTC+3)
        
        # Проверяем, что сейчас 00:00 или 12:00 и премия еще не выдана
        if now.hour in [0, 12] and now.minute == 0 and last_premium_hour != now.hour:
            logging.info(f"Starting premium distribution at {now}")
            try:
                await daily_premium(cursor, conn)
                logging.info(f"Premium distribution completed at {now}")
                last_premium_hour = now.hour  # Обновляем время последней выдачи премии
            except Exception as e:
                logging.error(f"Error during premium distribution: {e}")
        
        # Ожидание до следующей минуты
        await asyncio.sleep(60)

@dp.message_handler(lambda message: message.text.lower() == "когда ежа?")
async def check_next_premium(message: types.Message):
    # Проверка на регистрацию и бан
    cursor.execute('SELECT user_id, is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()

    if not user_data:
        await message.reply("❌ Вы не зарегистрированы в боте. Используйте /start для регистрации.", parse_mode="HTML")
        return

    # Если пользователь забанен - молча выходим
    if user_data[1] == 1:
        return

    now = datetime.now()
    next_premium_hour = 12 if now.hour < 12 else 0
    next_premium_date = now.replace(hour=next_premium_hour, minute=0, second=0, microsecond=0)
    
    if now.hour >= 12:
        next_premium_date += timedelta(days=1)
    
    time_left = next_premium_date - now
    hours, remainder = divmod(time_left.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    await message.answer(
        f"⏰ До следующей ежи осталось:\n"
        f"🕐 {int(hours)} часов, {int(minutes)} минут\n"
        f"📅 Следующая премия в: {next_premium_date.strftime('%Y-%m-%d %H:%M')}"
    )

@dp.message_handler(lambda message: message.text.lower() == "мои жертвы")
async def show_my_infected(message: types.Message):
    # Проверка на регистрацию и бан
    cursor.execute('SELECT user_id, is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()

    if not user_data:
        await message.reply("🎅❌ Вы не зарегистрированы в боте. Используйте /start для регистрации.", parse_mode="HTML")
        return

    if user_data[1] == 1:  # Если забанен - молча выходим
        return

    user_id = message.from_user.id
    
    cursor.execute('''
        WITH RankedInfections AS (
            SELECT 
                i.victim_id,
                COALESCE(u.lab_name, u.username, CAST(i.victim_id AS TEXT)) as victim_name,
                i.experience_gained,
                i.infect_date,
                ROW_NUMBER() OVER (PARTITION BY i.victim_id ORDER BY i.infect_date DESC) as rn
            FROM infected i
            LEFT JOIN users u ON i.victim_id = u.user_id
            WHERE i.user_id = ?
        )
        SELECT victim_id, victim_name, experience_gained
        FROM RankedInfections
        WHERE rn = 1
        ORDER BY infect_date DESC
        LIMIT 30
    ''', (user_id,))
    
    infections = cursor.fetchall()
    
    if not infections:
        await message.answer("🎄❌ У вас нет заражений!")
        return

    response = "🎅☣️ <b>Ваши жертвы:</b>\n\n"
    total_exp = 0
    
    for idx, (victim_id, victim_name, exp_gained) in enumerate(infections, 1):
        response += f"{idx}. 🎁 <a href='tg://openmessage?user_id={victim_id}'>{victim_name}</a> | {exp_gained:,} подарков\n"
        total_exp += exp_gained
    
    response += f"\n🎉💉 Суммарный опыт: {total_exp:,}"
    
    await message.answer(response, parse_mode="HTML")

@dp.message_handler(lambda message: message.text.lower() == "/giveprem")
async def manual_premium(message: types.Message):
    # Для админской команды проверяем только регистрацию
    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()

    if not user_data:
        await message.reply("🎅❌ Вы не зарегистрированы в боте. Используйте /start для регистрации.", parse_mode="HTML")
        return

    if message.from_user.id not in [6832369115, 1291390143]:
        return
    try:
        await daily_premium()
        await message.answer("🎅🎄 Премия успешно выдана под ёлочку! 🎁✅")
    except Exception as e:
        logging.error(f"Error during manual premium distribution: {e}")
        await message.answer("🎅❌ Произошла ошибка при выдаче премии.")

@dp.message_handler(lambda message: message.text.lower() == "мои слетевшие")
async def show_fallen_victims(message: types.Message):
    # Проверка на регистрацию и бан
    cursor.execute('SELECT user_id, is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()

    if not user_data:
        await message.reply(
            "🎄❌ Ой-ой, похоже, вы еще не зарегистрированы! Начните с /start и откройте первые подарки!",
            parse_mode="HTML")
        return

    if user_data[1] == 1:  # Если забанен - молча выходим
        return

    user_id = message.from_user.id
    
    cursor.execute('''
        WITH RankedFallen AS (
            SELECT 
                f.victim_id,
                COALESCE(u.lab_name, u.username, CAST(f.victim_id AS TEXT)) as victim_name,
                f.experience_gained,
                f.fall_date,
                ROW_NUMBER() OVER (PARTITION BY f.victim_id ORDER BY f.fall_date DESC) as rn
            FROM fallen_victims f
            LEFT JOIN users u ON f.victim_id = u.user_id
            WHERE f.user_id = ?
        )
        SELECT victim_id, victim_name, experience_gained, fall_date
        FROM RankedFallen
        WHERE rn = 1
        ORDER BY fall_date DESC
        LIMIT 30
    ''', (user_id,))
    
    fallen = cursor.fetchall()
    
    if not fallen:
        await message.answer(
            "🎁❌ У вас пока нет слетевших жертв",
            parse_mode="HTML")
        return

    response = "<b>🎄 Ваши слетевшие жертвы:</b>\n\n"
    total_gifts = 0
    
    for idx, (victim_id, victim_name, exp_gained, fall_date) in enumerate(fallen, 1):
        fall_datetime = datetime.strptime(fall_date, '%Y-%m-%d %H:%M:%S')
        response += f"{idx}. <a href='tg://openmessage?user_id={victim_id}'>{victim_name}</a> — {exp_gained:,} подарков\n"
        total_gifts += exp_gained
    
    response += f"\n🎉 <b>Всего слетевших жертв: </b> {total_gifts:,}\n🌟 Пусть этот Новый Год принесет вам ещё больше жертв и радости!"
    
    await message.answer(response, parse_mode="HTML")

# Регистрация пользователя
async def register_user(user_id, username, first_name):
    # Проверяем, не забанен ли пользователь
    cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()

    if user is not None and user[0] == 1:  # Если пользователь существует и забанен
        return  # Молча выходим

    # Проверяем существует ли пользователь
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()

    if user is None:
        registration_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO users (
                user_id, 
                username, 
                registration_date, 
                is_banned,
                ban_reason,
                banned_at,
                ban_end_time,
                banned_by
            ) VALUES (?, ?, ?, 0, NULL, NULL, NULL, NULL)
        ''', (user_id, username, registration_date))
        conn.commit()
        await bot.send_message(
            user_id, 
            f"🎁❄️ {first_name}, Рад видеть тебя в KOTBioWars! 🌟\n🐾 Используй <code>!помощь</code> для помощи по командам. Будь здоров и удачи!", 
            parse_mode="HTML"
        )

# Команда /start
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Проверяем, не забанен ли пользователь
    cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()

    if user is not None and user[0] == 1:  # Если пользователь существует и забанен
        return  # Молча выходим
    
    await register_user(user_id, username, first_name)
    
    await message.answer(
        "🎅 ссылки на проект:\n\n"
        "<blockquote>🧣 • KOTBioWarsBot.t.me - ссылка на бота.\n"
        "🎄 • channelkotbiowars.t.me - ссылка на канал.\n"
        "❄️ • KOTBioWarsChat.t.me - ссылка на чат.</blockquote>", 
        parse_mode="HTML"
    )

# Функция для извлечения информации о пользователе из разных форматов
def extract_user_from_command(message: types.Message) -> Tuple[Optional[int], Optional[str]]:
    # Разбиваем сообщение на аргументы
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    # Проверка на реплай
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        if cursor.fetchone():
            return user_id, None
        return None, "❌ Пользователь из реплая не найден в базе данных."
    
    # Если аргументов нет, возвращаем None для случайного выбора
    if not args:
        return None, None
        
    arg = args[0]
    
    # Проверка, если аргумент - ссылка на пользователя
    link_pattern = r'https?://t.me/([a-zA-Z0-9_]+)'
    link_match = re.match(link_pattern, arg)
    if link_match:
        username = link_match.group(1)
        cursor.execute('SELECT user_id FROM users WHERE LOWER(username) = LOWER(?)', (username,))
        result = cursor.fetchone()
        if result:
            return result[0], None
        return None, f"❌ Пользователь {username} из ссылки не найден в базе данных."

    # Проверка, если аргумент - ссылка tg://openmessage?user_id=123456789
    tg_link_pattern = r'tg://openmessage\?user_id=(\d+)'
    tg_link_match = re.match(tg_link_pattern, arg)
    if tg_link_match:
        user_id = int(tg_link_match.group(1))
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        if result:
            return user_id, None
        return None, "❌ Пользователь из ссылки не найден в базе данных."
    
    # Проверка на аргумент с @ (например, @username)
    if arg.startswith('@'):
        username = arg[1:]  # Убираем @
        cursor.execute('SELECT user_id FROM users WHERE LOWER(username) = LOWER(?)', (username,))
        result = cursor.fetchone()
        if result:
            return result[0], None
        return None, f"❌ Пользователь @{username} не найден в базе данных."

    # Проверка на обычный username (без @)
    username = arg
    cursor.execute('SELECT user_id FROM users WHERE LOWER(username) = LOWER(?)', (username,))
    result = cursor.fetchone()
    if result:
        return result[0], None
    return None, f"❌ Пользователь {username} не найден в базе данных."

    return None, "❌ Неверный формат аргумента. Используйте @username, username, ссылку на пользователя или ссылку tg://openmessage?user_id."

@dp.message_handler(lambda message: message.text.lower().startswith("кусь"))
async def infect_user(message: types.Message):
    try:
        # Проверяем, зарегистрирован ли пользователь
        cursor.execute('SELECT user_id, is_banned, username, pathogens, pathogen_name, qualification FROM users WHERE user_id = ?', (message.from_user.id,))
        user_data = cursor.fetchone()

        if not user_data:
            await message.reply("❌ Вы не зарегистрированы в боте. Используйте /start для регистрации.")
            return

        if user_data[1] == 1:  # Если пользователь заблокирован
            await message.reply("❌ Вы заблокированы.")
            return

        pathogens = user_data[3]
        qualification = user_data[5]

        if pathogens <= 0:  # Если патогены на нуле
            recovery_time = max(30 - qualification * 2, 5)
            next_recovery = datetime.now() + timedelta(minutes=recovery_time)
            
            await message.reply(
                f"🎄 Критический уровень патогенов!\n"
                f"├ ⏳ Восстановление: {recovery_time} мин.\n"
                f"└ 🎅 Эльфы санты уже ускоряют процесс.",
                parse_mode="HTML"
            )
            return

        user_id = message.from_user.id
        pathogen_name = user_data[4] if user_data[4] else "котячка"

        # Извлекаем жертву
        victim_id, error_message = extract_user_from_command(message)
        if error_message:
            await message.reply(error_message)
            return

        if not victim_id:  # Если жертва не указана, выбираем случайного пользователя
            cursor.execute("SELECT user_id FROM users WHERE user_id != ? AND is_banned = 0", (user_id,))
            victims = cursor.fetchall()
            if not victims:
                await message.reply("❌ В базе нет других пользователей для заражения.")
                return
            victim_id = random.choice(victims)[0]

        # Проверяем, что пользователь не пытается заразить сам себя
        if victim_id == user_id:
            await message.reply("❌ Вы не можете заразить себя.")
            return

        # Проверяем время последнего заражения
        cursor.execute("""
            SELECT infect_date FROM infected 
            WHERE user_id = ? AND victim_id = ? 
            ORDER BY infect_date DESC LIMIT 1
        """, (user_id, victim_id))
        last_infection = cursor.fetchone()

        cooldown_time = timedelta(hours=4)

        if last_infection:
            last_infection_time = datetime.strptime(last_infection[0], '%Y-%m-%d %H:%M:%S')
            time_since_infection = datetime.now() - last_infection_time
            if time_since_infection < cooldown_time:
                remaining_time = cooldown_time - time_since_infection
                hours = int(remaining_time.total_seconds() // 3600)
                minutes = int((remaining_time.total_seconds() % 3600) // 60)
                
                # Получаем информацию о жертве
                cursor.execute('SELECT lab_name FROM users WHERE user_id = ?', (victim_id,))
                victim_data = cursor.fetchone()
                
                if victim_data and victim_data[0]:  # Если у жертвы есть имя лаборатории
                    lab_name = victim_data[0]
                    await message.reply(
                        f'🎄 ⏳ До следующей атаки <a href="tg://openmessage?user_id={victim_id}">{lab_name}</a> осталось: <b>{hours} ч. {minutes} мин.</b>',
                        parse_mode="HTML"
                    )
                else:  # Если имени лаборатории нет, показываем юзернейм
                    await message.reply(
                        f'🎄 ⏳ До следующей атаки <a href="tg://openmessage?user_id={victim_id}">{victim_id}</a> осталось: <b>{hours} ч. {minutes} мин.</b>',
                        parse_mode="HTML"
                    )
                return

        # Проверяем данные атакующего и жертвы
        cursor.execute("""
            SELECT bio_experience, contagion, pathogens, virus_skill, lethality 
            FROM users WHERE user_id = ?
        """, (user_id,))
        attacker_data = cursor.fetchone()

        cursor.execute("""
            SELECT bio_experience, immunity, username, user_id, lab_name 
            FROM users WHERE user_id = ?
        """, (victim_id,))
        victim_data = cursor.fetchone()

        if not victim_data:
            await message.reply("❌ Жертва не найдена в базе данных.")
            return

        # Получаем данные для атаки
        attacker_contagion = attacker_data[1]
        victim_immunity = victim_data[1]
        pathogens = attacker_data[2]
        virus_skill = attacker_data[3]
        lethality = attacker_data[4]

        # Проверка иммунитета жертвы
        if victim_immunity > attacker_contagion:
            victim_display_name = f"""<a href="tg://openmessage?user_id={victim_data[3]}">{victim_data[2]}</a>"""
            # Изменения: если иммунитет слишком велик, патоген все равно тратится
            new_pathogens = pathogens - 1
            cursor.execute("UPDATE users SET pathogens = ? WHERE user_id = ?", (new_pathogens, user_id))
            await message.reply(
                f"❌ Иммунитет жертвы {victim_display_name} слишком велик! Осталось патогенов: {new_pathogens}",
                parse_mode="HTML"
            )
            return

        # Расчёт опыта и обновление данных
        victim_experience = victim_data[0]
        base_experience = max(1, victim_experience // 10)
        virus_bonus_percent = virus_skill * 1.5
        virus_bonus = int(base_experience * (virus_bonus_percent / 100))
        total_experience = base_experience + virus_bonus

        mutation_happened = random.random() < 0.1
        if mutation_happened:
            mutation_bonus = total_experience * (virus_skill / 100)
            total_experience += int(mutation_bonus)
            mutation_text = f" <b>🎁 Мутация вируса!</b>"
        else:
            mutation_text = ""

        # Проверка старого опыта, если был уже заражён
        cursor.execute("""
            SELECT experience_gained FROM infected WHERE user_id = ? AND victim_id = ? ORDER BY infect_date DESC LIMIT 1
        """, (user_id, victim_id))
        previous_infected_data = cursor.fetchone()

        if previous_infected_data:
            previous_experience = previous_infected_data[0]
            experience_diff = total_experience - previous_experience
            if experience_diff > 0:
                experience_message = f"+{experience_diff:,} био ежи"
            elif experience_diff < 0:
                experience_message = f"{experience_diff:,} био ежи"
            else:
                experience_message = f"-{experience_diff:,} био ежи"
        else:
            experience_message = f"+{total_experience:,} био ежи"

        # Уменьшаем патогены
        new_pathogens = pathogens - 1
        cursor.execute("UPDATE users SET pathogens = ? WHERE user_id = ?", (new_pathogens, user_id))

        # Добавляем горячку
        fever_duration = max(1, (lethality // 3) + 1)
        fever_end_time = (datetime.now() + timedelta(minutes=fever_duration)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("UPDATE users SET fever_end_time = ? WHERE user_id = ?", (fever_end_time, victim_id))

        # Обновление опыта
        cursor.execute("UPDATE users SET bio_experience = bio_experience + ? WHERE user_id = ?", (total_experience, user_id))

        # Сохраняем заражение
        infection_end_date = (datetime.now() + timedelta(days=lethality)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            INSERT INTO infected (user_id, victim_id, infect_date, infect_end_date, victim_experience, experience_gained)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, victim_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), infection_end_date, victim_experience, total_experience))

        conn.commit()

        attacker_display_name = f'<a href="tg://openmessage?user_id={user_id}">{user_data[2]}</a>'
        victim_display_name = f'<a href="tg://openmessage?user_id={victim_data[3]}">{victim_data[4] if victim_data[4] else victim_data[2]}</a>'
        
        await message.reply(
            f"🎄 {attacker_display_name} подверг заражению {victim_display_name} патогеном «{pathogen_name}»\n"
            f"🎁 {base_experience} подарков\n"
            f"{experience_message} {mutation_text}\n"
            f"❄️ Горячка на {fever_duration} мин.\n"
            f"🎅 Заражение на {lethality} дней\n"
            f"🦠 Осталось патогенов: {new_pathogens}\n",
            parse_mode="HTML"
        )

    except Exception as e:
        await message.reply(f"❌ Произошла ошибка: {str(e)}")

        await run_lab_cycle(user_id)

    except Exception as e:
        await message.reply(f"❌ Произошла ошибка: {str(e)}")

async def run_lab_cycle(user_id):
    """Цикл восстановления патогенов в лаборатории."""
    # Логика лаборатории
    cursor.execute('SELECT pathogens, qualification FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()

    if not user_data:
        return

    pathogens, qualification = user_data
    recovery_time = max(20 - qualification * 2, 5)
    next_recovery = datetime.now() + timedelta(minutes=recovery_time)

    new_pathogens = pathogens + 1
    cursor.execute("UPDATE users SET pathogens = ? WHERE user_id = ?", (new_pathogens, user_id))
    conn.commit()

@dp.message_handler(lambda message: message.text.lower() == "вак")
async def buy_vaccine(message: types.Message):
    cursor.execute('SELECT user_id, is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()

    if not user_data:
        await message.reply("❌ Вы не зарегистрированы в боте. Используйте /start для регистрации.", parse_mode="HTML")
        return

    if user_data[1] == 1:
        return

    user_id = message.from_user.id

    cursor.execute("SELECT fever_end_time, bio_resources FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    if not user_data or not user_data[0]:
        await message.reply("❄️ Морозная свежесть - никакой горячки! 🌟")
        return

    fever_end_time = user_data[0]
    bio_resources = user_data[1]
    fever_end = datetime.strptime(fever_end_time, '%Y-%м-%d %H:%M:%S')
    remaining_time = fever_end - datetime.now()

    if remaining_time <= timedelta(0):
        await message.reply("❄️ Морозная свежесть - никакой горячки! 🌟")
        return

    fever_minutes = math.ceil(remaining_time.total_seconds() / 60)
    vaccine_cost = fever_minutes * 50

    if bio_resources < vaccine_cost:
        await message.reply(f"🎁 Для новогоднего чуда не хватает {vaccine_cost:,} био-ресурсов! 🌟")
        return

    cursor.execute("""
        UPDATE users 
        SET fever_end_time = NULL,
            bio_resources = bio_resources - ?
        WHERE user_id = ?
    """, (vaccine_cost, user_id))
    conn.commit()

    await message.reply(f"🎅💉 Вакцина излечила вас от горячки. Стоимость вакцины: {vaccine_cost:,} био ресурсов 🎄")

@dp.message_handler(lambda message: message.text.lower() == "лаб")
async def lab_report(message: types.Message):
    cursor.execute('SELECT user_id, is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()

    if not user_data:
        await message.reply("❌ Вы не зарегистрированы в боте. Используйте /start для регистрации.", parse_mode="HTML")
        return

    if user_data[1] == 1:  # Проверка на бан
        return

    try:
        user_id = message.from_user.id

        cursor.execute('''
            SELECT 
                bio_experience, bio_resources, skill_level, contagion, immunity, 
                virus_skill, lethality, pathogens, max_pathogens, qualification, 
                pathogen_name, COALESCE(lab_name, username) AS lab_display_name 
            FROM users 
            WHERE user_id = ?
        ''', (user_id,))
        user = cursor.fetchone()

        if not user:
            await message.answer("❌ Профиль не найден!")
            return

        (bio_experience, bio_resources, skill_level, contagion, immunity, 
         virus_skill, lethality, pathogens, max_pathogens, qualification, 
         pathogen_name, lab_display_name) = user

        recovery_time = max(20 - qualification * 2, 5)
        remaining_seconds = recovery_time * 60
        if remaining_seconds >= 60:
            minutes = remaining_seconds // 60
            seconds = remaining_seconds % 60
            recovery_time_str = f"{minutes} мин {seconds} сек"
        else:
            recovery_time_str = f"{remaining_seconds} сек"

        name = message.from_user.first_name
        await message.reply(f"""🎄 <i>Праздничное досье:</i> <i>{lab_display_name or name}</i>

<blockquote>❄️ Новогодний патоген: <i>{pathogen_name}</i>
🎁 <b>Запас штаммов:</b> <i>{pathogens}/{max_pathogens}</i>
🎅 <b>Уровень исследователя:</b> <i>{qualification}</i>
⏱️ <b>Восстановление штамма:</b> <i>{recovery_time_str}</i>
</blockquote>

<b>[🎊 Праздничные навыки]</b>
<blockquote>├ 🌟 <b>Уровень мастерства:</b> <i>{skill_level}</i>
├ 🦠 <b>Сила заражения:</b> <i>{contagion}</i>
├ ⛄ <b>Зимний иммунитет:</b> <i>{immunity}</i>
├ 🎆 <b>Вирусная мощь:</b> <i>{virus_skill}</i>
└ ❄️ <b>Ледянная летальность:</b> <i>{lethality}</i></blockquote>

<b>[🎈 Праздничные достижения]</b>
<blockquote>├ 🎉 <b>подарков:</b> <i>{bio_experience}</i>
└ 🎀 <b>Био-ресурсы:</b> <i>{bio_resources}</i></blockquote>
""", parse_mode="HTML")
    finally:
        conn.commit()

# Создание таблицы банов
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_bans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    ban_type TEXT,  -- 'lab' или 'pathogen'
    ban_end TEXT,
    ban_reason TEXT,
    banned_by INTEGER,
    banned_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)''')

# Функция проверки бана
async def check_ban(user_id: int, ban_type: str) -> tuple:
    current_time = datetime.utcnow()
    
    cursor.execute('''
        SELECT ban_end, ban_reason, banned_by 
        FROM user_bans 
        WHERE user_id = ? AND ban_type = ? 
        AND ban_end > ? 
        ORDER BY ban_end DESC 
        LIMIT 1
    ''', (user_id, ban_type, current_time.strftime('%Y-%m-%d %H:%M:%S')))
    
    ban_info = cursor.fetchone()
    
    if ban_info:
        ban_end = datetime.strptime(ban_info[0], '%Y-%m-%d %H:%M:%S')
        if current_time < ban_end:
            return ban_info
    return None

# Функция форматирования времени бана
def format_ban_message(ban_info, admin_name):
    ban_end = datetime.strptime(ban_info[0], '%Y-%m-%d %H:%M:%S')
    current_time = datetime.utcnow()
    time_left = ban_end - current_time
    hours = int(time_left.total_seconds() // 3600)
    minutes = int((time_left.total_seconds() % 3600) // 60)
    
    return (f"❌ У вас действует наказание по причине: {ban_info[1]}\n"
            f"Выдал: <a href='tg://user?id={ban_info[2]}'>{admin_name}</a>\n"
            f"Осталось: {hours} ч. {minutes} мин.")

@dp.message_handler(lambda message: message.text.lower() == '/лабы')
async def show_lab_changes(message: types.Message):
     if message.from_user.id not in [6832369115, 1383131753]:
        return
        
        cursor.execute('''
        SELECT u.username, u.lab_name, pu.timestamp
        FROM users u
        LEFT JOIN pathogen_updates pu ON u.user_id = pu.user_id
        WHERE u.lab_name IS NOT NULL
        ORDER BY pu.timestamp DESC
        LIMIT 40
    ''')
        lab_changes = cursor.fetchall()

        if not lab_changes:
            await message.reply("❌ Нет данных о последних изменениях лабораторий.", parse_mode="HTML")
            return

    # Формируем ответ с последними изменениями лабораторий
        response = "🍊 <b>Последние изменения названий лабораторий:</b>\n\n"
        for index, (username, lab_name, timestamp) in enumerate(lab_changes, start=1):
        # Преобразуем timestamp в читаемый формат
            formatted_time = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S').strftime('%d-%m-%Y %H:%M:%S')
            response += f"{index}. @{username} - {lab_name} (изменено: {formatted_time})\n"

        await message.reply(response, parse_mode="HTML")

@dp.message_handler(lambda message: message.text.lower().startswith("+имя лаб"))
async def set_lab_name(message: types.Message):
    cursor.execute('SELECT user_id, is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        await message.reply("❌ Вы не зарегистрированы в боте. Используйте /start для регистрации.", parse_mode="HTML")
        return

    # Проверка на заблокированного пользователя
    if user_data[1] == 1:
        await message.reply("❌ Вы заблокированы. Не можете изменять данные лаборатории.", parse_mode="HTML")
        return

    # Получаем имя лаборатории после команды
    lab_name = message.text[8:].strip()
    
    # Проверка на пустое имя лаборатории
    if not lab_name:
        await message.reply("📔 <b>Укажите название лаборатории.</b>", parse_mode="HTML")
        return

    # Проверка на слишком длинное имя лаборатории
    if len(lab_name) > 20:
        await message.reply("❌ Слишком длинное имя лаборатории! Максимум 20 символов.", parse_mode="HTML")
        return

    cursor.execute('SELECT id, lab_name, reason, punishment_duration, unpunished_at FROM labs WHERE user_id = ?', (message.from_user.id,))
    lab_data = cursor.fetchone()

    current_time = datetime.now()

    if lab_data:
        unpunished_at = datetime.strptime(lab_data[4], '%Y-%m-%d %H:%M:%S')
        if unpunished_at > current_time:
            await message.reply(f"❌ Ваше наказание еще не истекло. Вы не можете изменить имя лаборатории.\n"
                                 f"⏳ Ожидайте до {unpunished_at.strftime('%Y-%m-%d %H:%M:%S')}.", parse_mode="HTML")
            return

    cursor.execute('''
        INSERT INTO labs (user_id, lab_name, reason, punishment_duration, unpunished_at, timestamp) 
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET lab_name = ?, reason = ?, punishment_duration = ?, 
        unpunished_at = ?, timestamp = ?
    ''', (message.from_user.id, lab_name, "", 0, "", current_time.strftime('%Y-%m-%d %H:%M:%S'),
          lab_name, "", 0, "", current_time.strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()

    # Ответ пользователю
    await message.reply(f"✅ Имя вашей лаборатории установлено как: <b>{lab_name}</b>", parse_mode="HTML")


@dp.message_handler(lambda message: message.text.lower() == "-имя лаб")
async def reset_lab_name(message: types.Message):
    cursor.execute('SELECT user_id, is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        await message.reply("❌ Вы не зарегистрированы в боте. Используйте /start для регистрации.", parse_mode="HTML")
        return

    # Если пользователь заблокирован
    if user_data[1] == 1:
        # Проверяем дату окончания наказания
        cursor.execute('SELECT unpunished_at FROM pathogen_updates WHERE user_id = ?', (message.from_user.id,))
        punishment_data = cursor.fetchone()

        if punishment_data:
            unpunished_at_str = punishment_data[0]
            unpunished_at = datetime.strptime(unpunished_at_str, '%Y-%m-%d %H:%M:%S')
            current_time = datetime.utcnow()

            # Если наказание еще не истекло
            if current_time < unpunished_at:
                time_left = unpunished_at - current_time
                minutes_left = time_left.total_seconds() // 60
                await message.reply(f"❌ Вы находитесь под наказанием! Можно будет использовать команду только через {int(minutes_left)} минут.")
                return
            else:
                # Если наказание прошло, снимаем блокировку
                cursor.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (message.from_user.id,))
                conn.commit()

    # Сбрасываем имя лаборатории
    cursor.execute('UPDATE users SET lab_name = NULL WHERE user_id = ?', (message.from_user.id,))
    conn.commit()
    await message.reply("✅ Имя вашей лаборатории сброшено.")


@dp.message_handler(lambda message: message.text.startswith('/rlab'))
async def reset_lab_name_by_admin(message: types.Message):
    if message.from_user.id not in [6832369115, 1383131753]:
        return

    try:
        args = message.get_args().split(maxsplit=1)
        if len(args) < 1:
            await message.reply("❌ Формат: /rlab [ID] [причина (не обязательно)]\nПример: /rlab 123456789 плохое имя лаборатории")
            return

        target_id = int(args[0])
        reason = args[1] if len(args) > 1 else "не указана"

        # Проверяем существование пользователя
        cursor.execute('SELECT username, lab_name, is_banned FROM users WHERE user_id = ?', (target_id,))
        user_data = cursor.fetchone()
        
        if not user_data:
            await message.reply("❌ Пользователь не найден в базе данных.")
            return

        username, lab_name, is_banned = user_data

        current_time = datetime.utcnow()
        end_time = current_time + timedelta(weeks=1)

        # Получаем данные о наказании из таблицы labs
        cursor.execute('SELECT reason, unpunished_at FROM labs WHERE user_id = ?', (target_id,))
        lab_data = cursor.fetchone()

        if lab_data:
            punishment_reason, unpunished_at_str = lab_data
            unpunished_at = datetime.strptime(unpunished_at_str, '%Y-%m-%d %H:%M:%S')
        else:
            punishment_reason = None
            unpunished_at = None

        # Если наказание уже есть, снимем его
        if is_banned:
            cursor.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (target_id,))
            cursor.execute('UPDATE labs SET unpunished_at = ?, reason = ?, punishment_duration = 0 WHERE user_id = ?',
                           (current_time.strftime('%Y-%m-%d %H:%M:%S'), "Наказание снято", 0, target_id))
            conn.commit()
            await message.reply(f"✅ Наказание для пользователя <a href='tg://user?id={target_id}'>{username}</a> снято.", parse_mode="HTML")
        else:
            # Если наказания нет, устанавливаем новое на неделю
            cursor.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (target_id,))
            cursor.execute('''
                INSERT INTO labs (user_id, lab_name, reason, punishment_duration, unpunished_at, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET 
                    reason = ?, 
                    punishment_duration = ?, 
                    unpunished_at = ?, 
                    timestamp = ?
            ''', (target_id, lab_name, reason, 7, end_time.strftime('%Y-%m-%d %H:%M:%S'), current_time.strftime('%Y-%m-%d %H:%M:%S'),
                  reason, 7, end_time.strftime('%Y-%m-%d %H:%M:%S'), current_time.strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()

            await message.reply(
                f"👤 Пользователь: <a href='tg://user?id={target_id}'>{username}</a>\n"
                f"🏷 Старое имя: {lab_name or 'Не установлено'}\n"
                f"⏰ Срок наказания: 7 дней\n"
                f"📝 Причина: {reason}\n"
                f"❌ Наказание будет снято после {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
                parse_mode="HTML"
            )

    except Exception as e:
        print(f"Error in reset_lab_name_by_admin: {e}")
        await message.reply("❌ Произошла ошибка при выполнении команды.")

@dp.message_handler(lambda message: message.text.lower().startswith('+имя патогена'))
async def set_pathogen_name(message: types.Message):
    cursor.execute('SELECT user_id, is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()

    if not user_data:
        await message.reply("❌ Вы не зарегистрированы в боте. Используйте /start для регистрации.", parse_mode="HTML")
        return

    # Проверка, находится ли пользователь под наказанием
    if user_data[1] == 1:  # Если is_banned = 1, игнорируем дальнейшее выполнение
        await message.reply("❌ Вы не можете изменить имя патогена, так как находитесь под наказанием.", parse_mode="HTML")
        return

    # Получаем имя патогена после команды, убираем лишние пробелы
    pathogen_name = message.text[len('+имя патогена'):].strip()

    if not pathogen_name:
        await message.reply(
            f"⚠️ Укажите название патогена\n"
            f"└ Пример: +имя патогена Омикрон",
            parse_mode="HTML"
        )
        return

    if len(pathogen_name) > 20:
        await message.reply(
            f"❌ Слишком длинное название!\n"
            f"└ Максимум 20 символов",
            parse_mode="HTML"
        )
        return

    cursor.execute('UPDATE users SET pathogen_name = ? WHERE user_id = ?', (pathogen_name, message.from_user.id))
    conn.commit()

    await message.reply(
        f"🧬 Патоген переименован\n"
        f"└ Новое имя: {pathogen_name}",
        parse_mode="HTML"
    )

@dp.message_handler(lambda message: message.text.lower() == "-имя патогена")
async def reset_pathogen_name(message: types.Message):
    cursor.execute('SELECT user_id, is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        await message.reply("❌ Вы не зарегистрированы в боте. Используйте /start для регистрации.", parse_mode="HTML")
        return
        
    if user_data[1] == 1:
        # Проверка на наказание из таблицы pathogen_updates
        cursor.execute('SELECT unpunished_at FROM pathogen_updates WHERE user_id = ?', (message.from_user.id,))
        punishment_data = cursor.fetchone()

        if punishment_data:
            unpunished_at_str = punishment_data[0]
            unpunished_at = datetime.strptime(unpunished_at_str, '%Y-%m-%d %H:%M:%S')
            current_time = datetime.utcnow()

            if current_time < unpunished_at:
                time_left = unpunished_at - current_time
                minutes_left = time_left.total_seconds() // 60
                await message.reply(f"❌ Вы находитесь под наказанием! Можно будет использовать команду только через {int(minutes_left)} минут.")
                return
            else:
                # Наказание снято, снимаем флаг is_banned
                cursor.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (message.from_user.id,))
                conn.commit()
        
    # Если нет наказания или оно уже прошло, сбрасываем имя патогена
    cursor.execute('UPDATE users SET pathogen_name = "котячка" WHERE user_id = ?', (message.from_user.id,))
    conn.commit()
    await message.reply("✅ Имя вашего патогена сброшено на стандартное: «котячка».")

@dp.message_handler(lambda message: message.text.lower().startswith('/rpat '))
async def admin_reset_pathogen(message: types.Message):
    cursor.execute('SELECT admin_level FROM admins WHERE user_id = ?', (message.from_user.id,))
    admin_data = cursor.fetchone()
    
    # Проверка на авторизованных администраторов
    if message.from_user.id not in [6832369115, 1291390143,]:
        return

    try:
        args = message.get_args().split(maxsplit=1)
        if len(args) < 1:
            await message.reply("❌ Формат: /rpat [ID] [причина (не обязательно)]\nПример: /rpat 123456789 плохое имя патогена")
            return

        target_id = int(args[0])
        reason = args[1] if len(args) > 1 else "не указана"

        cursor.execute('SELECT username, pathogen_name FROM users WHERE user_id = ?', (target_id,))
        user_data = cursor.fetchone()
        
        if not user_data:
            await message.reply("❌ Пользователь не найден в базе данных.")
            return

        username, pathogen_name = user_data

        # Срок наказания: 7 дней
        current_time = datetime.utcnow()
        end_time = current_time + timedelta(weeks=1)

        # Добавляем запись о наказании в таблицу pathogen_updates
        cursor.execute('''
            INSERT INTO pathogen_updates (user_id, reason, punishment_duration, unpunished_at, timestamp) 
            VALUES (?, ?, ?, ?, ?)
        ''', (target_id, reason, 7, end_time.strftime('%Y-%m-%d %H:%M:%S'), current_time.strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()

        await message.reply(
            f"👤 Пользователь: <a href='tg://user?id={target_id}'>{username}</a>\n"
            f"🏷 Старый патоген: {pathogen_name}\n"
            f"⏰ Срок наказания: 7 дней\n"
            f"📝 Причина: {reason}", 
            parse_mode="HTML"
        )

    except Exception as e:
        print(f"Error in admin_reset_pathogen: {e}")
        await message.reply("❌ Произошла ошибка при выполнении команды.")

# Команда "Биотоп" с учетом имени лаборатории
@dp.message_handler(lambda message: message.text.lower().startswith("биотоп"))
async def bio_top(message: types.Message):
    cursor.execute('SELECT user_id, is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        await message.reply("❌ Вы не зарегистрированы в боте. Используйте /start для регистрации.", parse_mode="HTML")
        return
        
    if user_data[1] == 1:
        return

    args = message.text.split()

    try:
        if len(args) == 1:
            cursor.execute('''
                SELECT 
                    user_id, 
                    CASE 
                        WHEN lab_name IS NOT NULL AND lab_name != '' THEN lab_name
                        ELSE COALESCE(username, user_id)
                    END AS display_name, 
                    bio_experience
                FROM users 
                ORDER BY bio_experience DESC 
                LIMIT 20
            ''')
            top_users = cursor.fetchall()

            if not top_users:
                await message.reply("❌ Топ лабораторий пуст.")
                return

            top_message = "🎄 <b>Зимний топ лабораторий по био-опыту:</b>\n\n"
            total_experience = sum(user[2] for user in top_users)
            user_id_from_message = message.from_user.id

            for idx, (user_id, display_name, bio_experience) in enumerate(top_users, 1):
                if user_id == user_id_from_message:
                    top_message += f'''{idx}. <a href="tg://openmessage?user_id={user_id}">{display_name}</a> | {bio_experience:,} подарков\n'''
                    continue
                top_message += f'''{idx}. <a href="tg://openmessage?user_id={user_id}">{display_name}</a> | {bio_experience:,} подарков\n'''

            top_message += f"\n☃️ Общий опыт лабораторий: {total_experience:,}"

        elif len(args) == 2 and args[1].lower() == "навык":
            cursor.execute('''
                SELECT 
                    user_id, 
                    CASE 
                        WHEN lab_name IS NOT NULL AND lab_name != '' THEN lab_name
                        ELSE COALESCE(username, user_id)
                    END AS display_name, 
                    skill_level
                FROM users 
                ORDER BY skill_level DESC 
                LIMIT 20
            ''')
            top_users = cursor.fetchall()

            if not top_users:
                await message.reply("❌ Топ лабораторий пуст.")
                return

            top_message = "🎚️ <b>Топ лабораторий по уровням навыков:</b>\n"
            total_skill_level = sum(user[2] for user in top_users)

            for idx, (user_id, display_name, skill_level) in enumerate(top_users, 1):
                top_message += f'''{idx}. <a href="tg://openmessage?user_id={user_id}">{display_name}</a> | {skill_level} ур.\n'''

            top_message += f"\n🎚️ Суммарный уровень навыков: {total_skill_level}"

        elif len(args) == 2 and args[1].lower() == "вирус":
            cursor.execute('''
                SELECT 
                    user_id, 
                    CASE 
                        WHEN lab_name IS NOT NULL AND lab_name != '' THEN lab_name
                        ELSE COALESCE(username, user_id)
                    END AS display_name, 
                    virus_skill
                FROM users 
                ORDER BY virus_skill DESC 
                LIMIT 20
            ''')
            top_users = cursor.fetchall()

            if not top_users:
                await message.reply("❌ Топ лабораторий пуст.")
                return

            top_message = "🔬 <b>Топ лабораторий по уровням вирусов:</b>\n"
            total_virus_skill = sum(user[2] for user in top_users)

            for idx, (user_id, display_name, virus_skill) in enumerate(top_users, 1):
                top_message += f'''{idx}. <a href="tg://openmessage?user_id={user_id}">{display_name}</a> | {virus_skill} ур.\n'''

            top_message += f"\n🔬 Суммарный уровень вирусов: {total_virus_skill}"

        else:
            top_message = "❌ Неправильный запрос. Используйте команду как: биотоп [навык/вирус]."

        await message.answer(top_message, parse_mode='HTML', disable_web_page_preview=True)

    except Exception as e:
        print(f"Ошибка в команде биотоп: {e}")
        await message.reply("❌ Произошла ошибка при выполнении команды.")
        
# Команда "Лист" (список всех пользователей)
@dp.message_handler(commands=['лист'])
async def list_users(message: types.Message):
    if message.from_user.id not in [6832369115]:
        return

    # Если user_id совпадает, выполняем команду
    cursor.execute('SELECT user_id, registration_date FROM users')
    users = cursor.fetchall()

    list_message = "📋 Список пользователей:\n"
    for index, (user_id, registration_date) in enumerate(users, start=1):
        list_message += f'{index}. ID: <a href="tg://openmessage?user_id={user_id}">котик</a> | {registration_date}\n'
    
    await message.reply(list_message, parse_mode="HTML")

# Команда "Bioexp" — Суммарный опыт всех игроков
@dp.message_handler(commands=['bioexp'])
async def bio_exp(message: types.Message):
    if message.from_user.id not in [6832369115]:
        return
    cursor.execute('SELECT SUM(bio_experience) FROM users')
    total_exp = cursor.fetchone()[0]
    await message.reply(
    f"🎄 Под ёлкой собрано:\n"
    f"└ 🎁 {total_exp:,} подарков",
    parse_mode="HTML"
)

# Функция для общей логики прокачки навыков
async def process_skill_upgrade(message: types.Message, skill: str, skill_column: str, cost_multiplier: float):
    cursor.execute('SELECT user_id, is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        await message.reply("🎄❄️ вы не зарегистрированы в нашей праздничной лаборатории! Используйте /start, чтобы начать путешествие! 🎅", parse_mode="HTML")
        return
        
    if user_data[1] == 1:
        return

    user_id = message.from_user.id
    
    # Проверяем формат команды
    command_parts = message.text.lower().split()
    
    # Если после команды нет пробела, но есть цифры - это ошибка
    if len(command_parts) == 1 and any(char.isdigit() for char in command_parts[0]):
        await message.reply("❄️🎅 Ах, после навыка должен быть пробел перед числом уровней! Пробуем снова? 🎁", parse_mode="HTML")
        return
    
    # Определяем количество уровней
    try:
        if len(command_parts) > 1:
            levels = int(command_parts[1])
        else:
            levels = 1
    except ValueError:
        return

    if levels < 1 or levels > 5:
        await message.reply("🎄❄️ О, можно прокачать только от 1 до 5 уровней за раз! 🎅 Попробуйте снова! 🎁", parse_mode="HTML")
        return

    is_upgrade = message.text.startswith("++")

    cursor.execute(
        f'SELECT bio_resources, {skill_column} FROM users WHERE user_id = ?',
        (user_id,)
    )
    user = cursor.fetchone()

    if user:
        bio_resources, current_value = user

        if skill == "квалификация" and current_value + levels > 20:
            await message.reply("🎄🎅 Максимальный уровень квалификации — 20!❄️", parse_mode="HTML")
            return

        # Расчет стоимости без скидки
        total_cost = sum([int((current_value + i + 1) ** cost_multiplier) for i in range(levels)])
        formatted_cost = '{0:,}'.format(total_cost).replace(',', ' ')

        skill_emojis = {
            "заразность": "🦠",
            "иммунитет": "🛡️",
            "вирус": "🧬",
            "навык": "📚",
            "патогены": "🧪",
            "квалификация": "🎓",
            "летальность": "☠️"
        }

        skill_emoji = skill_emojis.get(skill, "✨")

        if not is_upgrade:
            # Отображаем прокачку с текущего уровня на новый
            await message.reply(
                f"🎄✨ <b>Зимняя магия прокачки навыка</b> <i>{skill_emoji} «{skill}»</i> 🎅\n\n"
                f"❄️ <b>С уровня {current_value} до {current_value + levels}</b>\n"
                f"🎁 <b>Стоимость прокачки:</b> <i>{formatted_cost}</i> био-ресурсов\n",
                parse_mode="HTML"
            )
            return

        if bio_resources >= total_cost:
            new_value = current_value + levels
            cursor.execute(
                f'UPDATE users SET bio_resources = bio_resources - ?, {skill_column} = ? WHERE user_id = ?',
                (total_cost, new_value, user_id)
            )
            conn.commit()
            # Успешная прокачка
            await message.reply(
                f"🎄🎉 <b>Волшебная прокачка завершена!</b> <i>{skill_emoji} «{skill}»</i> успешно улучшен! 🎅\n\n"
                f"❄️ <b>С уровня {current_value} до {new_value}</b> 🎁\n"
                f"💰 <b>Стоимость:</b> <i>{formatted_cost}</i> био-ресурсов\n",
                parse_mode="HTML"
            )
        else:
            await message.reply(
                f"❄️🎅 <b>Ой, ресурсов не хватает!</b> 🎁\n\n"
                f"{skill_emoji} Для прокачки <b>{skill}</b> нужно:\n"
                f"💰 <i>{formatted_cost}</i> био-ресурсов\n",
                parse_mode="HTML"
            )
    else:
        await message.reply("🎄❄️ Упс, не удалось найти вашу лабораторию! Пройдите регистрацию, используя /start! 🎅", parse_mode="HTML")

# Команды для прокачки навыков
@dp.message_handler(lambda message: message.text.lower().startswith(("+зз", "++зз", "++заразность", "+заразность")))
async def upgrade_contagion(message: types.Message):
    await process_skill_upgrade(message, "заразность", "contagion", 2.5)

@dp.message_handler(lambda message: message.text.lower().startswith(("+иммун", "++иммун", "++иммунитет", "+иммунитет")))
async def upgrade_immunity(message: types.Message):
    await process_skill_upgrade(message, "иммунитет", "immunity", 2.4575)

@dp.message_handler(lambda message: message.text.lower().startswith(("+вирус", "++вирус")))
async def upgrade_virus(message: types.Message):
    await process_skill_upgrade(message, "вирус", "virus_skill", 2.7)

@dp.message_handler(lambda message: message.text.lower().startswith(("+навык", "++навык")))
async def upgrade_skill(message: types.Message):
    await process_skill_upgrade(message, "навык", "skill_level", 2.8)

@dp.message_handler(lambda message: message.text.lower().startswith(("+паты", "++паты", "++патоген", "++пат", "+пат", "+патоген")))
async def upgrade_pathogens(message: types.Message):
    await process_skill_upgrade(message, "патогены", "max_pathogens", 2.0)

@dp.message_handler(lambda message: message.text.lower().startswith(("+квала", "++квала", "+квалификация", "++квалификация", "+разработка", "++разработка")))
async def upgrade_qualification(message: types.Message):
    await process_skill_upgrade(message, "квалификация", "qualification", 2.6)

@dp.message_handler(lambda message: message.text.lower().startswith(("+летал", "++летал", "+летальность", "++летальность")))
async def upgrade_lethality(message: types.Message):
    await process_skill_upgrade(message, "летальность", "lethality", 1.795)

@dp.message_handler(lambda message: message.text.lower() == "!помощь")
async def help_command(message: types.Message):
    cursor.execute('SELECT user_id, is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        await message.reply("❌ Вы не зарегистрированы в боте. Используйте /start для регистрации.", parse_mode="HTML")
        return
        
    if user_data[1] == 1:
        return

    await message.answer(f"""🎄 <b>Новогодний путеводитель 2024</b>

🎅 <b>Волшебные команды:</b>
<code>!помощь</code> - Книга праздничных заклинаний
<code>лаб</code> - Зимняя лаборатория Деда Мороза
<code>вак</code> - Эликсир от зимней горячки
<code>биотоп</code> - Рейтинг волшебников года
<code>биотоп навык</code> - Мастера зимних чар
<code>биотоп вирус</code> - Короли ледяных вирусов

❄️ <b>Зимнее развитие:</b>
+(навык) - Расчёт цены заморозки
++(навык) - Усиление зимней магии

<blockquote>🎁 <b>Праздничные названия:</b>
<code>+имя лаб</code> (название) - Именование снежной лаборатории
<code>-имя лаб</code> - Сброс имени лаборатории
<code>+имя патогена</code> (название) - Назвать ледяной патоген
<code>-имя патогена</code> - Сброс имени патогена</blockquote>

⛄ <b>Особые заклинания:</b>
<code>кусь</code> (айди/юзернейм) - Заморозить цель
<code>мои жертвы</code> - Список замороженных
<code>мои слетевшие</code> - Список оттаявших
<code>ид</code> (реплай/ссылка) - Код волшебника""", parse_mode="HTML")

# код для проверки бана
async def is_user_banned(user_id: int) -> bool:
    cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return bool(result and result[0] == 1)

@dp.message_handler(lambda message: message.text.lower() == "бот")
async def bot_command(message: types.Message):
    cursor.execute('SELECT user_id, is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        await message.reply("❌ Вы не зарегистрированы в боте. Используйте /start для регистрации.", parse_mode="HTML")
        return
        
    if user_data[1] == 1:
        return
        
    start_time = time.time()
    bot_text = "🎄 Праздничная лаборатория активна!"

    sent_message = await message.reply(bot_text)

    response_time = round((time.time() - start_time) * 1000)
    bot_text = (
        f"🎄 Праздничная лаборатория активна!\n"
        f"└ 🧬 Скорость реакции: {response_time} мс"
    )
    await sent_message.edit_text(bot_text)

@dp.message_handler(lambda message: message.text.lower().startswith('ид'))
async def id_command(message: types.Message):
    cursor.execute('SELECT user_id, is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        await message.reply("🎄 Вы не зарегистрированы в праздничной лаборатории! Используйте /start ❄️", parse_mode="HTML")
        return
        
    if user_data[1] == 1:
        return

    try:
        # Получаем аргументы команды
        args = message.text.split(maxsplit=1)
        
        # Функция для форматирования ответа
        def format_user_info(user_id: int, username: str = None, is_self: bool = False) -> str:
            user_link = f"@{username}" if username else f'<a href="tg://user?id={user_id}">{user_id}</a>'
            prefix = "Ваш" if is_self else "ID пользователя"
            return f"🎅 {prefix} {user_link}: <code>{user_id}</code>"

        # Функция для извлечения ID из Telegram ссылок
        def extract_user_id_from_link(link: str) -> Optional[int]:
            try:
                if 'tg://user?id=' in link:
                    return int(link.split('=')[1])
                elif 'tg://openmessage?user_id=' in link:
                    return int(link.split('=')[1])
                return None
            except:
                return None

        # Если это реплай
        if message.reply_to_message:
            user_id = message.reply_to_message.from_user.id
            username = message.reply_to_message.from_user.username
            await message.reply(format_user_info(user_id, username), parse_mode="HTML")
            return

        # Если команда без аргументов
        if len(args) == 1:
            user_id = message.from_user.id
            username = message.from_user.username
            await message.reply(format_user_info(user_id, username, True), parse_mode="HTML")
            return

        # Получаем текст после команды
        query = args[1].strip()

        # Если это упоминание (@username)
        if query.startswith('@'):
            username = query[1:]
            if not re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
                await message.reply("❄️ Некорректный формат юзернейма! 🎄")
                return
            await message.reply(
                f"🎄 Для получения ID пользователя {query}, перешлите сообщение от этого пользователя ❄️", 
                parse_mode="HTML"
            )
            return

        # Если это ссылка t.me или telegram.me
        if 't.me/' in query or 'telegram.me/' in query:
            username = query.split('/')[-1]
            await message.reply(
                f"🎄 Для получения ID пользователя @{username}, перешлите сообщение от этого пользователя ❄️", 
                parse_mode="HTML"
            )
            return

        # Если это tg:// ссылка
        if query.startswith('tg://'):
            user_id = extract_user_id_from_link(query)
            if user_id:
                await message.reply(
                    f"🎅 ID пользователя по ссылке: <code>{user_id}</code>", 
                    parse_mode="HTML"
                )
                return
            else:
                await message.reply("❄️ Не удалось извлечь ID из ссылки! 🎄")
                return

        # Если это просто юзернейм без @
        if re.match(r'^[a-zA-Z0-9_]{5,32}$', query):
            await message.reply(
                f"🎄 Для получения ID пользователя @{query}, перешлите сообщение от этого пользователя ❄️", 
                parse_mode="HTML"
            )
            return

        # Если это число (возможно, уже ID)
        if query.isdigit():
            user_id = int(query)
            await message.reply(
                f"🎅 Указанный ID: <code>{user_id}</code>", 
                parse_mode="HTML"
            )
            return

        await message.reply("❄️ Некорректный формат запроса! 🎄")

    except Exception as e:
        print(f"Error in id_command: {e}")
        await message.reply("❄️ Произошла ошибка при обработке запроса! 🎄")

# Команда /reset — сброс всех параметров до стандартных
@dp.message_handler(lambda message: message.text.lower().startswith('/reset '))
async def reset_user(message: types.Message):
    if message.from_user.id not in [6832369115]:
        return

    args = message.text.split()  # Добавлено для получения аргументов команды

    try:
        target_user_id = int(args[1])
    except (IndexError, ValueError):
        # Если нет аргумента или он некорректный, обрабатываем это здесь
        target_user_id = message.from_user.id  # Сбрасываем параметры текущего пользователя

    if len(args) > 1:
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (target_user_id,))
        user_exists = cursor.fetchone()

        if not user_exists:
            await message.reply("❌ Пользователь с таким ID не найден.")
            return

        # Сбрасываем параметры пользователя с указанным ID
        cursor.execute('''
            UPDATE users 
            SET bio_experience = 0, 
                bio_resources = 0, 
                pathogens = 4, 
                skill_level = 1, 
                contagion = 1, 
                immunity = 0, 
                virus_skill = 1
            WHERE user_id = ?
        ''', (target_user_id,))
        conn.commit()

        await message.reply(f"✅ Параметры пользователя с ID {target_user_id} успешно сброшены до стандартных.")
    else:
        user_id = message.from_user.id
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        user_exists = cursor.fetchone()

        if not user_exists:
            await message.reply("❌ Вы не зарегистрированы в системе.")
            return

        # Сбрасываем параметры текущего пользователя до стандартных
        cursor.execute('''
            UPDATE users 
            SET bio_experience = 0, 
                bio_resources = 0, 
                pathogens = 4, 
                skill_level = 1, 
                contagion = 1, 
                immunity = 0, 
                virus_skill = 1
            WHERE user_id = ?
        ''', (user_id,))
        conn.commit()

        await message.reply("✅ Ваши параметры успешно сброшены до стандартных.")

# Функция для добавления колонок, если их нет
def add_missing_columns():
    # Проверяем существующие колонки
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = [column[1] for column in cursor.fetchall()]

    # Список необходимых колонок для бана с их типами
    columns_to_add = {
        'is_banned': 'INTEGER DEFAULT 0',
        'banned_at': 'TEXT DEFAULT NULL',
        'unbanned_at': 'TEXT DEFAULT NULL',
        'banned_by': 'INTEGER DEFAULT NULL',
        'ban_reason': 'TEXT DEFAULT NULL',
        'ban_end_time': 'TEXT DEFAULT NULL'
    }

    # Добавляем отсутствующие колонки
    for column_name, column_type in columns_to_add.items():
        if column_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
            except Exception as e:
                print(f"Error adding column {column_name}: {e}")
    
    conn.commit()

# Вызываем функцию для добавления колонок
add_missing_columns()

искл = [1291390143, 6832369115]

def parse_time(time_str: str) -> Optional[timedelta]:
    """
    Парсит строку времени в формате: число + единица измерения (d/h/m)
    Возвращает timedelta или None если формат неверный
    """
    time_match = re.match(r'(\d+)([dhm])', time_str.lower())
    if not time_match:
        return None
    
    amount = int(time_match.group(1))
    unit = time_match.group(2)
    
    time_units = {
        'd': lambda x: timedelta(days=x),
        'h': lambda x: timedelta(hours=x),
        'm': lambda x: timedelta(minutes=x)
    }
    
    return time_units.get(unit, lambda x: None)(amount)

@dp.message_handler(lambda message: message.text.lower().startswith("кас"))
async def toggle_ban(message: types.Message):
    if message.from_user.id not in [6832369115, 1291390143]:
        return

    args = message.text.split()
    if len(args) < 2:
        await message.reply("чота не то")
        return

    # Получение user_id из аргумента (поддержка как ID, так и username)
    target_arg = args[1]
    user_id = None

    if target_arg.isdigit():
        user_id = int(target_arg)
    elif target_arg.startswith('@'):
        username = target_arg[1:]
        cursor.execute('SELECT user_id FROM users WHERE LOWER(username) = LOWER(?)', (username,))
        result = cursor.fetchone()
        if result:
            user_id = result[0]

    if not user_id:
        await message.reply("❌ Пользователь не найден в базе данных.", parse_mode="HTML")
        return

    cursor.execute('SELECT user_id, is_banned, username FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()

    if not user_data:
        await message.reply("❌ Пользователь не найден в базе данных.", parse_mode="HTML")
        return

    moscow_tz = pytz.timezone('Europe/Moscow')
    current_time = datetime.now(moscow_tz)

    # Разбан пользователя
    if user_data[1] == 1:
        cursor.execute('''
            UPDATE users 
            SET is_banned = 0, 
                unbanned_at = ?,
                banned_at = NULL,
                ban_reason = NULL,
                banned_by = NULL,
                ban_end_time = NULL
            WHERE user_id = ?
        ''', (current_time.strftime('%Y-%m-%d %H:%M:%S'), user_id))
        conn.commit()

        await message.reply(
            f"✅ Пользователь <code>{user_id}</code> разблокирован\n"
            f"📅 Дата разблокировки: {current_time.strftime('%d.%m.%Y %H:%M:%S')} (МСК)\n"
            f"👤 Администратор: <a href='tg://openmessage?user_id={message.from_user.id}'>{message.from_user.full_name}</a>", 
            parse_mode="HTML"
        )
        return

    # Определение времени и причины бана
    time_delta = None
    ban_reason = "не указана"

    if len(args) > 2:
        # Проверка временного формата
        if any(args[2].lower().endswith(x) for x in ['d', 'h', 'm']):
            time_delta = parse_time(args[2])
            if not time_delta:
                await message.reply("❌ Неверный формат времени. Используйте: 1d, 2h, 30m", parse_mode="HTML")
                return
            ban_reason = " ".join(args[3:]) if len(args) > 3 else "не указана"
        else:
            ban_reason = " ".join(args[2:])

    ban_end_time = (current_time + time_delta).strftime('%Y-%m-%d %H:%M:%S') if time_delta else None

    cursor.execute('''
        UPDATE users 
        SET is_banned = 1, 
            banned_at = ?,
            ban_end_time = ?,
            ban_reason = ?,
            banned_by = ?,
            unbanned_at = NULL
        WHERE user_id = ?
    ''', (
        current_time.strftime('%Y-%m-%d %H:%M:%S'),
        ban_end_time,
        ban_reason,
        message.from_user.id,
        user_id
    ))
    conn.commit()

    ban_duration = f"до {(current_time + time_delta).strftime('%d.%m.%Y %H:%M:%S')} (МСК)" if time_delta else "навсегда"

    # Рождественско-новогоднее сообщение
    await message.reply(
        f"🎄🎅 Пользователь <a href='tg://openmessage?user_id={user_id}'>клик</a> заблокирован 🎅🎄\n"
        f"⏰ Срок блокировки: {ban_duration}\n"
        f"📝 Причина: {ban_reason}\n"
        f"👤 Администратор: <a href='tg://openmessage?user_id={message.from_user.id}'>{message.from_user.full_name}</a>\n",
        parse_mode="HTML"
    )

@dp.message_handler(lambda message: message.text.lower().startswith('/причина'))
async def get_ban_reason(message: types.Message):
    
    if message.from_user.id not in [6832369115, 1291390143]:
        return

    try:
        args = message.text.split()
        if len(args) != 2:
            await message.reply(
                "❌ Используйте формат: причина <ID> Пример: /причина 123456", 
                parse_mode="HTML"
            )
            return

        try:
            user_id = int(args[1])
        except ValueError:
            await message.reply("❌ ID пользователя должен быть числом.", parse_mode="HTML")
            return

        cursor.execute('''
            SELECT username, is_banned, ban_reason, banned_at, ban_end_time, banned_by
            FROM users 
            WHERE user_id = ?
        ''', (user_id,))
        
        user_data = cursor.fetchone()

        if not user_data:
            await message.reply("❌ Пользователь не найден в базе данных.", parse_mode="HTML")
            return

        username, is_banned, ban_reason, banned_at, ban_end_time, banned_by = user_data

        if not is_banned:
            await message.reply(
                f"✅ Пользователь <a href=tg://openmessage?user_id={user_id}'>{username}</a> не заблокирован.",
                parse_mode="HTML"
            )
            return

        moscow_tz = pytz.timezone('Europe/Moscow')
        current_time = datetime.now(moscow_tz)
        
        banned_at_moscow = datetime.strptime(banned_at, '%Y-%m-%d %H:%M:%S')
        banned_at_moscow = moscow_tz.localize(banned_at_moscow)
        
        ban_end_str = ""
        if ban_end_time:
            ban_end_moscow = datetime.strptime(ban_end_time, '%Y-%m-%d %H:%M:%S')
            ban_end_moscow = moscow_tz.localize(ban_end_moscow)
            
            if ban_end_moscow > current_time:
                time_left = ban_end_moscow - current_time
                days = time_left.days
                hours = time_left.seconds // 3600
                minutes = (time_left.seconds % 3600) // 60
                
                time_left_str = ""
                if days > 0:
                    time_left_str += f"{days} дн. "
                if hours > 0:
                    time_left_str += f"{hours} ч. "
                if minutes > 0:
                    time_left_str += f"{minutes} мин."
                    
                ban_end_str = f"⏰ Осталось: {time_left_str}\n"
            else:
                ban_end_str = "⏰ Срок блокировки истек\n"

        await message.reply(
            f"ℹ️ Информация о блокировке пользователя <a href='tg://openmessage?user_id={user_id}'>{username}</a>:\n\n"
            f"📝 Причина: {ban_reason}\n"
            f"📅 Дата блокировки: {banned_at_moscow.strftime('%d.%m.%Y %H:%M:%S')} (МСК)\n"
            f"{ban_end_str}"
            f"👤 Заблокировал: <a href='tg://openmessage?user_id={banned_by}'>Администратор</a>",
            parse_mode="HTML"
        )

    except Exception as e:
        print(f"Error in get_ban_reason: {e}")
        await message.reply("❌ Произошла ошибка при выполнении команды.")

@dp.message_handler(lambda message: message.text.lower() == "/changelog")
async def changelog_command(message: types.Message):
    cursor.execute('SELECT user_id, is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        await message.reply("❌ Вы не зарегистрированы в боте. Используйте /start для регистрации.", parse_mode="HTML")
        return
        
    if user_data[1] == 1:
        return
        
    changelog = """
🎄 <b>Список праздничных изменений:</b>

1️⃣ Украшен биотоп для новогодней тематики 🎅
2️⃣ Автовыдача ежедневной премии теперь работает как положено 🎁
3️⃣ Команда "кусь" исправлена.

❄️ <b>Текущие особенности:</b>
• Добавлено новое визуальное новогоднее оформление.

<i>Последнее обновление: 27.12.2024</i>
"""
    await message.reply(changelog, parse_mode="HTML")

@dp.message_handler(lambda message: message.text.lower().startswith('/set'))
async def set_user_attributes(message: types.Message):
    if message.from_user.id not in [6832369115, 1291390143]:
        return
    
    attribute_mapping = {
    'be': 'bio_experience',
    'br': 'bio_resources',
    'skill': 'skill_level',
    'inf': 'contagion',
    'imn': 'immunity',
    'virus': 'virus_skill',
    'p': 'pathogens',
    'mp': 'max_pathogens',
    'q': 'qualification',
    'm': 'lethality'
    }

    try:
        # Разбираем сообщение
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            raise ValueError("Недостаточно аргументов.")
        
        user_id = int(parts[1])  # ID пользователя
        updates = parts[2]       # Строка с обновлениями, например: "be 100, br 200"

        # Проверяем, существует ли пользователь с указанным ID
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        if not cursor.fetchone():
            await message.reply("❌ Пользователь с указанным ID не найден.")
            return

        # Разбираем обновления
        update_pairs = updates.split(',')
        for pair in update_pairs:
            short_attr, value = pair.strip().split()
            if short_attr not in attribute_mapping:
                await message.reply(f"❌ Недопустимый атрибут: {short_attr}. Допустимые: {', '.join(attribute_mapping.keys())}")
                return
            
            attribute = attribute_mapping[short_attr]
            value = int(value)  # Преобразуем значение в целое число

            # Обновляем значение атрибута
            cursor.execute(f'UPDATE users SET {attribute} = ? WHERE user_id = ?', (value, user_id))
        
        conn.commit()

        await message.reply(
            f"✅ Успешно обновлены атрибуты для пользователя с ID {user_id}:\n",
            parse_mode="HTML"
        )
    except ValueError as ve:
        await message.reply(f"❌ Некорректный формат команды: {ve}. Используйте: /set <айди> <атрибут> <значение>, <атрибут> <значение>, ...")
    except Exception as e:
        await message.reply(f"❌ Произошла ошибка: {e}")

@dp.message_handler(lambda message: message.text.lower() == "/help")
async def help_command(message: types.Message):
    if message.from_user.id not in [6832369115, 1291390143]:
        return
        
        help_text = """
🛠️ <b>Помощь по админ командам:</b>

<b>Команда /set (id) (параметр) (значение):</b>
└ Доступные параметры:
 • <code>be</code> - био:опыт
 • <code>br</code> - био-ресурсы
 • <code>skill</code> - навык
 • <code>inf</code> - заразность
 • <code>imn</code> - иммунитет
 • <code>virus</code> - вирус
 • <code>m</code> - летальность
 • <code>q</code> - квалификация
 • <code>p</code> - патоген
 • <code>mp</code> - максимум патогенов
└ Пример: <code>/set 123456789 be 100</code>
<b>Команда /i:</b>
└ Доступные параметры:
• <code>/i</code> - выбранная информация пользователя
Доступные параметры:
 • <code>be</code> - био-опыт
 • <code>br</code> - био-ресурсы
 • <code>skill</code> - навык
 • <code>inf</code> - заразность
 • <code>imn</code> - иммунитет
 • <code>virus</code> - вирус
 • <code>m</code> - летальность
 • <code>q</code> - квалификация
 • <code>p</code> - патоген
 • <code>mp</code> - максимум патогенов
 └ Пример: <code>/i 123456789 be, br</code>
<b>Другие команды:</b>
• <code>кас</code> (id) (time) - выдает бан
└ Пример: <code>кас 123456789 1d причина</code>

• <code>/reset</code> (id) - сброс навыков
• <code>/bioexp</code> - суммарный опыт игры
• <code>/лист</code> - даты регистрации
• <code>/rlab</code> - сброс имени лаборатории
• <code>/rpat</code> - сброс имени патогена

<b>Информационные команды:</b>
• <code>/lab</code> (reply/id) - полная информация
• <code>/info</code> - краткая информация
• <code>/i</code> - случайная информация
• <code>/паты</code> - список патогенов

<i>Обновлено: 24.12.2024</i>
"""
    await message.reply(help_text, parse_mode="HTML")

@dp.message_handler(lambda message: message.text.startswith("/lab"))
async def lab_full_report(message: types.Message):
    if message.from_user.id not in [6832369115]:
        return

    try:
        # Если команда вызвана реплаем
        if message.reply_to_message:
            target_user = message.reply_to_message.from_user
            target_id = target_user.id
            if target_user.is_bot:
                await message.reply("❌ Невозможно получить информацию о боте.")
                return
        else:
            # Если команда вызвана с ID в тексте
            parts = message.text.split()
            if len(parts) < 2 or not parts[1].isdigit():
                await message.reply("❌ Укажите корректный ID пользователя или используйте команду как реплай.")
                return
            target_id = int(parts[1])

        # Получение данных пользователя
        cursor.execute('''
            SELECT username, bio_experience, bio_resources, skill_level, contagion, immunity, 
                   virus_skill, lethality, qualification, pathogens, max_pathogens, pathogen_name, 
                   lab_name, registration_date
            FROM users WHERE user_id = ?
        ''', (target_id,))
        user_data = cursor.fetchone()

        if not user_data:
            await message.reply("❌ Пользователь с таким ID не найден.")
            return

        (username, bio_experience, bio_resources, skill_level, contagion, immunity, virus_skill, 
         lethality, qualification, pathogens, max_pathogens, pathogen_name, lab_name, registration_date) = user_data

        # Получение статистики заражений
        cursor.execute('SELECT COUNT(*) FROM infected WHERE user_id = ?', (target_id,))
        total_victims = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM fallen_victims WHERE user_id = ?', (target_id,))
        total_fallen_victims = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM infections WHERE attacker_id = ?', (target_id,))
        total_infections = cursor.fetchone()[0]

        # Формирование отчета
        lab_report = f"""
🔬 <i>Полный отчет лаборатории пользователя:</i> <b>{username or 'Без имени'}</b>
<b>[Общие данные]</b><blockquote>
📅 <b>Дата регистрации:</b> {registration_date}
☣️ <b>Патоген:</b> {pathogen_name or 'Не указан'}
🏢 <b>Лаборатория:</b> {lab_name or 'Не указана'}</blockquote>

<b>[Характеристики]</b><blockquote>
🎚️ <b>Уровень навыков:</b> {skill_level}
🦠 <b>Заразность:</b> {contagion}
🛡️ <b>Иммунитет:</b> {immunity}
🧪 <b>Уровень вируса:</b> {virus_skill}
☠️ <b>Летальность:</b> {lethality}
🛠️ <b>Квалификация:</b> {qualification}</blockquote>

<b>[Ресурсы]</b>
<blockquote>🧬 <b>Био ресурсы:</b> {bio_resources}
🎖️ <b>Био опыт:</b> {bio_experience}
🦠 <b>Патогены:</b> {pathogens}/{max_pathogens}</blockquote>

<b>[Заражения]</b>
<blockquote>🔗 <b>Всего заражений:</b> {total_infections}
🦠 <b>Всего жертв:</b> {total_victims}
💀 <b>Слетевшие жертвы:</b> {total_fallen_victims}</blockquote>
"""
        await message.reply(lab_report, parse_mode="HTML")

    except Exception as e:
        print(e)
        await message.reply("❌ Произошла ошибка при выполнении команды.")


@dp.message_handler(lambda message: message.text.startswith("/info"))
async def user_info(message: types.Message):
    if message.from_user.id not in [6832369115]:
        return

    try:
        # Если команда вызвана реплаем
        if message.reply_to_message:
            target_user = message.reply_to_message.from_user
            target_id = target_user.id
            if target_user.is_bot:
                await message.reply("❌ Невозможно получить информацию о боте.", parse_mode="HTML")
                return
            target_nickname = target_user.first_name  # Никнейм целевого пользователя
        else:
            # Если команда вызвана с ID в тексте
            parts = message.text.split()
            if len(parts) < 2 or not parts[1].isdigit():
                await message.reply("❌ Укажите корректный ID пользователя или используйте команду как реплай.", parse_mode="HTML")
                return
            target_id = int(parts[1])

            # Получаем пользователя по ID
            cursor.execute('SELECT first_name FROM users WHERE user_id = ?', (target_id,))
            user_data = cursor.fetchone()

            if not user_data:
                await message.reply("❌ Пользователь с таким ID не найден.", parse_mode="HTML")
                return

            target_nickname = user_data[0]  # Никнейм целевого пользователя

        # Получение данных пользователя
        cursor.execute('''
            SELECT username, registration_date, pathogen_name, lab_name 
            FROM users WHERE user_id = ?
        ''', (target_id,))
        user_data = cursor.fetchone()

        if not user_data:
            await message.reply("❌ Пользователь с таким ID не найден.", parse_mode="HTML")
            return

        username, registration_date, pathogen_name, lab_name = user_data

        # Формирование отчета
        info_message = f"""
🔍 <i>Информация о пользователе:</i>

<b>📛 Никнейм:</b> {target_nickname}
<b>🆔 ID:</b> {target_id}
<b>👤 Юзернейм:</b> {username or 'Не указан'}
<b>📅 Дата регистрации:</b> {registration_date}
<b>☣️ Название патогена:</b> {pathogen_name or 'Не указано'}
<b>🏢 Название лаборатории:</b> {lab_name or 'Не указано'}
"""
        await message.reply(info_message, parse_mode="HTML")

    except Exception as e:
        print(e)
        await message.reply("❌ Произошла ошибка при выполнении команды.", parse_mode="HTML")

@dp.message_handler(lambda message: message.text.startswith("/i"))
async def user_skill_info(message: types.Message):
    if message.from_user.id not in [6832369115]:
        return
    
    args = message.text.split()

    if len(args) < 3:
        await message.reply("❌ Используйте формат: /i <ID или реплай> <навык>", parse_mode="HTML")
        return

    # Извлечение ID пользователя и названия навыка
    target = args[1]
    skill_name = args[2].lower()

    # Проверка корректности названия навыка
    valid_skills = [
        "be", "bio_experience", "br", "bio_resources", "skill", "skill_level", "inf", "contagion",
        "imn", "immunity", "virus", "virus_skill", "m", "lethality", "q", "qualification", "p", "pathogens",
        "mp", "max_pathogens", "pn", "pathogen_name", "ln", "lab_name"
    ]

    if skill_name not in valid_skills:
        await message.reply("❌ Неверное название навыка. Доступные навыки: " + ", ".join(valid_skills), parse_mode="HTML")
        return

    # Получение ID пользователя (если команда вызвана реплаем или с ID)
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_id = target_user.id
    elif target.isdigit():
        target_id = int(target)
    else:
        await message.reply("❌ Укажите корректный ID пользователя или используйте команду как реплай.", parse_mode="HTML")
        return

    # Получение данных пользователя по ID
    cursor.execute('''
        SELECT bio_experience, bio_resources, skill_level, contagion, immunity, virus_skill,
               lethality, qualification, pathogens, max_pathogens, pathogen_name, lab_name
        FROM users WHERE user_id = ?
    ''', (target_id,))
    user_data = cursor.fetchone()

    if not user_data:
        await message.reply("❌ Пользователь с таким ID не найден.", parse_mode="HTML")
        return

    # Сопоставление навыков с полями в базе данных
    skill_mapping = {
        "be": 0, "bio_experience": 0, "br": 1, "bio_resources": 1, "s": 2, "skill_level": 2,
        "inf": 3, "contagion": 3, "imn": 4, "immunity": 4, "virus": 5, "virus_skill": 5, "letal": 6,
        "lethality": 6, "q": 7, "qualification": 7, "p": 8, "pathogens": 8, "mp": 9,
        "max_pathogens": 9, "pn": 10, "pathogen_name": 10, "ln": 11, "lab_name": 11
    }

    skill_index = skill_mapping.get(skill_name)

    if skill_index is None:
        await message.reply("❌ Навык не найден.", parse_mode="HTML")
        return

    skill_value = user_data[skill_index]

    # Формирование сообщения
    await message.reply(f"🔍 <b>Навык</b>: <i>{skill_name}</i>\n<b>Значение:</b> {skill_value}", parse_mode="HTML")

@dp.message_handler(lambda message: message.text.lower().startswith("чек"))
async def check_user(message: types.Message):
    cursor.execute('SELECT user_id, is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        await message.reply("❌ Вы не зарегистрированы в боте. Используйте /start для регистрации.", parse_mode="HTML")
        return
        
    if user_data[1] == 1:
        return
        
    current_time = datetime.utcnow()
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ Укажите ID, ссылку, или @username для проверки.", parse_mode="HTML")
        return

    target = args[1]

    def get_user_id(target):
        if target.startswith('https://t.me/'):
            return target.split('/')[-1]
        if target.startswith('@'):
            return target[1:]
        if target.isdigit():
            return int(target)
        return None

    target_user = get_user_id(target)

    if not target_user:
        await message.reply("❌ Некорректный формат. Укажите правильный ID, ссылку или юзернейм.", parse_mode="HTML")
        return

    # Получаем информацию о пользователе
    if isinstance(target_user, int):
        cursor.execute('SELECT user_id, username, bio_experience FROM users WHERE user_id = ?', (target_user,))
    else:
        cursor.execute('SELECT user_id, username, bio_experience FROM users WHERE username = ?', (target_user,))
    
    user = cursor.fetchone()
    if not user:
        await message.reply("❌ Пользователь не найден.", parse_mode="HTML")
        return

    user_id, username, current_bio_exp = user

    # Получаем информацию о последнем заражении
    cursor.execute('''
        SELECT victim_experience, infect_end_date
        FROM infected
        WHERE victim_id = ?
        ORDER BY infect_date DESC
        LIMIT 1
    ''', (user_id,))
    infection_info = cursor.fetchone()

    if infection_info:
        last_infection_exp, infect_end_date = infection_info
        
        current_infection_exp = max(1, int(current_bio_exp * 0.1))
        total_exp = last_infection_exp + current_infection_exp

        if infect_end_date:
            infect_end_time = datetime.strptime(infect_end_date, '%Y-%m-%d %H:%M:%S')
            
            if infect_end_time > current_time:
                response = (f"🍊 <a href='tg://openmessage?user_id={user_id}'>{username}</a> "
                          f"приносит {current_infection_exp:,} опыта\n"
                          f"заражение до: {infect_end_date}")
                
                await message.reply(response, parse_mode="HTML")
            else:
                await message.reply("❌ Заражение пользователя завершено.", parse_mode="HTML")
        else:
            await message.reply("❌ Не удалось найти дату окончания заражения.", parse_mode="HTML")
    else:
        current_infection_exp = max(1, int(current_bio_exp * 0.1))
        await message.reply(
            f"🍊 <a href='tg://openmessage?user_id={user_id}'>{username}</a> приносит {current_infection_exp:,} опыта",
            parse_mode="HTML"
        )

@dp.message_handler(lambda message: message.text.lower() == "/паты")
async def show_recent_pathogens(message: types.Message):
    if message.from_user.id not in [6832369115]:
    	return
    cursor.execute('SELECT user_id, is_banned FROM users WHERE user_id = ?', (message.from_user.id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        await message.reply("❌ Вы не зарегистрированы в боте. Используйте /start для регистрации.", parse_mode="HTML")
        return
        
    if user_data[1] == 1:
        await message.reply("❌ Вы заблокированы и не можете использовать эту команду.", parse_mode="HTML")
        return

    try:
        # Извлекаем пользователей с патогенами, которые не равны "котячка"
        cursor.execute('''
            SELECT u.user_id, u.pathogen_name, u.username 
            FROM users u
            WHERE u.pathogen_name IS NOT NULL 
            AND u.pathogen_name != "котячка"
            ORDER BY u.user_id DESC
            LIMIT 50
        ''')
        pathogens = cursor.fetchall()

        # Если нет установленных патогенов
        if not pathogens:
            await message.answer("📝 Нет установленных патогенов", parse_mode="HTML")
            return

        # Формируем ответ с патогенами
        response = "🧬 <b>Установленные патогены:</b>\n\n"
        for user_id, pathogen_name, username in pathogens:
            user_link = f"@{username}" if username else f'<a href="tg://openmessage?user_id={user_id}">{user_id}</a>'
            response += f"{user_link} - {pathogen_name}\n"

        await message.answer(response, parse_mode="HTML")

    except Exception as e:
        print(f"Error in show_recent_pathogens: {e}")
        await message.answer("❌ Произошла ошибка при выполнении команды.", parse_mode="HTML")

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
