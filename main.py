import sqlite3
import os
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Инициализация базы данных
DATABASE = 'survey.db'


def init_db():
    """Инициализация базы данных"""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        # Таблица с колонкой для JSON с ответами
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                answers TEXT
            )
        ''')
        conn.commit()


# Инициализация базы данных при первом запуске
if not os.path.exists(DATABASE):
    init_db()

# JSON-схема для анкеты (пример)
json_schema = [
    {"name": "Имя", "type": "text", "ogr": "required"},
    {"name": "Возраст", "type": "number", "ogr": "min=0"},
    {"name": "Email", "type": "email", "ogr": "required"},
    {"name": "Город", "type": "text", "ogr": "optional"},
    {"name": "Профессия", "type": "text", "ogr": "optional"}
]

# Глобальные переменные для хранения состояния анкеты
user_data = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Стартовая команда /start, начинающая анкету"""
    user_data[update.message.chat_id] = {"step": 0, "responses": {}}
    await ask_question(update, context)


async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Задает следующий вопрос пользователю в зависимости от текущего шага"""
    chat_id = update.message.chat_id
    user_info = user_data.get(chat_id)
    step = user_info.get("step")

    if step < len(json_schema):
        question = json_schema[step]["name"]
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
    field_name = json_schema[step]["name"]
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

    # Сохранение JSON в SQLite
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO responses (answers)
            VALUES (?)
        ''', (json_responses,))
        conn.commit()

    # Отправляем сообщение пользователю
    await update.message.reply_text("Спасибо за заполнение анкеты!")
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
