import sqlite3
import os
import json
import datetime
import time
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



user_data = {}

def load_json_schema():
    global json_schema
    with open('survey_schema.json', 'r', encoding='utf-8') as f:
        json_schema = json.load(f)

# Загрузка json_schema при запуске программы
load_json_schema()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Стартовая команда /start, открывает меню выбора"""

    # Проверяем, поступило ли событие через команду (message) или через нажатие кнопки (callback_query)
    if hasattr(update, 'message') and update.message:
        # Если это команда, используем update.message
        message = update.message
    elif hasattr(update, 'callback_query') and update.callback_query:
        # Если это callback_query (кнопка), используем update.callback_query.message
        message = update.callback_query.message
    else:
        return  # Если нет подходящего объекта, выходим

    # Формируем клавиатуру с кнопками
    keyboard = [
        [InlineKeyboardButton("Администрирование", callback_data='admin')],
        [InlineKeyboardButton("Заполнить анкету", callback_data='fill_survey')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение с клавиатурой
    await message.reply_text("Выберите действие:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка нажатий кнопок в меню"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    if query.data.startswith('download_'):
        survey_name = query.data[len('download_'):]  # Извлекаем название анкеты
        #await handle_date_input(update, context)
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


import datetime


# async def show_survey_selection(update: Update) -> None:
#     """Показывает список доступных анкет, которые можно заполнить на текущий момент"""
#     current_time = datetime.datetime.now()
#
#     keyboard = []
#
#     # Проходим по всем анкетам в json_schema
#     for survey in json_schema["surveys"]:
#         start_time_str = survey.get("start_time", "")
#
#         # Если поле start_time существует и не пусто, проверяем время начала
#         if start_time_str:
#             try:
#                 start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
#                 if current_time < start_time:
#                     # Если текущее время меньше времени начала, пропускаем эту анкету
#                     continue
#             except ValueError:
#                 # Обрабатываем ошибку, если формат времени неверен
#                 await update.callback_query.message.reply_text(f"Ошибка в формате времени для анкеты {survey['name']}.")
#                 continue
#
#         # Добавляем анкету в список, если она доступна для заполнения
#         keyboard.append([InlineKeyboardButton(survey['name'], callback_data=f'{survey["name"]}')])
#
#     if keyboard:
#         reply_markup = InlineKeyboardMarkup(keyboard)
#         await update.callback_query.message.reply_text("Выберите анкету для заполнения:", reply_markup=reply_markup)
#     else:
#         await update.callback_query.message.reply_text("На данный момент нет доступных анкет.")
async def show_survey_selection(update: Update) -> None:
    """Показывает список доступных анкет"""
    keyboard = []
    current_time = datetime.datetime.now()

    for survey in json_schema["surveys"]:
        start_time_str = survey.get("start_time")
        duration_hours = survey.get("duration", 0)  # Получаем продолжительность, если указана

        # Проверяем время начала и окончания
        if start_time_str:
            if len(start_time_str) == 13:
                start_time_str += ':00'  # Добавляем минуты
            start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
            end_time = start_time + datetime.timedelta(hours=duration_hours)

            # Проверка: анкета доступна только если текущее время в пределах начала и конца
            if not (start_time <= current_time <= end_time):
                continue  # Пропускаем эту анкету, если время не подходит

        # Если все проверки пройдены, добавляем анкету в список
        keyboard.append([InlineKeyboardButton(survey['name'], callback_data=f'{survey["name"]}')])

    if keyboard:
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text("Выберите анкету для заполнения:", reply_markup=reply_markup)
    else:
        await update.callback_query.message.reply_text("Нет доступных анкет.")


# async def start_survey(update: Update, survey_name: str) -> None:
#     """Начинает процесс заполнения выбранной анкеты"""
#     chat_id = update.callback_query.message.chat_id
#   #  survey_name= survey_name.replace("fill_", "")
#     # Получаем выбранную анкету
#     selected_survey = next((s for s in json_schema["surveys"] if s["name"] == survey_name), None)
#
#     if not selected_survey:
#      #   await update.callback_query.message.reply_text("Анкета не найдена.")
#         return
#
#     interval_hours = selected_survey.get("interval", 24)
#     remaining_time = get_remaining_time(chat_id, survey_name, interval_hours)
#
#     if remaining_time:
#         await update.callback_query.message.reply_text(
#             f"Вы уже заполнили анкету. Повторное заполнение возможно через {remaining_time}.")
#         return
#
#     user_data[chat_id] = {"step": 0, "responses": {}, "survey": selected_survey}
#     await ask_question(update.callback_query.message, chat_id)
#
import datetime

async def start_survey(update: Update, survey_name: str) -> None:
    """Начинает процесс заполнения выбранной анкеты"""
    chat_id = update.callback_query.message.chat_id
    selected_survey = next((s for s in json_schema["surveys"] if s["name"] == survey_name), None)

    if not selected_survey:
        await update.callback_query.message.reply_text("Анкета не найдена.")
        return

    interval_hours = selected_survey.get("interval", 24)
    remaining_time = get_remaining_time(chat_id, survey_name, interval_hours)

    if remaining_time:
        await update.callback_query.message.reply_text(
            f"Вы уже заполнили анкету. Повторное заполнение возможно через {remaining_time}.")
        return

    # Проверяем, истекло ли время начала
    start_time_str = selected_survey.get("start_time")
    duration_hours = selected_survey.get("duration", 0)

    if start_time_str:
        start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
        current_time = datetime.datetime.now()
        if current_time < start_time:
            await update.callback_query.message.reply_text("Анкета еще недоступна.")
            return

        end_time = start_time + datetime.timedelta(hours=duration_hours)
        if current_time > end_time:
            await update.callback_query.message.reply_text("Время на заполнение анкеты истекло.")
            return

    user_data[chat_id] = {"step": 0, "responses": {}, "survey": selected_survey, "start_time": time.time()}
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
        # Сохраняем ответы и благодарим за заполнение
        await save_survey_response(chat_id, survey["name"], user_info["responses"])
        await message.reply_text("Спасибо за заполнение анкеты!")

        # Возвращаем пользователя в главное меню, вызывая start
        update = Update(  # Создаём новый объект Update для вызова start
            update_id=message.message_id,
            message=message  # Передаём текущее сообщение
        )
        await start(update, None)
# async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE, user_state: dict) -> None:
#     """Обработка ответов на вопросы анкеты"""
#     chat_id = update.message.chat_id
#     user_info = user_data.get(chat_id)
#
#     if not user_info:
#         return
#
#     step = user_info.get("step")
#     survey = user_info["survey"]
#     if step < len(survey["form"]):
#         question = survey["form"][step]
#         user_info["responses"][question["name"]] = update.message.text
#         user_info["step"] += 1
#         await ask_question(update.message, chat_id)
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
        user_response = update.message.text


        # Проверка ограничений (ogr)
        ogr = question.get("ogr", "")
        validation_result, error_message = validate_response(user_response, ogr)

        if not validation_result:
            await update.message.reply_text(error_message)
            return  # Не переходим к следующему вопросу, пока ответ не будет корректным

        # Сохраняем ответ
        user_info["responses"][question["name"]] = user_response
        user_info["step"] += 1
        await ask_question(update.message, chat_id)

def validate_response(response: str, ogr: str) -> tuple:
    """Валидация ответа в соответствии с ограничениями (ogr).
    Возвращает кортеж (bool, str), где bool указывает на успешность валидации,
    а str - сообщение об ошибке в случае неуспеха.
    """
    for constraint in ogr.split(","):
        constraint = constraint.strip()
        if constraint.startswith("max>"):
            max_value = int(constraint.split(">")[1])
            if not response.isdigit() or int(response) > max_value:
                return False, f"Ответ должен быть меньше или равен {max_value}."
        elif constraint.startswith("min<"):
            min_value = int(constraint.split("<")[1])
            if not response.isdigit() or int(response) < min_value:
                return False, f"Ответ должен быть больше или равен {min_value}."
        elif constraint.startswith("mask="):
            mask = constraint.split("=")[1].strip("[]")
            if len(response) != len(mask):
                return False, f"Длина ответа должна быть {len(mask)} символов."
            for r_char, m_char in zip(response, mask):
                if m_char != '?' and r_char != m_char:
                    return False, f"Ответ не соответствует маске {mask}."
        elif constraint.startswith("length="):
            length = int(constraint.split("=")[1])
            if len(response) != length:
                return False, f"Ответ должен содержать ровно {length} символов."

    return True, "Ответ принят."  # Если все проверки пройдены


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
        user_state[query.message.chat_id]=None

        # Запускаем команду /start
        load_json_schema()
        update = Update(  # Создаём новый объект Update для вызова start
            update_id=query.message.message_id,
            message=query.message  # Передаём текущее сообщение
        )
        await start(update, None)
        #await start(update, context)
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
            new_survey_name = update.message.text

            # Проверка на уникальность названия анкеты в json_schema
            for survey in json_schema['surveys']:
                if survey['name'].lower() == new_survey_name.lower():
                    await update.message.reply_text("Анкета с таким названием уже существует. Введите другое название.")
                    return

            # Сохраняем уникальное имя анкеты
            context.user_data['new_survey']['name'] = new_survey_name
            await update.message.reply_text(
                "Введите время начала анкеты в формате YYYY-MM-DD HH:MM (или введите 0, чтобы оставить пустым):")
            context.user_data['waiting_for_start_time'] = True

        elif context.user_data.get('waiting_for_start_time'):
            # Сохраняем время начала анкеты
            start_time_text = update.message.text
            if start_time_text == "0":
                context.user_data['new_survey']['start_time'] = ""  # Оставляем пустым
                await update.message.reply_text("Введите продолжительность анкеты в часах:")
                context.user_data['waiting_for_duration'] = True
                context.user_data.pop('waiting_for_start_time', None)
            else:
                try:
                    # Пробуем преобразовать введенное время в datetime
                    start_time = datetime.datetime.strptime(start_time_text, "%Y-%m-%d %H:%M")
                    context.user_data['new_survey']['start_time'] = start_time.strftime("%Y-%m-%d %H:%M")
                    await update.message.reply_text("Введите продолжительность анкеты в часах:")
                    context.user_data['waiting_for_duration'] = True
                    context.user_data.pop('waiting_for_start_time', None)
                except ValueError:
                    await update.message.reply_text(
                        "Некорректный формат времени. Попробуйте еще раз в формате YYYY-MM-DD HH:MM или введите 0.")

        elif context.user_data.get('waiting_for_duration'):
            # Сохраняем продолжительность анкеты
            try:
                duration = int(update.message.text)  # Преобразуем введенное значение в целое число
                context.user_data['new_survey']['duration'] = duration
                await update.message.reply_text("Введите интервал между повторным заполнением анкеты в часах:")
                context.user_data['waiting_for_interval'] = True
                context.user_data.pop('waiting_for_duration', None)
            except ValueError:
                await update.message.reply_text("Некорректное значение. Пожалуйста, введите продолжительность в часах.")

        elif context.user_data.get('waiting_for_interval'):
            # Сохраняем интервал между повторными заполнениями анкеты
            try:
                interval = int(update.message.text)  # Преобразуем введенное значение в целое число
                context.user_data['new_survey']['interval'] = interval
                context.user_data['new_survey']['form'] = []  # Инициализируем форму для вопросов анкеты
                await update.message.reply_text("Введите первый вопрос для анкеты:")
                context.user_data['waiting_for_question'] = True
                context.user_data.pop('waiting_for_interval', None)
            except ValueError:
                await update.message.reply_text("Некорректное значение. Пожалуйста, введите интервал в часах.")

        elif context.user_data.get('waiting_for_question'):
            # Добавляем новый вопрос
            question_text = update.message.text
            context.user_data['new_question'] = {"name": question_text, "type": "text", "ogr": "optional"}
            context.user_data['new_survey']['form'].append(context.user_data['new_question'])


            # Запрашиваем ограничения
            await update.message.reply_text("Введите ограничения (например, max>100, min<0, mask=[?.?], length=10):")
            context.user_data['waiting_for_ogr'] = True
            context.user_data.pop('waiting_for_question', None)
        elif context.user_data.get('waiting_for_ogr'):
            # Сохраняем ограничения для последнего вопроса
            ogr_text = update.message.text
            context.user_data['new_question']['ogr'] = ogr_text
            context.user_data.pop('waiting_for_ogr', None)

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
        cursor.execute('SELECT answers, timestamp,survey_name FROM responses WHERE survey_name = ?', (survey_name,))
        rows = cursor.fetchall()
        # Создаем CSV-файл в памяти
        output = StringIO()
        header = ['Timestamp', 'Survey Name']  # Начинаем с временной метки и названия анкеты
        csv_writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        # Получаем уникальные ключи из всех ответов
        all_keys = set()
        for row in rows:
            answers = json.loads(row[0])  # Обратите внимание, что answers находится во втором индексе
            all_keys.update(answers.keys())
        header.extend(all_keys)
        csv_writer.writerow(header)

        for row in rows:
            answers = json.loads(row[0])
            csv_row = [row[1], row[2]]  # Временная метка и название анкеты
            csv_row.extend([answers.get(key, '') for key in all_keys])
            csv_writer.writerow(csv_row)

        output.seek(0)




        await update.callback_query.message.reply_document(
            document=output.getvalue().encode('windows-1251'),
            filename=f'{survey_name}.csv'
        )
        await update.callback_query.answer("Анкета загружена.")

        async def select_date_range(update: Update) -> None:
            """Запрашивает у пользователя диапазон дат для скачивания анкеты."""
            query = update.callback_query
            await query.answer()

            await query.message.reply_text("Введите дату начала (в формате YYYY-MM-DD):")
            user_state[query.message.chat_id] = "waiting_for_start_date"  # Устанавливаем состояние для ожидания даты начала

    async def handle_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обрабатывает ввод дат для скачивания анкет."""
        chat_id = update.message.chat_id

        if user_state.get(chat_id) == "waiting_for_start_date":
            user_state[chat_id] = "waiting_for_end_date"  # Переход к ожиданию даты окончания
            context.user_data['start_date'] = update.message.text  # Сохраняем дату начала
            await update.message.reply_text("Введите дату окончания (в формате YYYY-MM-DD):")
        elif user_state.get(chat_id) == "waiting_for_end_date":
            user_state[chat_id] = None  # Сбрасываем состояние
            context.user_data['end_date'] = update.message.text  # Сохраняем дату окончания
            await download_survey_csv(update, context)  # Переходим к скачиванию


async def download_survey_csv2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Скачивание выбранной анкеты в формате CSV с учетом диапазона дат."""
    chat_id = update.callback_query.message.chat_id
    survey_name = context.user_data.get('survey_name')  # Имя анкеты из контекста
    start_date = context.user_data.get('start_date')
    end_date = context.user_data.get('end_date')

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT answers, timestamp FROM responses 
            WHERE survey_name = ? AND timestamp BETWEEN ? AND ?
        ''', (survey_name, start_date, end_date))
        rows = cursor.fetchall()

        if not rows:
            await update.callback_query.message.reply_text("Нет ответов для данной анкеты в указанный диапазон дат.")
            return

        # Создаем CSV-файл в памяти
        output = StringIO()
        header = ['Timestamp', 'Answers']  # Заголовки
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


async def handle_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ввод дат для скачивания анкет."""
    chat_id = update.message.chat_id

    if user_state.get(chat_id) == "waiting_for_start_date":
        user_state[chat_id] = "waiting_for_end_date"  # Переход к ожиданию даты окончания
        context.user_data['start_date'] = update.message.text  # Сохраняем дату начала
        await update.message.reply_text("Введите дату окончания (в формате YYYY-MM-DD):")
    elif user_state.get(chat_id) == "waiting_for_end_date":
        user_state[chat_id] = None  # Сбрасываем состояние
        context.user_data['end_date'] = update.message.text  # Сохраняем дату окончания
        await download_survey_csv(update, context)  # Переходим к скачиванию