import os
import traceback
from datetime import datetime

from telebot import types

import psycopg2
from psycopg2 import sql


connection = psycopg2.connect(
    dbname='gigahr',
    user='postgres',
    password='postgres',
    host='localhost',
    port=5432
)
connection.autocommit = True
cursor = connection.cursor()


def enter_user_data(message):
    parts = message.text.split("\n")
    parsed = []

    expected_num = 1

    for line in parts:
        line = line.strip()

        if not line:
            continue

        if line.startswith(f"{expected_num}."):
            content = line[len(f"{expected_num}."):].strip()
            parsed.append(content)
            expected_num += 1

    if len(parsed) == 3:
        user_id = message.from_user.id

        cursor.execute(
            """
            INSERT INTO users_data (tg_id, fio, resume, contact) VALUES (%s, %s, %s, %s)
            ON CONFLICT (tg_id) DO UPDATE SET
                fio = EXCLUDED.fio,
                resume = EXCLUDED.resume,
                contact = EXCLUDED.contact;
            """,
            (user_id, parsed[0], parsed[1], parsed[2])
        )

        log_file(f"TG_ID:{user_id} - Пользователь добавил свои данные в БД.")
        return True

    return False


def inline_buttons_list(list_name: str, buttons_list: list[list[str]], current_page: int = 1, max_buttons: int = 5):
    markup = types.InlineKeyboardMarkup()

    pages_count = (len(buttons_list) + max_buttons - 1) // max_buttons

    start = current_page * max_buttons
    end = start + max_buttons
    page_buttons = buttons_list[start:end]

    for button_text, button_callback in page_buttons:
        markup.add(types.InlineKeyboardButton(text=button_text, callback_data=button_callback))

    if pages_count > 1:
        prev_page = current_page - 1 if current_page > 0 else pages_count - 1
        button_prev = types.InlineKeyboardButton(text='<', callback_data=f'<page/{list_name}>{prev_page}')

        button_page = types.InlineKeyboardButton(text=f'{current_page + 1}/{pages_count}', callback_data='page_button')

        next_page = current_page + 1 if current_page < pages_count - 1 else 0
        button_next = types.InlineKeyboardButton(text='>', callback_data=f'<page/{list_name}>{next_page}')

        markup.row(button_prev, button_page, button_next)

    return markup


def log_file(data: str | Exception):
    path = 'logs'
    os.makedirs(path, exist_ok=True)

    is_error = isinstance(data, Exception)
    prefix = "ERROR" if is_error else "ACTION"

    existing_files = [f for f in os.listdir(path) if f.startswith(prefix)]
    current_file = None
    if existing_files:
        existing_files.sort()
        candidate = os.path.join(path, existing_files[-1])
        if os.path.getsize(candidate) < 1 * 1024 * 1024 * 1024:
            current_file = candidate

    if not current_file:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        current_file = os.path.join(path, f"{prefix}_{timestamp}.log")

    if is_error:
        log_text = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {str(data)}\n"
        log_text += traceback.format_exc() + "\n\n"
    else:
        log_text = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {data}\n"

    with open(current_file, "a", encoding="utf-8") as f:
        f.write(log_text)


def get_vacancies():
    cursor.execute("SELECT id, name, description, status FROM vacancies;")
    rows = cursor.fetchall()
    return [list(row) for row in rows]


def get_users_data():
    cursor.execute("SELECT tg_id, fio, resume, contact FROM users_data;")
    rows = cursor.fetchall()
    return [list(row) for row in rows]


def get_interview_slots():
    cursor.execute("SELECT id, vacancy_id, available_date, available_time, is_available FROM interview_slots;")
    rows = cursor.fetchall()
    return [list(row) for row in rows]


def get_candidates():
    cursor.execute("SELECT id, user_id, slot_id, date, vacancy_name, user_fio, user_resume, user_contact, status FROM candidates;")
    rows = cursor.fetchall()
    return [list(row) for row in rows]


def notifications(table_name: str):
    query_select = sql.SQL("SELECT id, user_id, vacancy_name FROM {} WHERE is_notified = TRUE").format(sql.Identifier(table_name))
    cursor.execute(query_select)
    rows = cursor.fetchall()

    query_delete = sql.SQL("DELETE FROM {} WHERE is_notified = TRUE").format(sql.Identifier(table_name))
    cursor.execute(query_delete)

    return rows


def changed_vacancy_status():
    cursor.execute(
        """
        SELECT id, user_id, slot_id, date, vacancy_name, status, COALESCE(last_notified_status, '') AS last_status
        FROM candidates
        WHERE status IS DISTINCT FROM COALESCE(last_notified_status, '')
        """
    )
    rows = cursor.fetchall()

    result_rows = []
    for candidate_id, user_id, slot_id, date, vacancy_name, status, last_status in rows:
        if not (last_status == '' and status == 'Назначено собеседование'):
            result_rows.append((candidate_id, user_id, slot_id, date, vacancy_name, status))

        cursor.execute(
            "UPDATE candidates SET last_notified_status = %s WHERE id = %s",
            (status, candidate_id)
        )
        if status in ("Принят", "Отказано") and slot_id:
            cursor.execute(
                "DELETE FROM interview_slots WHERE id = %s",
                (slot_id,)
            )

    return result_rows
