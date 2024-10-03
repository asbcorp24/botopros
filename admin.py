import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from state import user_state  # Импортируем user_state

# Загрузка данных администратора из JSON-файла
def load_admin_credentials():
    with open('admin_credentials.json', 'r') as file:
        return json.load(file)


admin_credentials = load_admin_credentials()
current_admin_step = {}  # Хранит текущий шаг аутентификации для каждого пользователя


async def admin_login(update, context):
    """Запрашивает у пользователя ввод логина и пароля для администрирования."""
    chat_id = update.message.chat_id if update.message else update.callback_query.message.chat_id
    current_admin_step[chat_id] = {"step": "login"}
    user_state[chat_id] = 'admin_login'
    # Отправляем запрос на ввод логина
    if update.message:
        await update.message.reply_text("Введите логин:")
    elif update.callback_query:
        await update.callback_query.message.reply_text("Введите логин:")


async def handle_admin_credentials(update, context):
    """Обрабатывает ввод логина и пароля администратора."""
    chat_id = update.message.chat_id
    text = update.message.text

    # Проверяем текущий шаг аутентификации
    if chat_id in current_admin_step:
        step = current_admin_step[chat_id]["step"]

        if step == "login":
            # Проверяем логин
            if text == admin_credentials["login"]:
                current_admin_step[chat_id]["step"] = "password"
                await update.message.reply_text("Введите пароль:")
            else:
                await update.message.reply_text("Неверный логин. Попробуйте снова.")

        elif step == "password":
            # Проверяем пароль
            if text == admin_credentials["password"]:
                # Успешная аутентификация
                await update.message.reply_text("Успешный вход!")
                current_admin_step[chat_id]["authenticated"] = True
                del current_admin_step[chat_id]["step"]  # Удаляем шаг после успешного входа
                await show_admin_menu(update, context)
            else:
                await update.message.reply_text("Неверный пароль. Попробуйте снова.")


async def show_admin_menu(update, context):
    """Отображает меню администратора с кнопками."""
    keyboard = [
        [InlineKeyboardButton("Загрузить анкеты", callback_data='download_surveys')],
        [InlineKeyboardButton("Добавить анкету", callback_data='add_survey')],
        [InlineKeyboardButton("Выйти", callback_data='logout')]  # Добавляем кнопку "Выйти"
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text("Выберите действие:", reply_markup=reply_markup)
