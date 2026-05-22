import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import database as db
import handlers
import admin_handlers
from config import BOT_TOKEN
from lottery import check_and_run_lottery

# Включаем логирование чтобы видеть ошибки
logging.basicConfig(level=logging.INFO)


async def main():
    # Создаем бота
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Создаем базу данных
    await db.init_db()

    # Подключаем все обработчики
    dp.include_router(handlers.router)
    dp.include_router(admin_handlers.router)

    # Запускаем фоновую задачу для проверки розыгрыша
    asyncio.create_task(check_and_run_lottery(bot))

    # Запускаем бота
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
