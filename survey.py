import sqlite3
import os
import json
import datetime
import csv
from io import StringIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from admin import admin_login  # Импорт функции администрирования
from state import user_state  # Импортируем user_state
DATABASE = 'survey.db'
json_schema = None  # Глобальная переменная для схемы

def init_db():
    """Инициализация базы данных"""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                survey_name TEXT,
                answers TEXT,
                timestamp TEXT
            )
        ''')
        conn.commit()


if not os.path.exists(DATABASE):
    init_db()

# Пример JSON схемы анкеты с несколькими анкетами
# json_schema = {
#     "surveys": [
#         {
#             "name": "Анкета 1",
#             "form": [
#                 {"name": "Имя", "type": "text", "ogr": "required"},
#                 {"name": "Возраст", "type": "number", "ogr": "min=0"},
#                 {"name": "Email", "type": "email", "ogr": "required"},
#             ],
#             "interval": 48  # Интервал между заполнениями анкеты в часах
#         },
#         {
#             "name": "Анкета 2",
#             "form": [
#                 {"name": "Город", "type": "text", "ogr": "optional"},
#                 {"name": "Профессия", "type": "text", "ogr": "optional"}
#             ],
#             "interval": 24
#         }
#     ]
# }

user_data = {}

def load_json_schema():
    global json_schema
    with open('survey_schema.json', 'r', encoding='utf-8') as f:
        json_schema = json.load(f)

# Загрузка json_schema при запуске программы
load_json_schema()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    """Стартовая команда /start, открывает меню выбора"""
    keyboard = [
        [InlineKeyboardButton("Администрирование", callback_data='admin')],
        [InlineKeyboardButton("Заполнить анкету", callback_data='fill_survey')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка нажатий кнопок в меню"""
    query = update.callback_query
    await query.answer()
    if query.data.startswith('download_'):
        survey_name = query.data[len('download_'):]  # Извлекаем название анкеты
        await download_survey_csv(update, context, survey_name)  # Переходим к скачиванию
    print( query.data )
    if query.data == 'download_surveys':
        #await download_surveys(update, context)
        await show_available_surveys(update)  # Показываем список анкет
    if query.data == 'add_survey':
        await add_survey(update, context,query.message.chat_id)
    elif query.data == 'admin':
        # Запрашиваем логин и пароль администратора
        await admin_login(update, context)
    elif query.data in ['yes','no']:
        await handle_more_questions_button(update, context)
    elif query.data == 'fill_survey':
        await show_survey_selection(update)
    elif query.data == 'logout':
        chat_id = query.message.chat_id
        user_state[chat_id] = None  # Сбрасываем состояние администратора
        await update.callback_query.message.reply_text("Вы вышли из администрирования.")
        await start(update, context)  # Возвращаем в главное меню
    else :
        await start_survey(update,query.data)



async def show_survey_selection(update: Update) -> None:

    """Показывает список доступных анкет"""
    keyboard = [
        [InlineKeyboardButton(survey['name'], callback_data=f'{survey["name"]}')]
        for survey in json_schema["surveys"]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text("Выберите анкету для заполнения:", reply_markup=reply_markup)


async def start_survey(update: Update, survey_name: str) -> None:
    """Начинает процесс заполнения выбранной анкеты"""
    chat_id = update.callback_query.message.chat_id
  #  survey_name= survey_name.replace("fill_", "")
    # Получаем выбранную анкету
    selected_survey = next((s for s in json_schema["surveys"] if s["name"] == survey_name), None)

    if not selected_survey:
     #   await update.callback_query.message.reply_text("Анкета не найдена.")
        return

    interval_hours = selected_survey.get("interval", 24)
    remaining_time = get_remaining_time(chat_id, survey_name, interval_hours)

    if remaining_time:
        await update.callback_query.message.reply_text(
            f"Вы уже заполнили анкету. Повторное заполнение возможно через {remaining_time}.")
        return

    user_data[chat_id] = {"step": 0, "responses": {}, "survey": selected_survey}
    await ask_question(update.callback_query.message, chat_id)


async def ask_question(message, chat_id: int) -> None:
    """Задает следующий вопрос пользователю в зависимости от текущего шага"""
    user_info = user_data.get(chat_id)
    survey = user_info["survey"]
    step = user_info.get("step")

    if step < len(survey["form"]):
        question = survey["form"][step]["name"]
        await message.reply_text(question)
    else:
        await save_survey_response(chat_id, survey["name"], user_info["responses"])
        await message.reply_text("Спасибо за заполнение анкеты!")


async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE, user_state: dict) -> None:
    """Обработка ответов на вопросы анкеты"""
    chat_id = update.message.chat_id
    user_info = user_data.get(chat_id)

    if not user_info:
        return

    step = user_info.get("step")
    survey = user_info["survey"]
    if step < len(survey["form"]):
        question = survey["form"][step]
        user_info["responses"][question["name"]] = update.message.text
        user_info["step"] += 1
        await ask_question(update.message, chat_id)


async  def save_survey_response(chat_id, survey_name, responses):
    """Сохраняет ответы на анкету в базу данных"""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        response_data = json.dumps(responses, ensure_ascii=False)
        cursor.execute('''
            INSERT INTO responses (chat_id, survey_name, answers, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (chat_id, survey_name, response_data, timestamp))
        conn.commit()
async def download_surveys(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Скачивание анкет в формате CSV"""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT survey_name, answers, timestamp FROM responses')
        rows = cursor.fetchall()

        # Создаем CSV-файл в памяти
        output = StringIO()
        header = ['Timestamp', 'Survey Name']  # Начинаем с временной метки и названия анкеты
        csv_writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

        # Получаем уникальные ключи из всех ответов
        all_keys = set()
        for row in rows:
            answers = json.loads(row[1])  # Обратите внимание, что answers находится во втором индексе
            all_keys.update(answers.keys())
        header.extend(all_keys)
        csv_writer.writerow(header)

        for row in rows:
            answers = json.loads(row[1])
            csv_row = [row[2], row[0]]  # Временная метка и название анкеты
            csv_row.extend([answers.get(key, '') for key in all_keys])
            csv_writer.writerow(csv_row)

        output.seek(0)

        await update.callback_query.message.reply_document(
            document=output.getvalue().encode('windows-1251'),
            filename='surveys.csv'
        )
        await update.callback_query.answer("Анкеты загружены.")

def get_remaining_time(chat_id, survey_name, interval_hours):
    """Проверяет время последнего заполнения анкеты и возвращает оставшееся время до следующего возможного заполнения"""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT timestamp FROM responses
            WHERE chat_id = ? AND survey_name = ?
            ORDER BY timestamp DESC LIMIT 1
        ''', (chat_id, survey_name))
        last_submission = cursor.fetchone()

        if last_submission:
            last_time = datetime.datetime.fromisoformat(last_submission[0])
            next_allowed_time = last_time + datetime.timedelta(hours=interval_hours)
            remaining_time = next_allowed_time - datetime.datetime.now()

            if remaining_time > datetime.timedelta(0):
                hours, remainder = divmod(remaining_time.seconds, 3600)
                minutes = remainder // 60
                return f"{hours} час(ов) и {minutes} минут(ы)"
    return None


async def handle_more_questions_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатие кнопок 'Да' или 'Нет' для добавления дополнительных вопросов."""
    query = update.callback_query
    await query.answer()  # Закрываем уведомление с кнопками

    if query.data == 'yes':
        await query.edit_message_text("Введите следующий вопрос:")
        context.user_data['waiting_for_question'] = True
    else:
        # Заканчиваем добавление анкеты и сохраняем её
        await save_new_survey(context.user_data['new_survey'])
        await query.edit_message_text(f"Анкета '{context.user_data['new_survey']['name']}' добавлена!")
        context.user_data.pop('adding_survey', None)
        context.user_data.pop('new_survey', None)
        # Запускаем команду /start
        load_json_schema()
        await start(update, context)
async def add_survey(update: Update, context: ContextTypes.DEFAULT_TYPE,chat_id) -> None:
    """Начало процесса добавления новой анкеты"""
    await update.callback_query.message.reply_text("Введите имя новой анкеты:")
    context.user_data['adding_survey'] = True  # Флаг начала процесса добавления анкеты
    context.user_data['new_survey'] = {}  # Храним временные данные новой анкеты
    context.user_data['new_survey']['form'] = []  # Список вопросов новой анкеты
    user_state[chat_id] = "start_surv";
async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка ввода администратора для добавления новой анкеты"""
    if context.user_data.get('adding_survey'):
        if 'name' not in context.user_data['new_survey']:
            # Сохраняем имя анкеты
            context.user_data['new_survey']['name'] = update.message.text
            await update.message.reply_text("Введите первый вопрос для анкеты:")
            context.user_data['waiting_for_question'] = True
        elif context.user_data.get('waiting_for_question'):
            # Добавляем новый вопрос
            question_text = update.message.text
            context.user_data['new_question'] = {"name": question_text, "type": "text", "ogr": "optional"}  # Устанавливаем значения по умолчанию
            context.user_data['new_survey']['form'].append(context.user_data['new_question'])
            context.user_data.pop('new_question', None)

            # Показываем кнопки для добавления ещё одного вопроса
            keyboard = [
                [InlineKeyboardButton("Да", callback_data='yes')],
                [InlineKeyboardButton("Нет", callback_data='no')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Добавить еще один вопрос?", reply_markup=reply_markup)
            context.user_data['waiting_for_more_questions'] = True
            context.user_data.pop('waiting_for_question', None)


async def save_new_survey(survey: dict) -> None:
    """Сохраняет новую анкету в JSON-файл"""
    with open('survey_schema.json', 'r+', encoding='utf-8') as f:
        schema = json.load(f)
        schema['surveys'].append(survey)  # Добавляем новую анкету
        f.seek(0)  # Возвращаемся в начало файла
        json.dump(schema, f, ensure_ascii=False, indent=4)  # Сохраняем обновленный JSON
        f.truncate()  # Удаляем старое содержимое, которое осталось после записи
async def show_available_surveys(update: Update) -> None:
    """Показывает список доступных анкет для скачивания."""
    keyboard = [
        [InlineKeyboardButton(survey['name'], callback_data=f'download_{survey["name"]}')]
        for survey in json_schema["surveys"]
    ]
    keyboard.append([InlineKeyboardButton("Отмена", callback_data='cancel_download')])  # Кнопка отмены
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text("Выберите анкету для скачивания:", reply_markup=reply_markup)
async def download_survey_csv(update: Update, context: ContextTypes.DEFAULT_TYPE, survey_name: str) -> None:
    """Скачивание выбранной анкеты в формате CSV."""
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT answers, timestamp FROM responses WHERE survey_name = ?', (survey_name,))
        rows = cursor.fetchall()

        if not rows:
            await update.callback_query.message.reply_text("Нет ответов для данной анкеты.")
            return

        # Создаем CSV-файл в памяти
        output = StringIO()
        header = ['Timestamp', 'Answers']  # Заголовки (можно изменить по необходимости)
        csv_writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow(header)

        for row in rows:
            answers = json.loads(row[0])
            csv_row = [row[1], answers]  # Временная метка и ответы
            csv_writer.writerow(csv_row)

        output.seek(0)

        await update.callback_query.message.reply_document(
            document=output.getvalue().encode('windows-1251'),
            filename=f'{survey_name}.csv'
        )
        await update.callback_query.answer("Анкета загружена.")