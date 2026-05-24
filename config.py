import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

PAYMENT_DETAILS = """
🏦 РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ:
Т-Банк: 2200 7004 3556 8828
Получатель: Наталья О.
Сумма: 800 рублей (первый билет)
Сумма со скидкой: 700 рублей (последующие билеты)
Назначение: Подписка на бота 10 дней
"""

PRIZE_INFO = {
    "name": "Sony PlayStation 5",
    "description": "Игровая консоль",
    "photo": "https://iprofishop.ru/upload/iblock/52a/jq7d52ur5reyrkneywl1ex7yqudxoi2m.png"
}

PRICE_FIRST = 800
PRICE_DISCOUNT = 700
TOTAL_TICKETS = 100
