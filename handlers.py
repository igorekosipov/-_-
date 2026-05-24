import aiosqlite
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime

import database as db
from keyboards import main_menu, confirm_payment_keyboard
from states import PaymentStates
from config import PRIZE_INFO, PRICE_FIRST, PRICE_DISCOUNT, TOTAL_TICKETS

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].split("_")[1])
            if referrer_id == message.from_user.id:
                referrer_id = None
        except:
            pass
    
    await state.clear()
    await db.add_user(
        message.from_user.id, 
        message.from_user.username, 
        message.from_user.full_name,
        referrer_id
    )
    
    if referrer_id and referrer_id != message.from_user.id:
        await db.add_referral(referrer_id, message.from_user.id)
    
    await db.cleanup_expired_subscriptions()
    
    welcome_text = """
🎉 Добро пожаловать в розыгрыш ценных призов!

🎁 Еженедельные розыгрыши с реальными призами
💫 Честно и прозрачно
🚚 Доставка СДЭК по всей России

🎁 АКЦИИ:
• Первый билет — 700₽
• Последующие билеты — 600₽
• Приведи друга → получи бесплатный билет
• Купи 20 билетов → бесплатный билет
• Купи 70 билетов → физический приз в подарок!

Используйте меню для навигации
"""
    await message.answer(welcome_text, reply_markup=main_menu())


@router.message(F.text == "📋 Правила")
async def show_rules(message: Message):
    rules = """
📜 ПРАВИЛА РОЗЫГРЫША

✅ Все честно и без обмана
✅ Розыгрыш проводится рандомно
✅ Если вы находитесь не в Бийске, выигрыш отправится СДЭКом до вашего города
✅ Приз высылается в течение 3 дней после розыгрыша

Как участвовать:
1. Оформите подписку на бота
2. В подарок вы получаете лотерейный билет
3. Ждите розыгрыша и забирайте приз!

ЦЕНЫ:
• Первый билет — 700₽
• Все последующие билеты — 600₽
"""
    await message.answer(rules, reply_markup=main_menu())


@router.message(F.text == "📦 Как получить приз")
async def how_to_get_prize(message: Message):
    text = """
🎁 КАК ПОЛУЧИТЬ ПРИЗ:

1️⃣ После розыгрыша победителю приходит уведомление
2️⃣ С вами свяжется менеджер в течение 24 часов
3️⃣ Менеджер уточнит данные для отправки
4️⃣ Приз отправляется СДЭКом в течение 3 дней

Для связи с менеджером: @manager_username
"""
    await message.answer(text, reply_markup=main_menu())


@router.message(F.text == "🎁 Розыгрыш")
async def show_lottery(message: Message):
    try:
        status = await db.get_current_lottery_status()
        if not status:
            await message.answer("❌ Розыгрыш временно недоступен")
            return

        sold, is_active, started_at = status

        async with aiosqlite.connect(db.DATABASE_PATH) as conn:
            cursor = await conn.execute(
                "SELECT ticket_number FROM subscriptions WHERE payment_confirmed = 1 AND expires_at > ?",
                (datetime.now(),)
            )
            taken_rows = await cursor.fetchall()
            taken = set([row[0] for row in taken_rows])

        available = [num for num in range(1, TOTAL_TICKETS + 1) if num not in taken]
        
        user_ticket_count = await db.get_user_ticket_count(message.from_user.id)
        price = PRICE_FIRST if user_ticket_count == 0 else PRICE_DISCOUNT
        
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        
        buttons = []

        # 19 СТРОК ПО 8 БИЛЕТОВ = 152 (покажем 150)
        # Номера билетов: 1-8, 9-16, 17-24, ... до 145-152 (покажем до 150)
        for row in range(19):  # 0-18 = 19 строк
            row_buttons = []
            for col in range(1, 9):  # 1-8 = 8 кнопок в строке
                ticket_num = row * 8 + col
                if ticket_num <= TOTAL_TICKETS:
                    if ticket_num in taken:
                        row_buttons.append(InlineKeyboardButton(text=f"🔒", callback_data="sold"))
                    else:
                        row_buttons.append(InlineKeyboardButton(text=str(ticket_num), callback_data=f"buy_{ticket_num}"))
            if row_buttons:  # добавляем строку только если есть кнопки
                buttons.append(row_buttons)
        
        buttons.append([
            InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        ])
        
        timer_info = await db.get_lottery_timer()
        timer_start, timer_end, is_timer_active = timer_info if timer_info else (None, None, False)
        
        timer_text = ""
        if is_timer_active and timer_end:
            end_time = datetime.fromisoformat(timer_end) if isinstance(timer_end, str) else timer_end
            time_left = end_time - datetime.now()
            days = time_left.days
            hours = time_left.seconds // 3600
            minutes = (time_left.seconds % 3600) // 60
            if days > 0:
                timer_text = f"⏰ ДО РОЗЫГРЫША: {days}д {hours}ч {minutes}мин"
            else:
                timer_text = f"⏰ ДО РОЗЫГРЫША: {hours}ч {minutes}мин"
        
        lottery_text = f"""
🎰 АКТУАЛЬНЫЙ РОЗЫГРЫШ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 ПРИЗ: {PRIZE_INFO['name']}
📝 ОПИСАНИЕ: {PRIZE_INFO['description']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎫 ПРОДАНО: {sold}/{TOTAL_TICKETS}
✨ ДОСТУПНО: {len(available)}
💰 ЦЕНА БИЛЕТА: {price}₽
{timer_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 Ваш баланс билетов: {user_ticket_count}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👇 ВЫБЕРИТЕ НОМЕР БИЛЕТА (1-150):
"""
        
        await message.answer(
            lottery_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )

    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
        print(f"Ошибка: {e}")

@router.callback_query(F.data.startswith("buy_"))
async def buy_ticket(callback: CallbackQuery, state: FSMContext):
    try:
        ticket_num = int(callback.data.split("_")[1])

        async with aiosqlite.connect(db.DATABASE_PATH) as conn:
            cursor = await conn.execute(
                "SELECT id FROM subscriptions WHERE ticket_number = ? AND payment_confirmed = 1 AND expires_at > ?",
                (ticket_num, datetime.now())
            )
            if await cursor.fetchone():
                await callback.answer("❌ Этот билет уже куплен!", show_alert=True)
                return

        user_ticket_count = await db.get_user_ticket_count(callback.from_user.id)
        price = PRICE_FIRST if user_ticket_count == 0 else PRICE_DISCOUNT
        
        await state.update_data(ticket_number=ticket_num, price=price)

        payment_text = f"""
💳 ОФОРМЛЕНИЕ ПОДПИСКИ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Вы выбрали билет №{ticket_num}

🏦 РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ:
Сбербанк: 1234 5678 9012 3456
Получатель: Иванов Иван Иванович
Сумма: {price} рублей
Назначение: Подписка на бота 10 дней

⚠️ ВАЖНО: После оплаты отправьте чек в этот чат.
"""

        await callback.message.delete()
        await callback.message.answer(payment_text)
        await state.set_state(PaymentStates.waiting_for_receipt)
        await callback.answer()

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data == "cancel")
async def cancel_purchase(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("❌ Покупка отменена", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "refresh")
async def refresh_lottery(callback: CallbackQuery):
    await callback.message.delete()
    await show_lottery(callback.message)
    await callback.answer()


@router.callback_query(F.data == "sold")
async def sold_ticket(callback: CallbackQuery):
    await callback.answer("❌ Этот билет уже продан!", show_alert=True)


@router.message(PaymentStates.waiting_for_receipt, F.photo)
async def handle_receipt(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        ticket_num = data.get("ticket_number")
        price = data.get("price", PRICE_FIRST)

        if not ticket_num:
            await message.answer("❌ Ошибка: начните заново", reply_markup=main_menu())
            await state.clear()
            return

        photo = message.photo[-1]
        file_id = photo.file_id

        await db.add_subscription(message.from_user.id, ticket_num, file_id, price)

        async with aiosqlite.connect(db.DATABASE_PATH) as conn:
            cursor = await conn.execute(
                "SELECT id FROM subscriptions WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                (message.from_user.id,)
            )
            sub_id = (await cursor.fetchone())[0]

        from config import ADMIN_IDS
        admin_text = f"""
📥 НОВАЯ ОПЛАТА ОЖИДАЕТ ПРОВЕРКИ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 Пользователь: @{message.from_user.username or message.from_user.full_name}
🆔 ID: {message.from_user.id}
🎫 Билет №{ticket_num}
💰 Сумма: {price}₽
🕐 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_photo(
                    admin_id,
                    photo=file_id,
                    caption=admin_text,
                    reply_markup=confirm_payment_keyboard(sub_id)
                )
            except Exception as e:
                print(f"Ошибка: {e}")

        await message.answer(
            "✅ Чек отправлен на проверку!\nМенеджер проверит оплату в ближайшее время.",
            reply_markup=main_menu()
        )
        await state.clear()

    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(PaymentStates.waiting_for_receipt)
async def invalid_receipt(message: Message):
    await message.answer(
        "❌ Пожалуйста, отправьте ФОТО чека об оплате.",
        reply_markup=main_menu()
    )


@router.message(F.text == "🎫 Купленные билеты")
async def show_my_tickets(message: Message):
    try:
        tickets = await db.get_user_tickets(message.from_user.id)
        ticket_count = await db.get_user_ticket_count(message.from_user.id)

        if not tickets:
            await message.answer(
                "📭 У вас пока нет активных билетов.\n\n"
                f"💰 Всего куплено билетов за всё время: {ticket_count}\n"
                f"🎯 До следующей акции: {20 - ticket_count if ticket_count < 20 else 0} билетов до бесплатного билета\n"
                f"🏆 До физического приза: {70 - ticket_count if ticket_count < 70 else 0} билетов",
                reply_markup=main_menu()
            )
            return

        text = f"🎫 ВАШИ АКТИВНЫЕ БИЛЕТЫ:\n━━━━━━━━━━━━━━━━━\n"
        for ticket_num, purchase_date, confirmed in tickets:
            if confirmed:
                date_str = datetime.fromisoformat(purchase_date).strftime('%d.%m.%Y')
                text += f"🔸 Билет №{ticket_num} (куплен {date_str})\n"
        
        text += f"\n📊 ВСЕГО КУПЛЕНО: {ticket_count} билетов"

        await message.answer(text, reply_markup=main_menu())

    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(F.text == "🏆 Последний билет")
async def last_draw_winner(message: Message):
    try:
        winner = await db.get_last_winner()
        
        if winner:
            winner_id, winner_ticket, draw_date = winner
            date_str = datetime.fromisoformat(draw_date).strftime('%d.%m.%Y %H:%M')
            
            await message.answer(
                f"🏆 ПОСЛЕДНИЙ РОЗЫГРЫШ\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🎲 ВЫИГРЫШНЫЙ БИЛЕТ: №{winner_ticket}\n"
                f"📅 ДАТА: {date_str}\n"
                f"🎁 ПРИЗ: {PRIZE_INFO['name']}",
                reply_markup=main_menu()
            )
        else:
            await message.answer(
                "📭 Пока не было проведено ни одного розыгрыша.",
                reply_markup=main_menu()
            )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.message(F.text == "🎁 Акции")
async def show_promotions(message: Message):
    ticket_count = await db.get_user_ticket_count(message.from_user.id)
    
    text = f"""
🎁 АКТУАЛЬНЫЕ АКЦИИ 🎁
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ ПЕРВЫЙ БИЛЕТ СО СКИДКОЙ
• Первый билет — 700₽
• Последующие билеты — 600₽

2️⃣ ПРИВЕДИ ДРУГА
• Приведи друга, который купит билет
• Ты получишь БЕСПЛАТНЫЙ билет на выбор
• Друг получит скидку 600₽ на билет

3️⃣ ЗА 20 КУПЛЕННЫХ БИЛЕТОВ
• Бесплатный билет на следующий розыгрыш
• Ваш прогресс: {ticket_count}/20

4️⃣ ЗА 70 КУПЛЕННЫХ БИЛЕТОВ
• Бесплатный физический приз (рандомный)
• Ваш прогресс: {ticket_count}/70

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💫 Активируйте акции, участвуя в розыгрышах!
"""
    await message.answer(text, reply_markup=main_menu())


@router.message(F.text == "👥 Реферальная ссылка")
async def show_referral(message: Message):
    user_id = message.from_user.id
    bot_username = (await message.bot.get_me()).username
    
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    referrals_count = await db.get_referrals_count(user_id)
    referrals_list = await db.get_referral_list(user_id)
    
    text = f"""
👥 РЕФЕРАЛЬНАЯ ПРОГРАММА 👥
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔗 ВАША РЕФЕРАЛЬНАЯ ССЫЛКА:
`{referral_link}`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 СТАТИСТИКА:
• Приглашено друзей: {len(referrals_list)}
• Из них купили билет: {referrals_count}

🎁 ВОЗНАГРАЖДЕНИЕ:
За каждого друга, который купит билет:
• ВЫ получаете БЕСПЛАТНЫЙ билет
• ДРУГ получает скидку 600₽ на билет

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👥 ПРИГЛАШЕННЫЕ ДРУЗЬЯ:
"""
    
    if referrals_list:
        for ref_id, username, bought, date in referrals_list[-5:]:
            status = "✅ купил" if bought else "⏳ ожидает"
            username_str = f"@{username}" if username else f"ID:{ref_id}"
            text += f"\n• {username_str} — {status}"
    else:
        text += "\nПока нет приглашенных друзей"
    
    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu())
