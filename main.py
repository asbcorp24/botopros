from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from admin import admin_login, handle_admin_credentials
from survey import start, button_handler, download_surveys, handle_response, add_survey, handle_admin_input, handle_more_questions_button
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from flask import Flask, request  # Импортируем Flask для вебхука
from state import user_state  # Импортируем user_state

app = Flask(__name__)  # Создаем экземпляр Flask

def load_json_schema():
    SCHEMA_FILE = 'survey_schema.json'
    if os.path.exists(SCHEMA_FILE):
        with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        raise FileNotFoundError(f"Файл {SCHEMA_FILE} не найден")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Главный обработчик текстовых сообщений, который переключает между режимами"""
    chat_id = update.message.chat_id
    message_text = update.message.text.lower()

    # Проверка состояния пользователя
    if user_state.get(chat_id) == 'admin_login':
        # Если пользователь вводит логин и пароль
        await handle_admin_credentials(update, context)
    elif user_state.get(chat_id) == 'start_surv':
        await handle_admin_input(update, context)
    else:
        # Иначе считаем, что это ответы на анкету
        await handle_response(update, context, user_state)

def check_login(text: str) -> bool:
    """Проверка логина и пароля (простая реализация)"""
    return text == "admin"

def load_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    json_schema = load_json_schema()
    config = load_config()
    token = config.get("token")
    use_webhook = config.get("use_webhook", False)  # Добавьте это в ваш config.json

    """Запуск бота."""
    application = Application.builder().token(token).build()

    # Обработка команды /start
    application.add_handler(CommandHandler('start', start))

    # Обработка нажатий кнопок в меню
    application.add_handler(CallbackQueryHandler(button_handler))

    # Обработка ответов на анкеты
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    if use_webhook:
        # Запуск вебхука
        @app.route('/webhook', methods=['POST'])
        def webhook():
            update = request.get_json()
            if update:
                application.process_update(update)
            return 'ok', 200

        # Установка вебхука
        application.bot.set_webhook(url=config.get("YOUR_WEBHOOK_URL"))  # Замените на ваш URL
        app.run(host='0.0.0.0', port=8443)  # Запускаем Flask-приложение для вебхука
    else:
        # Запуск пуллинга
        application.run_polling()

if __name__ == '__main__':
    main()
