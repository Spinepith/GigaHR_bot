import os
import traceback
from datetime import datetime

from telebot import types

import psycopg2
from psycopg2 import sql

from ..config import *


connection = psycopg2.connect(
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT
)
connection.autocommit = True
cursor = connection.cursor()


def inline_buttons_list(list_name: str, buttons_list: list[list[str]], current_page: int = 1, max_buttons: int = 5):
    markup = types.InlineKeyboardMarkup()

    pages_count = (len(buttons_list) + max_buttons - 1) // max_buttons

    start = current_page * max_buttons
    end = start + max_buttons
    page_buttons = buttons_list[start:end]

    for button_text, button_callback in page_buttons:
        markup.add(types.InlineKeyboardButton(
            text=button_text, callback_data=button_callback))

    if pages_count > 1:
        prev_page = current_page - 1 if current_page > 0 else pages_count - 1
        button_prev = types.InlineKeyboardButton(
            text='<', callback_data=f'<page/{list_name}>{prev_page}')

        button_page = types.InlineKeyboardButton(
            text=f'{current_page + 1}/{pages_count}', callback_data='page_button')

        next_page = current_page + 1 if current_page < pages_count - 1 else 0
        button_next = types.InlineKeyboardButton(
            text='>', callback_data=f'<page/{list_name}>{next_page}')

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


# ФУНКЦИИ ДЛЯ РАБОТЫ С БД
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


def get_vacancies():
    cursor.execute("SELECT id, name, description, status FROM vacancies;"
                   )
    rows = cursor.fetchall()
    return [list(row) for row in rows]


def get_users_data():
    cursor.execute("SELECT tg_id, fio, resume, contact FROM users_data;"
                   )
    rows = cursor.fetchall()
    return [list(row) for row in rows]


def get_interview_slots():
    cursor.execute(
        "SELECT id, vacancy_id, available_date, available_time, is_available FROM interview_slots;"
    )
    rows = cursor.fetchall()
    return [list(row) for row in rows]


def get_candidates():
    cursor.execute(
        "SELECT id, user_id, slot_id, date, vacancy_name, user_fio, user_resume, user_contact, status FROM candidates;"
    )
    rows = cursor.fetchall()
    return [list(row) for row in rows]


def notifications(table_name: str):
    query_select = sql.SQL("SELECT id, user_id, vacancy_name FROM {} WHERE is_notified = TRUE").format(
        sql.Identifier(table_name))
    cursor.execute(query_select)
    rows = cursor.fetchall()

    query_delete = sql.SQL("DELETE FROM {} WHERE is_notified = TRUE").format(
        sql.Identifier(table_name))
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
            result_rows.append(
                (candidate_id, user_id, slot_id, date, vacancy_name, status))

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


# ДЛЯ СОТРУДНИКОВ
def is_employee(tg_id: int):
    try:
        cursor.execute("SELECT 1 FROM employees WHERE tg_id = %s LIMIT 1;", (tg_id,))
        result = cursor.fetchone()
        return result is not None
    except Exception as e:
        log_file(f"Ошибка при проверке сотрудника: {e}")
        return False


def get_all_interviews_employee(tg_id: int):
    try:
        cursor.execute("""
                    SELECT 
                        s.id AS slot_id,
                        s.available_date,
                        s.available_time,
                        v.name AS vacancy_name
                    FROM interview_slots s
                    JOIN vacancies v ON s.vacancy_id = v.id
                    WHERE s.employee_tg_id = %s
                    ORDER BY s.available_date, s.available_time
                """, (tg_id,))
        rows = cursor.fetchall()
        return [list(row) for row in rows]
    except Exception as e:
        log_file("Ошибка при получении дат всех собеседований из БД.")
        log_file(e)


def get_interviews_employee(tg_id: int):
    try:
        cursor.execute(
            "SELECT id, slot_id, date FROM candidates WHERE employee_tg_id = %s ORDER BY date;",
            (tg_id,)
        )
        rows = cursor.fetchall()
        return [list(row) for row in rows]
    except Exception as e:
        log_file("Ошибка при получении дат занятых собеседований из БД.")
        log_file(e)


def get_data_interview_employee(tg_id: int, slot_id: int):
    try:
        cursor.execute(
            """SELECT id, date, vacancy_name, user_fio, user_resume, user_contact, status 
               FROM candidates 
               WHERE slot_id = %s AND employee_tg_id = %s 
               ORDER BY date;""",
            (slot_id, tg_id)
        )
        return cursor.fetchall()[0]
    except Exception as e:
        log_file("Ошибка при получение информации о кандидате из БД.")
        log_file(e)


def set_status_interview_employee(slot_id: int, status: str):
    try:
        cursor.execute(
            "UPDATE candidates SET status = %s WHERE slot_id = %s;",
            (status, slot_id)
        )
    except Exception as e:
        log_file("Ошибка при изменении статуса собеседования в БД.")
        log_file(e)


def add_interview_employee(tg_id: int, vacancy_name: str, date_str: str, time_str: str):
    try:
        cursor.execute("SELECT 1 FROM employees WHERE tg_id = %s AND vacancy_name = %s", (tg_id, vacancy_name))
        employee = cursor.fetchone()

        if not employee:
            log_file(
                f"Попытка добавить слот для чужой вакансии. Сотрудник tg_id {tg_id} не привязан к вакансии: {vacancy_name}"
            )
            return False

        cursor.execute("SELECT id FROM vacancies WHERE name = %s", (vacancy_name,))
        vacancy = cursor.fetchone()

        if not vacancy:
            log_file(f"Вакансия '{vacancy_name}' не найдена в БД.")
            return False

        vacancy_id = vacancy[0]

        cursor.execute("""
                    INSERT INTO interview_slots (vacancy_id, available_date, available_time, is_available, employee_tg_id)
                    VALUES (%s, %s, %s, TRUE, %s)
                """, (vacancy_id, date_str, time_str, tg_id))

        log_file(f"[{vacancy_name}] Сотрудник добавил дату собеседования в БД.")
        return True
    except Exception as e:
        log_file("Ошибка при добавлении даты собеседования в БД.")
        log_file(e)


def delete_interview_employee(tg_id: int, slot_id: int):
    try:
        cursor.execute("""
            SELECT available_date, available_time 
            FROM interview_slots 
            WHERE id = %s AND employee_tg_id = %s
        """, (slot_id, tg_id))
        slot_data = cursor.fetchone()

        cursor.execute("DELETE FROM interview_slots WHERE id = %s AND employee_tg_id = %s", (slot_id, tg_id))

        return slot_data
    except Exception as e:
        log_file("Ошибка при удалении даты собеседования из БД.")
        log_file(e)


def notifications_employee():
    cursor.execute("""
            SELECT 
                id, 
                employee_tg_id,
                vacancy_name,
                user_fio,
                user_contact,
                user_resume,
                available_date,
                available_time,
                action_type
            FROM employee_notifications 
            WHERE is_notified = TRUE
        """)
    rows = cursor.fetchall()

    cursor.execute("DELETE FROM employee_notifications WHERE is_notified = TRUE")
    return rows
