from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from admin import admin_login, handle_admin_credentials
from survey import start, button_handler, download_surveys, handle_response,add_survey
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
# Для каждого пользователя создается состояние, чтобы определить, что именно нужно обрабатывать
from state import user_state  # Импортируем user_state
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

    # Проверка состояния пользователя
    if user_state.get(chat_id) == 'admin_login':
        # Если пользователь вводит логин и пароль
        await handle_admin_credentials(update, context)

    else:
        # Иначе считаем, что это ответы на анкету
        await handle_response(update, context)


async def admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запуск процесса логина администратора"""
    chat_id = update.message.chat_id
    user_state[chat_id] = 'admin_login'
    await update.message.reply_text("Введите логин:")



def check_login(text: str) -> bool:
    """Проверка логина и пароля (простая реализация)"""
    # Здесь должна быть логика проверки логина
    return text == "admin"


def main():
    json_schema = load_json_schema()

    """Запуск бота."""
    application = Application.builder().token('7034463952:AAF20wTujVISRpUO0m4rAvsDBbF2TVwQj9Q').build()

    # Обработка команды /start
    application.add_handler(CommandHandler('start', start))

    # Обработка текстовых сообщений (для ввода логина и пароля администратора)
  #  application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_credentials))

    # Обработка нажатий кнопок в меню
    application.add_handler(CallbackQueryHandler(button_handler))

    # Обработка ответов на анкеты
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Запуск бота
    application.run_polling()


if __name__ == '__main__':
    main()
