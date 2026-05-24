import aiosqlite
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from datetime import datetime

import database as db
from keyboards import admin_menu, main_menu
from config import ADMIN_IDS, PRIZE_INFO, PRICE_FIRST, PRICE_DISCOUNT, TOTAL_TICKETS

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
            SELECT id, user_id, ticket_number, receipt_photo, purchase_date, price_paid
            FROM subscriptions 
            WHERE payment_confirmed = 0
        """)
        pending = await cursor.fetchall()

    if not pending:
        await message.answer("✅ Нет ожидающих оплат")
        return

    for sub_id, user_id, ticket_num, receipt, purchase_date, price in pending:
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
💰 Сумма: {price}₽
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
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    sub_id = int(callback.data.split("_")[1])
    sub_info = await db.get_pending_subscription(sub_id)

    if not sub_info:
        await callback.answer("❌ Подписка не найдена", show_alert=True)
        return

    user_id, ticket_num, receipt_photo, price = sub_info
    
    sold, buyer_id, bought_ticket = await db.confirm_payment(sub_id)
    
    # Отмечаем, что реферал купил билет
    await db.mark_referral_bought(user_id)

    # Проверяем акции
    free_ticket_20 = await db.check_and_give_free_ticket(user_id, callback.bot)
    physical_prize_70 = await db.check_and_give_physical_prize(user_id)

    # Проверяем, не пришел ли пользователь по реферальной ссылке
    async with aiosqlite.connect(db.DATABASE_PATH) as conn:
        cursor = await conn.execute("""
            SELECT referrer_id FROM users WHERE user_id = ?
        """, (user_id,))
        referrer_data = await cursor.fetchone()
        
        if referrer_data and referrer_data[0]:
            referrer_id = referrer_data[0]
            await db.mark_referral_free_ticket_given(referrer_id, user_id)
            # Уведомляем реферера о бесплатном билете
            try:
                await callback.bot.send_message(
                    referrer_id,
                    f"🎉 ПОЗДРАВЛЯЕМ!\n\n"
                    f"Ваш друг @{callback.from_user.username or 'пользователь'} купил билет!\n"
                    f"Вы получили БЕСПЛАТНЫЙ БИЛЕТ на выбор!\n\n"
                    f"Напишите /free_ticket чтобы получить билет."
                )
            except:
                pass

    # Уведомление пользователю
    success_message = f"""
✅ ОПЛАТА ПОДТВЕРЖДЕНА ✅

Ваш билет №{ticket_num} АКТИВИРОВАН!

💰 Оплачено: {price}₽
📊 Продано: {sold}/{TOTAL_TICKETS}
"""

    if free_ticket_20:
        success_message += f"\n🎉 ПОЗДРАВЛЯЕМ! Вы купили 20 билетов!\nПолучите БЕСПЛАТНЫЙ БИЛЕТ в разделе 'Акции'!"
    
    if physical_prize_70:
        success_message += f"\n🏆 ПОЗДРАВЛЯЕМ! Вы купили 70 билетов!\nСвяжитесь с менеджером для получения физического приза!"

    try:
        await callback.bot.send_message(user_id, success_message, reply_markup=main_menu())
    except:
        pass

    await callback.message.edit_caption(
        caption=f"✅ ПОДТВЕРЖДЕНО ✅\nБилет №{ticket_num}\nПродано: {sold}/{TOTAL_TICKETS}\nСумма: {price}₽"
    )

    await callback.answer(f"✅ Оплата подтверждена! Продано {sold}/{TOTAL_TICKETS}")

    # Проверка условий для розыгрыша
    status = await db.get_current_lottery_status()
    if status:
        sold_count, is_active, started_at = status
        timer_info = await db.get_lottery_timer()
        timer_start, timer_end, is_timer_active = timer_info if timer_info else (None, None, False)
        
        should_draw = False
        reason = ""
        
        if sold_count >= TOTAL_TICKETS and is_active:
            should_draw = True
            reason = "Проданы все 150 билетов"
            if is_timer_active:
                await db.stop_lottery_timer()
        
        elif is_timer_active and timer_end:
            end_time = datetime.fromisoformat(timer_end) if isinstance(timer_end, str) else timer_end
            if datetime.now() >= end_time:
                should_draw = True
                reason = "Истекло 4 дня"
                await db.stop_lottery_timer()
        
        elif sold_count >= 60 and not is_timer_active and is_active and sold_count < TOTAL_TICKETS:
            await db.start_lottery_timer()
            for admin_id in ADMIN_IDS:
                try:
                    await callback.bot.send_message(
                        admin_id,
                        f"⏰ ЗАПУЩЕН ТАЙМЕР НА 4 ДНЯ!\n\n"
                        f"Продано {sold_count}/{TOTAL_TICKETS} билетов\n"
                        f"Розыгрыш состоится через 4 дня!"
                    )
                except:
                    pass
        
        if should_draw:
            winner = await db.start_lottery_draw()
            if winner:
                try:
                    await callback.bot.send_message(
                        winner["user_id"],
                        f"""
🎉🎉🎉 ПОЗДРАВЛЯЕМ! ВЫ ПОБЕДИТЕЛЬ! 🎉🎉🎉

ВЫ ВЫИГРАЛИ {PRIZE_INFO['name']}!!!

Ваш билет №{winner['ticket']} оказался победным!

С вами свяжется менеджер для вручения приза!
"""
                    )
                except:
                    pass

                for admin_id in ADMIN_IDS:
                    try:
                        await callback.bot.send_message(
                            admin_id,
                            f"""
🏆🏆🏆 РОЗЫГРЫШ СОСТОЯЛСЯ! 🏆🏆🏆

ПОБЕДИТЕЛЬ: ID {winner['user_id']}
Билет: №{winner['ticket']}
Приз: {PRIZE_INFO['name']}

ПРИЧИНА: {reason}

❗️ СВЯЖИТЕСЬ С ПОБЕДИТЕЛЕМ! ❗️
"""
                        )
                    except:
                        pass


@router.callback_query(F.data.startswith("reject_"))
async def reject_payment(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    sub_id = int(callback.data.split("_")[1])
    sub_info = await db.get_pending_subscription(sub_id)

    if sub_info:
        user_id, ticket_num, receipt_photo, price = sub_info

        reject_message = f"""
❌ ОПЛАТА ОТКЛОНЕНА ❌

Билет №{ticket_num} НЕ БУДЕТ АКТИВИРОВАН.

Причина: чек не прошел проверку.

Пожалуйста, отправьте четкий чек заново.
"""

        try:
            await callback.bot.send_message(user_id, reject_message, reply_markup=main_menu())
        except:
            pass

        await db.delete_subscription(sub_id)

        await callback.message.edit_caption(
            caption=f"❌ ОТКАЗАНО ❌\nБилет №{ticket_num}\nПользователь уведомлен"
        )

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
        
        cursor = await conn.execute("SELECT COUNT(*) FROM users")
        users_count = (await cursor.fetchone())[0]
        
        cursor = await conn.execute("SELECT SUM(price_paid) FROM subscriptions WHERE payment_confirmed = 1")
        total_revenue = (await cursor.fetchone())[0] or 0

    sold = status[0] if status else 0

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
👥 ВСЕГО ПОЛЬЗОВАТЕЛЕЙ: {users_count}
🎫 АКТИВНЫХ БИЛЕТОВ: {len(tickets)}
🎰 ПРОДАНО БИЛЕТОВ: {sold}/{TOTAL_TICKETS}
✨ ОСТАЛОСЬ: {TOTAL_TICKETS - sold}
⏳ ОЖИДАЮТ ОПЛАТЫ: {pending_count}{timer_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 СОБРАНО СРЕДСТВ: {total_revenue}₽
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎁 ЦЕНЫ:
• Первый билет: {PRICE_FIRST}₽
• Последующие: {PRICE_DISCOUNT}₽
"""
    await message.answer(stats)


@router.message(F.text == "🗑 Сбросить все билеты")
async def reset_all_tickets(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    async with aiosqlite.connect(db.DATABASE_PATH) as conn:
        await conn.execute("DELETE FROM subscriptions WHERE payment_confirmed = 0")
        await conn.execute("UPDATE current_lottery SET tickets_sold = 0 WHERE id = 1")
        await conn.commit()
    
    await message.answer("✅ ВСЕ ДАННЫЕ СБРОШЕНЫ!\n\nВсе билеты очищены, счетчик обнулен.")
