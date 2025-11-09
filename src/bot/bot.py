import datetime
import time
import sys
import signal
import atexit
import threading
import telebot

from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from . import utils
from . import gigahr

from ..config import *


TOKEN = BOT_TOKEN
bot = telebot.TeleBot(TOKEN)

employee_mod = False


@bot.message_handler(commands=['start'])
def start_command(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        types.KeyboardButton('Вакансии'),
        types.KeyboardButton('Мои собеседования')
    )
    markup.add(types.KeyboardButton('Мои данные'))

    bot.send_message(
        message.chat.id,
        '<b>Здравствуйте!\n'
        'Я - ваш персональный HR-помощник.\n\n</b>'
        'Здесь вы можете узнать обо всех актуальных вакансиях нашей компании и записаться на собеседование.\n'
        'Я понимаю свободную речь, поэтому вы можете просто написать свой вопрос, и я постараюсь помочь!\n\n'
        '<em>Основные действия осуществляются через кнопки - они помогут вам быстро найти нужную информацию.</em>',
        reply_markup=markup,
        parse_mode='html'
    )


@bot.message_handler(commands=['vacancies'])
def vacancies_command(message):
    if employee_mod:
        return

    vacancies_list = utils.get_vacancies()
    buttons_list = [[i[1], f'<vacancy>{i[0]}'] for i in vacancies_list]

    if len(buttons_list):
        bot.send_message(
            message.chat.id,
            '<b><em>СПИСОК ВАКАНСИЙ</em></b>',
            reply_markup=utils.inline_buttons_list('vacancies', buttons_list, 0, 7),
            parse_mode='html'
        )
    else:
        bot.send_message(message.chat.id, "Сейчас список вакансий пуст.")


@bot.message_handler(commands=['mydata'])
def mydata_command(message):
    users_data = utils.get_users_data()
    user_data = ["НЕТ ДАННЫХ", "НЕТ ДАННЫХ", "НЕТ ДАННЫХ", "НЕТ ДАННЫХ"]

    user_id = message.from_user.id
    for user in users_data:
        if user_id == user[0]:
            user_data = user
            break

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text='Изменить данные', callback_data=f'<mydata>'))

    bot.send_message(
        message.chat.id,
        f'<b>ФИО\n</b>{user_data[1]}\n\n'
        f'<b>Резюме</b>\n{user_data[2]}\n\n'
        f'<b>Контакт для связи</b>\n{user_data[3]}',
        reply_markup=markup,
        parse_mode='html'
    )


@bot.message_handler(commands=['interviews'])
def interviews_command(message):
    candidates = utils.get_candidates()
    user_interviews = ["[НЕТ ДАННЫХ] НЕТ ДАННЫХ - НЕТ ДАННЫХ"]
    create_button = False

    for i in candidates:
        if message.from_user.id == i[1]:
            user_interviews.append(f'[{i[3]}] {i[4]} - {i[8]}')
            if not create_button and i[8] == "Назначено собеседование":
                create_button = True

    markup = types.InlineKeyboardMarkup()
    if len(user_interviews) == 1:
        message_text = "У вас пока нет назначенных собеседований."
    else:
        message_text = "\n\n".join(user_interviews[1:])
        if create_button:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(text='Отменить собеседование', callback_data=f'<my_interviews>'))

    bot.send_message(
        message.chat.id,
        f'<b>Ваши собеседования:</b>\n\n'
        f'{message_text}',
        reply_markup=markup,
        parse_mode='html'
    )


@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(
        message.chat.id,
        '/vacancies - список вакансий\n'
        '/mydata - мои данные\n'
        '/interviews - мои собеседования\n'
        '/help - список всех команд\n'
    )


@bot.message_handler(commands=[CHANGE_STATUS_COMMAND])
def change_status_command(message):
    if not utils.is_employee(message.from_user.id):
        bot.send_message(message.chat.id, "Вы не найдены в базе данных сотрудников")
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('Занятые даты'))
    markup.row(
        types.KeyboardButton('Добавить'),
        types.KeyboardButton('Удалить')
    )
    markup.add(types.KeyboardButton('Все даты'))

    bot.send_message(
        message.chat.id,
        '<b><em>ВЫ ПЕРЕКЛЮЧИЛИСЬ НА ВЕРСИЮ ДЛЯ СОТРУДНИКА</em></b>',
        reply_markup=markup,
        parse_mode='html'
    )

    global employee_mod
    employee_mod = True


@bot.message_handler(content_types=['text'])
def not_command(message):
    if message.text.lower() == 'вакансии':
        vacancies_command(message)
    elif message.text.lower() == 'мои данные':
        mydata_command(message)
    elif message.text.lower() == 'мои собеседования':
        interviews_command(message)

    elif employee_mod and message.text.lower() == 'добавить':
        msg = bot.send_message(
            message.chat.id,
            "Введите вакансию в первой строке\n"
            "Введите дату и время во второй строке\n\n"
            "Химик-технолог\n"
            "2025-12-16 14:20"
            "\n\n"
            "Обязательно соблюдайте формат из примера"
        )
        bot.register_next_step_handler(msg, add_interview)
    elif employee_mod and (message.text.lower() == 'удалить' or message.text.lower() == 'занятые даты'):
        if message.text.lower() == 'занятые даты':
            slots = utils.get_interviews_employee(message.from_user.id)
            buttons_list = [
                [f"[{date}]", f"<interview_data>{slot_id}"] for _id, slot_id, date in slots
            ]
            list_type = "interviews_data"
        else:
            slots = utils.get_all_interviews_employee(message.from_user.id)
            buttons_list = [
                [f"[{_date} {_time}]", f"<del_interview>{slot_id}"] for slot_id, _date, _time, vacancy in slots
            ]
            list_type = "del_interviews"

        if not slots:
            bot.send_message(message.chat.id, "У вас нет созданных дат собеседований")
        else:
            bot.send_message(
                message.chat.id,
                '<b><em>СПИСОК ВСЕХ ДАТ</em></b>',
                reply_markup=utils.inline_buttons_list(list_type, buttons_list, 0, 7),
                parse_mode='html'
            )
    elif employee_mod and message.text.lower() == 'все даты':
        slots = utils.get_all_interviews_employee(message.from_user.id)

        if slots:
            slots_message = "\n".join(f"[{_date} {_time}] {vacancy}" for slot_id, _date, _time, vacancy in slots)
        else:
            slots_message = "У вас нет созданных дат собеседований"

        bot.send_message(message.chat.id, slots_message)

    else:
        utils.log_file(f'TG_ID: {message.from_user.id} - Пользователю будет отвечать GigaChat.')

        user_id = message.from_user.id
        vacancies_list = utils.get_vacancies()
        response = gigahr.get_response(user_id, message.text, vacancies_list)

        if response != '/vacancies':
            bot.send_message(user_id, response)
            utils.log_file(f'TG_ID: {message.from_user.id} - Пользователю успешно ответил GigaChat.')
        else:
            vacancies_command(message)


@bot.callback_query_handler(func=lambda callback: True)
def callback_message(callback):
    if callback.data.startswith('<mydata>'):
        bot.send_message(
            callback.message.chat.id,
            '<b>Введите данные в формате</b>\n\n'
            '1. ФИО\n'
            '2. Резюме\n'
            '3. Контакт для связи\n\n'
            '<em>Каждый пункт вводите с новой строки и обязательно указывайте его номер.</em>',
            parse_mode='html'
        )

        bot.register_next_step_handler(
            callback.message,
            lambda message: mydata_command(message) if utils.enter_user_data(message) else bot.send_message(
                message.chat.id, 'Ошибка обновления данных')
        )

    if callback.data.startswith('<vacancy>'):
        rows = utils.get_vacancies()
        vacancy_data = ['НЕТ ДАННЫХ', 'НЕТ ДАННЫХ', 'НЕТ ДАННЫХ', 'НЕТ ДАННЫХ']

        for i in rows:
            vacancy_id, vacancy_name, vacancy_description, vacancy_status = i
            if int(vacancy_id) == int(callback.data.split('<vacancy>')[1]):
                vacancy_data = i
                break

        if vacancy_data[3] == 'Свободна':
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(text='Записаться', callback_data=f'<interviews>{vacancy_data[0]}'))
            bot.send_message(
                callback.message.chat.id,
                f'<b>{vacancy_data[1]}</b>\n\n'
                f'{vacancy_data[2]}\n\n'
                f'<em>Для записи будут использованы "Мои данные".</em>',
                reply_markup=markup,
                parse_mode='html'
            )
        else:
            markup = types.InlineKeyboardMarkup()
            if vacancy_data[3] != 'НЕТ ДАННЫХ':
                markup.add(
                    types.InlineKeyboardButton(
                        text='Сообщить, когда появится место',
                        callback_data=f'<vcn_ntf>{vacancy_data[0]}|{callback.from_user.id}'
                    )
                )
            bot.send_message(
                callback.message.chat.id,
                f'<b>{vacancy_data[1]}</b>\n\n'
                f'{vacancy_data[2]}\n\n'
                '<em>К сожалению, данная вакансия временно недоступна!</em>',
                reply_markup=markup,
                parse_mode='html'
            )

    if callback.data.startswith('<interviews>'):
        vacancy_id = int(callback.data.split('<interviews>')[1])
        all_interview_dates = utils.get_interview_slots()
        buttons_list = [
            [f'{i[2]} {i[3]}', f'<set_interview_date>v_id:{i[1]};slot_id:{i[0]}']
            for i in all_interview_dates if int(i[1]) == vacancy_id and i[4]
        ]

        rows = utils.get_vacancies()
        vacancy_name = ''
        for i in rows:
            if vacancy_id == i[0]:
                vacancy_name = i[1]
                break

        markup = utils.inline_buttons_list(f'interview_dates_{vacancy_id}', buttons_list, 0, 7)
        if markup.to_dict().get("inline_keyboard"):
            bot.send_message(
                callback.message.chat.id,
                f'<b>{vacancy_name}</b>\n'
                f'<em>Для записи будут использованы "Мои данные".</em>\n\n'
                f'Даты собеседований',
                reply_markup=markup,
                parse_mode='html'
            )
        else:
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    text='Сообщить, когда появится дата',
                    callback_data=f'<intvw_ntf>{vacancy_id}|{callback.from_user.id}'
                )
            )

            bot.send_message(
                callback.message.chat.id,
                f'<b>{vacancy_name}</b>\nПока нет доступных дат',
                reply_markup=markup,
                parse_mode='html'
            )

    if callback.data.startswith('<set_interview_date>'):
        payload = callback.data.replace("<set_interview_date>", "")
        parts = payload.split(";")

        vacancy_id = int(parts[0].split(":")[1])
        slot_id = int(parts[1].split(":", 1)[1])

        utils.cursor.execute("SELECT available_date, available_time, employee_tg_id FROM interview_slots WHERE id = %s;", (slot_id,))
        available_date, available_time, employee_tg_id = utils.cursor.fetchone() or (None, None, None)
        date = f'{available_date} {available_time}'

        utils.cursor.execute("SELECT name FROM vacancies WHERE id = %s;", (vacancy_id,))
        result = utils.cursor.fetchone()
        vacancy_name = result[0] if result else "НЕТ ДАННЫХ"

        users_data = utils.get_users_data()
        user_data = []
        for i in users_data:
            if i[0] == callback.from_user.id:
                user_data = i
                break

        try:
            utils.cursor.execute(
                "INSERT INTO candidates (user_id, slot_id, date, employee_tg_id, vacancy_name, user_fio, user_resume, user_contact, status)"
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);",
                (callback.from_user.id, slot_id, date, employee_tg_id, vacancy_name, user_data[1], user_data[2], user_data[3], 'Назначено собеседование')
            )

            bot.send_message(
                callback.message.chat.id,
                f'<b>{vacancy_name}</b>\n\n'
                f'Вы записались на собеседование\n'
                f'{date}',
                parse_mode='html'
            )

            utils.log_file(f'TG_ID: {callback.from_user.id} - Пользователь записался на собеседование {vacancy_name}.')
        except:
            bot.send_message(
                callback.message.chat.id,
                f'<b>{vacancy_name}</b>\n\n'
                f'НЕВОЗМОЖНО ЗАПИСАТЬСЯ\n'
                f'{available_date} {available_time}\n\n'
                '<em>Проверьте меню "Мои данные"</em>',
                parse_mode='html'
            )
            utils.log_file(
                f'TG_ID: {callback.from_user.id} - '
                f'Пользователь пытался второй раз записаться на одно и то же собеседование {vacancy_name}.'
            )

    if callback.data.startswith('<my_interviews>'):
        user_id = callback.from_user.id

        candidates = utils.get_candidates()
        buttons_list = [
            [f'[{i[3]}] {i[4]}', f'<cancel_interview>{i[2]}']
            for i in candidates if user_id == i[1] and i[8] == "Назначено собеседование"
        ]

        bot.send_message(
            callback.message.chat.id,
            'Какое собеседование отменить?',
            reply_markup=utils.inline_buttons_list(f'my_interviews', buttons_list, 0, 7)
        )

    if callback.data.startswith('<cancel_interview>'):
        slot_id = callback.data.split("<cancel_interview>")[1]

        utils.cursor.execute("SELECT date, vacancy_name FROM candidates WHERE slot_id = %s;", (slot_id,))
        date, vacancy_name = utils.cursor.fetchone() or (None, None)

        if date and vacancy_name:
            utils.cursor.execute("DELETE FROM candidates WHERE slot_id = %s;", (slot_id,))
            bot.send_message(
                callback.message.chat.id,
                f'<b>{vacancy_name}</b>\n\n'
                f'Собеседование отменено\n'
                f'{date}',
                parse_mode='html'
            )
            utils.log_file(f'TG_ID: {callback.from_user.id} - Пользователь отменил собеседование.')
        else:
            bot.send_message(callback.message.chat.id, 'Вы уже отменяли это собеседование.')

    if callback.data.startswith('<vcn_ntf>'):
        bot.edit_message_reply_markup(callback.message.chat.id, callback.message.message_id, reply_markup=None)
        vacancy_id = int(callback.data.split('<vcn_ntf>')[1].split('|')[0])
        utils.cursor.execute("SELECT name FROM vacancies WHERE id = %s;", (vacancy_id,))
        result = utils.cursor.fetchone()
        vacancy_name = result[0] if result else "НЕТ ДАННЫХ"

        utils.cursor.execute(
            "INSERT INTO vacancy_subscriptions (user_id, vacancy_id, vacancy_name)"
            "VALUES (%s, %s, %s)"
            "ON CONFLICT (user_id, vacancy_id) DO NOTHING;",
            (callback.from_user.id, vacancy_id, vacancy_name)
        )

        try:
            bot.send_message(
                callback.message.chat.id,
                f'<b>{vacancy_name}</b>\nВам поступит уведомление, когда вакансия снова станет доступна.',
                parse_mode='html'
            )
            utils.log_file(
                f'TG_ID: {callback.from_user.id} - Пользователь подписался на уведомление о вакансии {vacancy_name}.'
            )
        except:
            bot.send_message(
                callback.message.chat.id,
                f'<b>Произошла ошибка</b>.\nВозможно в меню "МОИ ДАННЫЕ" вы ничего не вводили о себе.',
                parse_mode='html'
            )

    if callback.data.startswith('<intvw_ntf>'):
        bot.edit_message_reply_markup(callback.message.chat.id, callback.message.message_id, reply_markup=None)
        vacancy_id = int(callback.data.split('<intvw_ntf>')[1].split('|')[0])
        utils.cursor.execute("SELECT name FROM vacancies WHERE id = %s;", (vacancy_id,))
        result = utils.cursor.fetchone()
        vacancy_name = result[0] if result else "НЕТ ДАННЫХ"

        utils.cursor.execute(
            "INSERT INTO interview_slot_subscriptions (user_id, vacancy_id, vacancy_name)"
            "VALUES (%s, %s, %s)"
            "ON CONFLICT (user_id, vacancy_id) DO NOTHING;",
            (callback.from_user.id, vacancy_id, vacancy_name)
        )

        bot.send_message(
            callback.message.chat.id,
            f'<b>{vacancy_name}</b>\nВам поступит уведомление, когда появится возможность пройти собеседование.',
            parse_mode='html'
        )
        utils.log_file(
            f'TG_ID: {callback.from_user.id} - Пользователь подписался на уведомление о собеседовании {vacancy_name}.'
        )

    if callback.data.startswith('<interview_data>'):
        try:
            user_id = callback.from_user.id
            slot_id = int(callback.data.split('<interview_data>')[1])
            candidate = utils.get_data_interview_employee(user_id, slot_id)

            statuses = ["Назначено собеседование", "На рассмотрении", "Принят", "Отказано"]
            markup = InlineKeyboardMarkup()
            for i, j in enumerate(statuses):
                if candidate[6] != j:
                    markup.add(InlineKeyboardButton(text=j, callback_data=f"<change_vacancy_status>{slot_id};{i}"))

            bot.send_message(
                callback.message.chat.id,
                "<b>Информация о кандидате\n\n</b>"
                f"{candidate[2]}\n"
                f"{candidate[1]}\n\n"
                f"{candidate[4]}\n\n"
                f"{candidate[3]}\n"
                f"{candidate[5]}\n\n"
                f"[{candidate[6]}]",
                reply_markup=markup,
                parse_mode='html'
            )
        except Exception as e:
            bot.send_message(callback.message.chat.id, "Произошла ошибка. Попробуйте еще раз.")
            utils.log_file(
                f'TG_ID: {callback.from_user.id} - '
                f'Ошибка при получение информации о кандидате из БД.'
            )
            utils.log_file(e)

    if callback.data.startswith('<del_interview>'):
        try:
            user_id = callback.from_user.id
            slot_id = int(callback.data.split('<del_interview>')[1])
            deleted = utils.delete_interview_employee(user_id, slot_id)
            bot.send_message(
                callback.message.chat.id,
                "<b>Дата собеседования успешно удалена!</b>\n\n"
                f"{deleted[0]} {deleted[1]}",
                parse_mode='html'
            )

            try:
                slots = utils.get_all_interviews_employee(callback.from_user.id)
                buttons_list = [
                    [f"[{_date} {_time}]", f"<del_interview>{slot_id}"] for slot_id, _date, _time, vacancy in slots
                ]
                bot.edit_message_reply_markup(
                    callback.message.chat.id,
                    callback.message.message_id,
                    reply_markup=utils.inline_buttons_list('del_interviews', buttons_list, 0, 7),
                )
            except:
                pass

        except Exception as e:
            bot.send_message(callback.message.chat.id, "Произошла ошибка. Попробуйте еще раз.")
            utils.log_file(
                f'TG_ID: {callback.from_user.id} - '
                f'Ошибка при удалении даты собеседования из БД.'
            )
            utils.log_file(e)

    if callback.data.startswith('<change_vacancy_status>'):
        try:
            user_id = callback.from_user.id
            statuses = ["Назначено собеседование", "На рассмотрении", "Принят", "Отказано"]

            payload = callback.data.replace("<change_vacancy_status>", "")
            slot_id = int(payload.split(';')[0])
            status = statuses[int(payload.split(';')[1])]

            utils.set_status_interview_employee(slot_id, status)
            candidate = utils.get_data_interview_employee(user_id, slot_id)

            if status not in ("Принят", "Отказано"):
                markup = InlineKeyboardMarkup()
                for i, j in enumerate(statuses):
                    if candidate[6] != j:
                        markup.add(InlineKeyboardButton(text=j, callback_data=f"<change_vacancy_status>{slot_id};{i}"))
            else:
                markup = None

            bot.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text="<b>Информация о кандидате\n\n</b>"
                     f"{candidate[2]}\n"
                     f"{candidate[1]}\n\n"
                     f"{candidate[4]}\n\n"
                     f"{candidate[3]}\n"
                     f"{candidate[5]}\n\n"
                     f"[{candidate[6]}]",
                reply_markup=markup,
                parse_mode='html'
            )
        except Exception as e:
            bot.send_message(callback.message.chat.id, "Произошла ошибка. Попробуйте еще раз.")
            utils.log_file(
                f'TG_ID: {callback.from_user.id} - '
                f'Ошибка при изменении статуса собеседования.'
            )
            utils.log_file(e)

    if callback.data.startswith('<page/'):
        buttons_list = []
        list_type = ''

        if callback.data.startswith('<page/vacancies>'):
            vacancies_list = utils.get_vacancies()
            buttons_list = [[i[1], f'<vacancy>{i[0]}'] for i in vacancies_list]
            list_type = 'vacancies'
        elif callback.data.startswith('<page/interview_dates_'):
            vacancy_id = int(callback.data.split('page/interview_dates_')[1].split('>')[0])
            all_interview_dates = utils.get_interview_slots()
            buttons_list = [
                [f'{i[2]} {i[3]}', f'<set_interview_date>id:{i[1]};date:{i[2]} {i[3]}']
                for i in all_interview_dates if int(i[1]) == vacancy_id
            ]
            list_type = f'interview_dates_{vacancy_id}'
        elif callback.data.startswith('<page/my_interviews>'):
            candidates = utils.get_candidates()
            user_id = callback.from_user.id
            buttons_list = [
                [f'[{i[3]}] {i[4]}', f'<cancel_interview>{i[2]}']
                for i in candidates if user_id == i[1] and i[8] == "Назначено собеседование"
            ]
            list_type = 'my_interviews'
        elif callback.data.startswith('<page/interview_data>'):
            slots = utils.get_all_interviews_employee(callback.from_user.id)
            buttons_list = [
                [f"[{date}]", f"<interview_data>{slot_id}"] for _id, slot_id, date in slots
            ]
            list_type = 'interviews_data'
        elif callback.data.startswith('<page/interviews_data>'):
            slots = utils.get_interviews_employee(callback.from_user.id)
            buttons_list = [
                [f"[{date}]", f"<interview_data>{slot_id}"] for _id, slot_id, date in slots
            ]
            list_type = 'interviews_data'
        elif callback.data.startswith('<page/del_interviews>'):
            slots = utils.get_all_interviews_employee(callback.from_user.id)
            buttons_list = [
                [f"[{_date} {_time}]", f"<del_interview>{slot_id}"] for slot_id, _date, _time, vacancy in slots
            ]
            list_type = 'del_interviews'

        new_page = int(callback.data.split('>')[1])
        bot.edit_message_reply_markup(
            callback.message.chat.id,
            callback.message.message_id,
            reply_markup=utils.inline_buttons_list(list_type, buttons_list, new_page, 7)
        )


def add_interview(message):
    try:
        lines = [line.strip() for line in message.text.strip().split('\n') if line.strip()]

        if len(lines) != 2:
            bot.send_message(message.chat.id, "Ошибка при добавлении даты собеседовании\nВведите две строки")
            return

        vacancy_name = lines[0]
        datetime_str = lines[1]

        try:
            parts = datetime_str.strip().split(' ')
            if len(parts) != 2:
                raise ValueError

            date_str, time_str = parts

            datetime.datetime.strptime(date_str, "%Y-%m-%d")
            datetime.datetime.strptime(time_str, "%H:%M")
            time_str = time_str + ":00"
        except:
            bot.send_message(
                message.chat.id,
                "Ошибка при добавлении даты собеседовании\nНеверный формат даты и времени\n\n"
                "Используйте: ГГГГ-ММ-ДД ЧЧ:ММ\n"
                "Пример: 2025-12-16 14:20"
            )
            return

        success = utils.add_interview_employee(message.from_user.id, vacancy_name, date_str, time_str)
        if success:
            bot.send_message(message.chat.id, "Дата собеседования успешно добавлена!\n\n")
        else:
            bot.send_message(
                message.chat.id,
                "Ошибка при добавлении даты собеседовании\n"
                "Возможно данные дата и время уже существуют\n"
                "Проверьте правильность введенных данных"
            )
    except:
        bot.send_message(message.chat.id, "Ошибка при добавлении даты собеседовании. Попробуйте еще раз.")
        utils.log_file("Ошибка при добавлении даты собеседовании")


def check_notifications():
    while True:
        rows = utils.notifications('vacancy_subscriptions')
        for record_id, user_id, vacancy_name in rows:
            bot.send_message(user_id, f'<b>{vacancy_name}</b>\n\nВакансия доступна!', parse_mode='html')
            utils.log_file(
                f'TG_ID: {user_id} - Пользователю отправлено уведомлено о доступности вакансии {vacancy_name}.'
            )

        rows = utils.notifications('interview_slot_subscriptions')
        for record_id, user_id, vacancy_name in rows:
            bot.send_message(
                user_id,
                f"<b>{vacancy_name}</b>\n\nПоявился слот собеседования!",
                parse_mode="html"
            )
            utils.log_file(
                f"TG_ID: {user_id} - Пользователю отправлено уведомление о появлении вакансии {vacancy_name}."
            )

        rows = utils.changed_vacancy_status()
        for candidate_id, user_id, slot_id, date, vacancy_name, status in rows:
            bot.send_message(
                user_id,
                f"<b>{vacancy_name}</b>\n[{date}]\n\nСтатус вашей заявки изменился на\n<b><em>{status}</em></b>",
                parse_mode="html"
            )
            utils.log_file(
                f"TG_ID: {user_id} - Пользователю отправлено уведомление смене статуса собеседования {vacancy_name}."
            )

        rows = utils.notifications_employee()
        for notification in rows:
            record_id, employee_id, vacancy_name, user_fio, user_contact, user_resume, available_date, available_time, action_type = notification

            message = (
                f"<b>{'Новый кандидат' if action_type == 'added' else 'Кандидат отменил собеседование'}</b>\n\n"
                f"{vacancy_name}\n"
                f"{available_date} {available_time}\n\n"
                f"{user_resume}\n\n"
                f"{user_fio}\n"
                f"{user_contact}"
            )

            try:
                bot.send_message(
                    employee_id,
                    message,
                    parse_mode="html"
                )
                utils.log_file(
                    f"TG_ID: {employee_id} - Сотруднику отправлено уведомление о кандидате."
                )
            except telebot.apihelper.ApiTelegramException as e:
                utils.log_file(
                    f"TG_ID: {employee_id} - Сотруднику НЕ отправлено уведомление о кандидате. {e}"
                )

        time.sleep(10)


def start_bot():
    threading.Thread(target=check_notifications, daemon=True).start()
    atexit.register(lambda: (utils.cursor.close(), utils.connection.close()))
    signal.signal(signal.SIGINT, lambda sig, name: sys.exit(0))

    while True:
        try:
            print("\n# БОТ ЗАПУЩЕН\nЧТОБЫ ОСТАНОВИТЬ - НАЖМИТЕ Ctrl + C ИЛИ Control + C")
            utils.log_file("БОТ ЗАПУЩЕН")

            bot.polling(none_stop=False, interval=1, timeout=10)

            utils.log_file("БОТ ЗАВЕРШИЛ РАБОТУ")
            print("# БОТ ЗАВЕРШИЛ РАБОТУ\n")
        except SystemExit:
            utils.log_file(f"ПОЛЬЗОВАТЕЛЬ ЗАВЕРШИЛ РАБОТУ БОТА")
            print(f"# ПОЛЬЗОВАТЕЛЬ ЗАВЕРШИЛ РАБОТУ БОТА")
            break
        except Exception as e:
            utils.log_file("# КРИТИЧЕСКАЯ ОШИБКА. БОТ ЗАВЕРШИЛ РАБОТУ. БОТ БУДЕТ ПЕРЕЗАПУЩЕН ЧЕРЕЗ 5 СЕКУНД")
            utils.log_file(e)
            print(f"# КРИТИЧЕСКАЯ ОШИБКА. БОТ ЗАВЕРШИЛ РАБОТУ\n{e}\n\nБОТ БУДЕТ ПЕРЕЗАПУЩЕН ЧЕРЕЗ 5 СЕКУНД")
            time.sleep(5)
