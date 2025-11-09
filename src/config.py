""" ФАЙЛ С НАСТРОЙКАМИ. ГЛАВНАЯ ПЕРЕМЕННАЯ, СО ВСЕМИ ПАРАМЕТРАМИ БОТА """
import os
import json


with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json"), "r", encoding="utf-8") as f:
    __config = json.load(f)


DB_NAME = __config["db_name"]
DB_USER = __config["db_user"]
DB_PASSWORD = __config["db_password"]
DB_HOST = __config["db_host"]
DB_PORT = __config["db_port"]

BOT_TOKEN = __config["bot_token"]
GIGACHAT_TOKEN = __config["gigachat_token"]

CHANGE_STATUS_COMMAND = __config["change_status_command"]