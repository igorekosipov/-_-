import aiosqlite
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from datetime import datetime

import database as db
from keyboards import admin_menu, main_menu
from config import ADMIN_IDS, PRIZE_INFO, PRICE, TOTAL_TICKETS

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return

    await message.answer(
        "🔐 АДМИН ПАНЕЛЬ\n\nВыберите действие:",
        reply_markup=admin_menu()
    )


@router.message(F.text == "📋 Ожидают оплаты")
async def pending_payments(message: Message):
    if not is_admin(message.from_user.id):
        return

    async with aiosqlite.connect(db.DATABASE_PATH) as conn:
        cursor = await conn.execute("""
            SELECT id, user_id, ticket_number, receipt_photo, purchase_date
            FROM subscriptions 
            WHERE payment_confirmed = 0
        """)
        pending = await cursor.fetchall()

    if not pending:
        await message.answer("✅ Нет ожидающих оплат")
        return

    for sub_id, user_id, ticket_num, receipt, purchase_date in pending:
        try:
            user = await message.bot.get_chat(user_id)
            username = f"@{user.username}" if user.username else f"ID: {user_id}"
        except:
            username = f"ID: {user_id}"

        text = f"""
📋 ОЖИДАЕТ ПОДТВЕРЖДЕНИЯ
━━━━━━━━━━━━━━━━━━━
🆔 ID подписки: {sub_id}
👤 Пользователь: {username}
🎫 Билет: №{ticket_num}
💰 Сумма: {PRICE}₽
🕐 Дата: {purchase_date}
━━━━━━━━━━━━━━━━━━━
"""
        try:
            await message.bot.send_photo(
                message.chat.id,
                photo=receipt,
                caption=text
            )
        except:
            await message.answer(text)


@router.callback_query(F.data.startswith("confirm_"))
async def confirm_payment(callback: CallbackQuery):
    """✅ ПОДТВЕРЖДЕНИЕ - ДЕНЬГИ ПРИШЛИ"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    sub_id = int(callback.data.split("_")[1])

    sub_info = await db.get_pending_subscription(sub_id)

    if not sub_info:
        await callback.answer("❌ Подписка не найдена", show_alert=True)
        return

    user_id, ticket_num, receipt_photo = sub_info

    sold = await db.confirm_payment(sub_id)

    # Уведомление пользователю
    success_message = f"""
✅✅✅ ОПЛАТА ПОДТВЕРЖДЕНА ✅✅✅

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ваш платеж на сумму {PRICE}₽ УСПЕШНО ПОЛУЧЕН!

🎫 ВАШ БИЛЕТ №{ticket_num} АКТИВИРОВАН!

📊 ПРОДАНО: {sold}/{TOTAL_TICKETS}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🍀 ЖЕЛАЕМ УДАЧИ!
"""

    try:
        await callback.bot.send_message(user_id, success_message, reply_markup=main_menu())
        print(f"✅ Уведомление отправлено пользователю {user_id}")
    except Exception as e:
        print(f"❌ Ошибка уведомления: {e}")

    try:
        await callback.message.edit_caption(
            caption=f"✅ ПОДТВЕРЖДЕНО ✅\nБилет №{ticket_num}\nПродано: {sold}/{TOTAL_TICKETS}"
        )
    except:
        pass

    await callback.answer(f"✅ Оплата подтверждена! Продано {sold}/{TOTAL_TICKETS}")

    # ========== ПРОВЕРКА УСЛОВИЙ ДЛЯ РОЗЫГРЫША ==========
    status = await db.get_current_lottery_status()
    if status:
        sold_count, is_active, started_at = status

        timer_info = await db.get_lottery_timer()
        timer_start, timer_end, is_timer_active = timer_info if timer_info else (None, None, False)

        should_draw = False
        reason = ""

        # УСЛОВИЕ 1: Проданы ВСЕ 100 билетов - МГНОВЕННЫЙ РОЗЫГРЫШ
        if sold_count >= TOTAL_TICKETS and is_active:
            should_draw = True
            reason = "Проданы все 100 билетов"
            if is_timer_active:
                await db.stop_lottery_timer()

        # УСЛОВИЕ 2: Таймер активен и время истекло (4 дня)
        elif is_timer_active and timer_end:
            end_time = datetime.fromisoformat(timer_end) if isinstance(timer_end, str) else timer_end
            if datetime.now() >= end_time:
                should_draw = True
                reason = "Истекло 4 дня"
                await db.stop_lottery_timer()

        # УСЛОВИЕ 3: Продано 60+ и таймер еще не запущен - ЗАПУСКАЕМ ТАЙМЕР
        elif sold_count >= 60 and not is_timer_active and is_active and sold_count < TOTAL_TICKETS:
            await db.start_lottery_timer()
            print(f"✅ ТАЙМЕР ЗАПУЩЕН! Продано {sold_count} билетов")

            for admin_id in ADMIN_IDS:
                try:
                    await callback.bot.send_message(
                        admin_id,
                        f"⏰ ЗАПУЩЕН ТАЙМЕР НА 4 ДНЯ!\n\n"
                        f"Продано {sold_count}/{TOTAL_TICKETS} билетов\n"
                        f"Розыгрыш состоится через 4 дня!\n"
                        f"Если будут проданы все 100 билетов - розыгрыш произойдет сразу!"
                    )
                except:
                    pass

        # Проводим розыгрыш если нужно
        if should_draw:
            winner = await db.start_lottery_draw()
            if winner:
                # Уведомляем победителя
                try:
                    await callback.bot.send_message(
                        winner["user_id"],
                        f"""
🎉🎉🎉 ПОЗДРАВЛЯЕМ! ВЫ ПОБЕДИТЕЛЬ! 🎉🎉🎉

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ВЫ ВЫИГРАЛИ {PRIZE_INFO['name']}!!!

🏆 ВАШ БИЛЕТ №{winner['ticket']} ОКАЗАЛСЯ ПОБЕДНЫМ!

📦 ПРИЗ: {PRIZE_INFO['name']}
📝 ОПИСАНИЕ: {PRIZE_INFO['description']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
С ВАМИ СВЯЖЕТСЯ МЕНЕДЖЕР 
В БЛИЖАЙШЕЕ ВРЕМЯ ДЛЯ ВРУЧЕНИЯ ПРИЗА!

Спасибо за участие! 🙏
"""
                    )
                except Exception as e:
                    print(f"Ошибка уведомления победителя: {e}")

                # Уведомляем админа
                for admin_id in ADMIN_IDS:
                    try:
                        await callback.bot.send_message(
                            admin_id,
                            f"""
🏆🏆🏆 РОЗЫГРЫШ СОСТОЯЛСЯ! 🏆🏆🏆

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ПОБЕДИТЕЛЬ:
👤 ID: {winner['user_id']}
🎫 Билет: №{winner['ticket']}
🏆 Приз: {PRIZE_INFO['name']}

ПРИЧИНА: {reason}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❗️ СВЯЖИТЕСЬ С ПОБЕДИТЕЛЕМ ДЛЯ ВРУЧЕНИЯ ПРИЗА! ❗️
"""
                        )
                    except:
                        pass

                print(f"✅ Розыгрыш проведен! Победитель: билет №{winner['ticket']}")


@router.callback_query(F.data.startswith("reject_"))
async def reject_payment(callback: CallbackQuery):
    """❌ ОТКАЗ - ДЕНЬГИ НЕ ПРИШЛИ"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    sub_id = int(callback.data.split("_")[1])

    sub_info = await db.get_pending_subscription(sub_id)

    if sub_info:
        user_id, ticket_num, receipt_photo = sub_info

        reject_message = f"""
❌❌❌ ОПЛАТА ОТКЛОНЕНА ❌❌❌

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Уважаемый участник!

Ваш платеж на сумму {PRICE}₽ 
НЕ ПОДТВЕРЖДЕН

ПРИЧИНА ОТКАЗА:
• Чек не соответствует требованиям
• Перевод не обнаружен на нашем счету

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ЧТО ДЕЛАТЬ:
1️⃣ Проверьте реквизиты
2️⃣ Отправьте НОВЫЙ, ЧЕТКИЙ чек
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Билет №{ticket_num} НЕ БУДЕТ АКТИВИРОВАН
"""

        try:
            await callback.bot.send_message(user_id, reject_message, reply_markup=main_menu())
            print(f"❌ Уведомление об отказе отправлено пользователю {user_id}")
        except Exception as e:
            print(f"❌ Ошибка отправки уведомления: {e}")

        await db.delete_subscription(sub_id)

        try:
            await callback.message.edit_caption(
                caption=f"❌ ОТКАЗАНО ❌\nБилет №{ticket_num}\nПользователь уведомлен"
            )
        except:
            pass

        await callback.answer("❌ Оплата отклонена!", show_alert=True)
    else:
        await callback.answer("❌ Подписка не найдена", show_alert=True)


@router.message(F.text == "🎲 Запустить розыгрыш")
async def force_draw(message: Message):
    if not is_admin(message.from_user.id):
        return

    winner = await db.start_lottery_draw()

    if winner:
        try:
            await message.bot.send_message(
                winner["user_id"],
                f"""
🎉🎉🎉 ПОЗДРАВЛЯЕМ! ВЫ ПОБЕДИТЕЛЬ! 🎉🎉🎉

ВЫ ВЫИГРАЛИ {PRIZE_INFO['name']}!!!

Ваш билет №{winner['ticket']} оказался победным!

С вами свяжется менеджер в ближайшее время!
"""
            )
        except:
            pass

        await message.answer(
            f"✅ РОЗЫГРЫШ ПРОВЕДЕН!\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Победитель: ID {winner['user_id']}\n"
            f"Билет: №{winner['ticket']}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Победитель получил уведомление!"
        )
    else:
        await message.answer("❌ Нет активных билетов для розыгрыша")


@router.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    status = await db.get_current_lottery_status()
    tickets = await db.get_all_active_tickets()

    async with aiosqlite.connect(db.DATABASE_PATH) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM subscriptions WHERE payment_confirmed = 0")
        pending_count = (await cursor.fetchone())[0]

    sold = status[0] if status else 0

    # Получаем статус таймера
    timer_info = await db.get_timer_status()
    timer_active, timer_end = timer_info if timer_info else (False, None)

    timer_text = ""
    if timer_active and timer_end:
        end_time = datetime.fromisoformat(timer_end) if isinstance(timer_end, str) else timer_end
        time_left = end_time - datetime.now()
        days = time_left.days
        hours = time_left.seconds // 3600
        minutes = (time_left.seconds % 3600) // 60
        timer_text = f"\n⏰ ДО РОЗЫГРЫША: {days}д {hours}ч {minutes}мин"

    stats = f"""
📊 СТАТИСТИКА БОТА
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎫 АКТИВНЫХ БИЛЕТОВ: {len(tickets)}
🎰 ПРОДАНО БИЛЕТОВ: {sold}/{TOTAL_TICKETS}
✨ ОСТАЛОСЬ: {TOTAL_TICKETS - sold}
👥 УЧАСТНИКОВ: {len(set([t[0] for t in tickets]))}
⏳ ОЖИДАЮТ ОПЛАТЫ: {pending_count}{timer_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 СОБРАНО СРЕДСТВ: {len(tickets) * PRICE}₽
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    await message.answer(stats)
