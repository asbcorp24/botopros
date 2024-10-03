import sqlite3
import os
import json
import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Инициализация базы данных
DATABASE = 'survey.db'


def init_db():
    """Инициализация базы данных"""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        # Таблица с колонками для JSON-ответов и времени заполнения
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                answers TEXT,
                timestamp TEXT
            )
        ''')
        conn.commit()


# Инициализация базы данных при первом запуске
if not os.path.exists(DATABASE):
    init_db()

# JSON-схема для анкеты с интервалом (пример)
json_schema = {
    "form": [
        {"name": "Имя", "type": "text", "ogr": "required"},
        {"name": "Возраст", "type": "number", "ogr": "min=0"},
        {"name": "Email", "type": "email", "ogr": "required"},
        {"name": "Город", "type": "text", "ogr": "optional"},
        {"name": "Профессия", "type": "text", "ogr": "optional"}
    ],
    "interval": 48  # Количество часов между заполнениями анкеты
}

# Глобальные переменные для хранения состояния анкеты
user_data = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Стартовая команда /start, начинающая анкету"""
    chat_id = update.message.chat_id

    # Проверяем, заполнял ли пользователь анкету в течение времени, указанного в json_schema["interval"]
    interval_hours = json_schema.get("interval", 24)  # по умолчанию 24 часа, если поле отсутствует
    if not can_fill_survey(chat_id, interval_hours):
        await update.message.reply_text(
            f"Вы уже заполнили анкету. Повторное заполнение возможно через {interval_hours} часов.")
        return

    user_data[chat_id] = {"step": 0, "responses": {}}
    await ask_question(update, context)


def can_fill_survey(chat_id, interval_hours):
    """Проверка, может ли пользователь заполнить анкету (в зависимости от интервала)"""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT timestamp FROM responses WHERE chat_id = ? ORDER BY timestamp DESC LIMIT 1
        ''', (chat_id,))
        result = cursor.fetchone()

        if result:
            last_filled = datetime.datetime.fromisoformat(result[0])
            now = datetime.datetime.now()

            # Проверяем, прошло ли указанное количество часов
            if (now - last_filled).total_seconds() < interval_hours * 3600:
                return False

    return True


async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Задает следующий вопрос пользователю в зависимости от текущего шага"""
    chat_id = update.message.chat_id
    user_info = user_data.get(chat_id)
    step = user_info.get("step")

    if step < len(json_schema["form"]):
        question = json_schema["form"][step]["name"]
        await update.message.reply_text(f"Пожалуйста, введите {question}:")
    else:
        # Если все вопросы заданы, сохранить данные
        await save_data(update, context)


async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка ответов пользователя и переход к следующему вопросу"""
    chat_id = update.message.chat_id
    user_info = user_data.get(chat_id)
    step = user_info.get("step")

    # Сохраняем ответ
    field_name = json_schema["form"][step]["name"]
    user_info["responses"][field_name] = update.message.text

    # Переход к следующему вопросу
    user_info["step"] += 1
    user_data[chat_id] = user_info

    await ask_question(update, context)


async def save_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сохраняет собранные данные в виде JSON в базу данных SQLite"""
    chat_id = update.message.chat_id
    responses = user_data[chat_id]["responses"]

    # Преобразование словаря с ответами в JSON-строку
    json_responses = json.dumps(responses, ensure_ascii=False)
    timestamp = datetime.datetime.now().isoformat()

    # Сохранение JSON и времени в SQLite
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO responses (chat_id, answers, timestamp)
            VALUES (?, ?, ?)
        ''', (chat_id, json_responses, timestamp))
        conn.commit()

    # Отправляем сообщение пользователю
    await update.message.reply_text(
        "Спасибо за заполнение анкеты! Вы сможете заполнить её снова через указанное время.")
    del user_data[chat_id]  # Очищаем данные после завершения


def main():
    """Запуск Telegram-бота"""
    application = Application.builder().token('7034463952:AAF20wTujVISRpUO0m4rAvsDBbF2TVwQj9Q').build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))

    # Обработчик для ответов
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_response))

    # Запуск бота
    application.run_polling()


if __name__ == '__main__':
    main()
