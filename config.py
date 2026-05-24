import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

PAYMENT_DETAILS = """
🏦 РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ:
Сбербанк: 1234 5678 9012 3456
Получатель: Иванов Иван Иванович
Сумма: 700 рублей (первый билет)
Сумма со скидкой: 600 рублей (последующие билеты)
Назначение: Подписка на бота 10 дней
"""

PRIZE_INFO = {
    "name": "Sony PlayStation 5",
    "description": "Игровая консоль нового поколения",
    "photo": ""
}

PRICE_FIRST = 700
PRICE_DISCOUNT = 600
TOTAL_TICKETS = 150
