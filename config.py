import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

PAYMENT_DETAILS = """
🏦 РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ:
Т-Банк: 2200 7004 3556 8828
Получатель: NATALIYA O.
Сумма: 700 рублей
Назначение: Подписка на бота 10 дней
"""

PRIZE_INFO = {
    "name": "Sony PlayStation 5",
    "description": "Игровая консоль",
    "photo": "https://playboom.ru/upload/iblock/164/yl282l57qbi7kj9zoxnubssu4osvewpi/1.webp"
}

PRICE = 700
TOTAL_TICKETS = 100
