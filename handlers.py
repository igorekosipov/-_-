import aiosqlite
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from datetime import datetime

import database as db
from keyboards import main_menu, ticket_selection_keyboard, confirm_payment_keyboard
from states import PaymentStates
from config import PRIZE_INFO, PRICE, PAYMENT_DETAILS, TOTAL_TICKETS

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    await db.cleanup_expired_subscriptions()

    welcome_text = """
🎉 Добро пожаловать в розыгрыш ценных призов!

🎁 Еженедельные розыгрыши с реальными призами
💫 Честно и прозрачно
🚚 Доставка СДЭК по всей России

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
1. Оформите подписку на бота (700₽/10 дней)
2. В подарок вы получаете лотерейный билет
3. Отсчет по рулетке начинается после купленных 60 билетов (4дня), если все 100 билеты были выкуплены, рулетка начинается сразу
3. Ждите розыгрыша и забирайте приз!
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

Для связи с менеджером: @IgoroOsipov1
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

        from config import TOTAL_TICKETS
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        # ========== ПОЛУЧАЕМ СТАТУС ТАЙМЕРА ==========
        timer_info = await db.get_lottery_timer()
        timer_start, timer_end, is_timer_active = timer_info if timer_info else (None, None, False)

        # ФОРМИРУЕМ ТЕКСТ ТАЙМЕРА
        timer_text = ""
        time_left_text = ""

        if is_timer_active and timer_end:
            end_time = datetime.fromisoformat(timer_end) if isinstance(timer_end, str) else timer_end
            time_left = end_time - datetime.now()

            if time_left.total_seconds() > 0:
                days = time_left.days
                hours = time_left.seconds // 3600
                minutes = (time_left.seconds % 3600) // 60
                seconds = time_left.seconds % 60

                if days > 0:
                    time_left_text = f"⏰ {days}д {hours}ч {minutes}мин {seconds}с"
                elif hours > 0:
                    time_left_text = f"⏰ {hours}ч {minutes}мин {seconds}с"
                elif minutes > 0:
                    time_left_text = f"⏰ {minutes}мин {seconds}с"
                else:
                    time_left_text = f"⏰ {seconds}с"

                timer_text = f"\n⏳ ДО РОЗЫГРЫША ОСТАЛОСЬ: {time_left_text}"
            else:
                timer_text = "\n🎲 РОЗЫГРЫШ БУДЕТ ПРОВЕДЕН В БЛИЖАЙШЕЕ ВРЕМЯ!"
        elif sold >= 60 and not is_timer_active and sold < TOTAL_TICKETS:
            timer_text = "\n⏳ ТАЙМЕР ЗАПУСТИТСЯ ПРИ ДОСТИЖЕНИИ 60 ПРОДАННЫХ БИЛЕТОВ!"
        elif sold >= TOTAL_TICKETS:
            timer_text = "\n🎲 ВСЕ БИЛЕТЫ ПРОДАНЫ! РОЗЫГРЫШ СОСТОИТСЯ СЕЙЧАС!"

        # СОЗДАЕМ КНОПКИ (8x8 + 4)
        buttons = []

        # 1-8
        row1 = []
        for i in range(1, 9):
            if i in taken:
                row1.append(InlineKeyboardButton(text=f"🔒{i}", callback_data="sold"))
            else:
                row1.append(InlineKeyboardButton(text=str(i), callback_data=f"buy_{i}"))
        buttons.append(row1)

        # 9-16
        row2 = []
        for i in range(9, 17):
            if i in taken:
                row2.append(InlineKeyboardButton(text=f"🔒{i}", callback_data="sold"))
            else:
                row2.append(InlineKeyboardButton(text=str(i), callback_data=f"buy_{i}"))
        buttons.append(row2)

        # 17-24
        row3 = []
        for i in range(17, 25):
            if i in taken:
                row3.append(InlineKeyboardButton(text=f"🔒{i}", callback_data="sold"))
            else:
                row3.append(InlineKeyboardButton(text=str(i), callback_data=f"buy_{i}"))
        buttons.append(row3)

        # 25-32
        row4 = []
        for i in range(25, 33):
            if i in taken:
                row4.append(InlineKeyboardButton(text=f"🔒{i}", callback_data="sold"))
            else:
                row4.append(InlineKeyboardButton(text=str(i), callback_data=f"buy_{i}"))
        buttons.append(row4)

        # 33-40
        row5 = []
        for i in range(33, 41):
            if i in taken:
                row5.append(InlineKeyboardButton(text=f"🔒{i}", callback_data="sold"))
            else:
                row5.append(InlineKeyboardButton(text=str(i), callback_data=f"buy_{i}"))
        buttons.append(row5)

        # 41-48
        row6 = []
        for i in range(41, 49):
            if i in taken:
                row6.append(InlineKeyboardButton(text=f"🔒{i}", callback_data="sold"))
            else:
                row6.append(InlineKeyboardButton(text=str(i), callback_data=f"buy_{i}"))
        buttons.append(row6)

        # 49-56
        row7 = []
        for i in range(49, 57):
            if i in taken:
                row7.append(InlineKeyboardButton(text=f"🔒{i}", callback_data="sold"))
            else:
                row7.append(InlineKeyboardButton(text=str(i), callback_data=f"buy_{i}"))
        buttons.append(row7)

        # 57-64
        row8 = []
        for i in range(57, 65):
            if i in taken:
                row8.append(InlineKeyboardButton(text=f"🔒{i}", callback_data="sold"))
            else:
                row8.append(InlineKeyboardButton(text=str(i), callback_data=f"buy_{i}"))
        buttons.append(row8)

        # 65-72
        row9 = []
        for i in range(65, 73):
            if i in taken:
                row9.append(InlineKeyboardButton(text=f"🔒{i}", callback_data="sold"))
            else:
                row9.append(InlineKeyboardButton(text=str(i), callback_data=f"buy_{i}"))
        buttons.append(row9)

        # 73-80
        row10 = []
        for i in range(73, 81):
            if i in taken:
                row10.append(InlineKeyboardButton(text=f"🔒{i}", callback_data="sold"))
            else:
                row10.append(InlineKeyboardButton(text=str(i), callback_data=f"buy_{i}"))
        buttons.append(row10)

        # 81-88
        row11 = []
        for i in range(81, 89):
            if i in taken:
                row11.append(InlineKeyboardButton(text=f"🔒{i}", callback_data="sold"))
            else:
                row11.append(InlineKeyboardButton(text=str(i), callback_data=f"buy_{i}"))
        buttons.append(row11)

        # 89-96
        row12 = []
        for i in range(89, 97):
            if i in taken:
                row12.append(InlineKeyboardButton(text=f"🔒{i}", callback_data="sold"))
            else:
                row12.append(InlineKeyboardButton(text=str(i), callback_data=f"buy_{i}"))
        buttons.append(row12)

        # 97-100
        row13 = []
        for i in range(97, 101):
            if i in taken:
                row13.append(InlineKeyboardButton(text=f"🔒{i}", callback_data="sold"))
            else:
                row13.append(InlineKeyboardButton(text=str(i), callback_data=f"buy_{i}"))
        buttons.append(row13)

        # Кнопки управления
        buttons.append([
            InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        ])

        lottery_text = f"""
🎰 АКТУАЛЬНЫЙ РОЗЫГРЫШ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 ПРИЗ: {PRIZE_INFO['name']}
📝 ОПИСАНИЕ: {PRIZE_INFO['description']}
💰 СТОИМОСТЬ: {PRICE}₽
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎫 ПРОДАНО: {sold}/{TOTAL_TICKETS}
✨ ДОСТУПНО: {TOTAL_TICKETS - sold}{timer_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👇 ВЫБЕРИТЕ НОМЕР БИЛЕТА (1-100):
"""

        await message.answer_photo(
            photo=PRIZE_INFO["photo"],
            caption=lottery_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )

    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
        print(f"Ошибка: {e}")

        @router.callback_query(F.data == "refresh")
        async def refresh_lottery(callback: CallbackQuery):
            """Обновить список билетов и таймер"""
            await callback.message.delete()
            await show_lottery(callback.message)
            await callback.answer()

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

        await state.update_data(ticket_number=ticket_num)

        payment_text = f"""
💳 ОФОРМЛЕНИЕ ПОДПИСКИ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Вы выбрали билет №{ticket_num}

Стоимость подписки на 10 дней: {PRICE}₽
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{PAYMENT_DETAILS}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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


@router.message(PaymentStates.waiting_for_receipt, F.photo)
async def handle_receipt(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        ticket_num = data.get("ticket_number")

        if not ticket_num:
            await message.answer("❌ Ошибка: начните заново", reply_markup=main_menu())
            await state.clear()
            return

        photo = message.photo[-1]
        file_id = photo.file_id

        await db.add_subscription(message.from_user.id, ticket_num, file_id)

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
💰 Сумма: {PRICE}₽
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

        if not tickets:
            await message.answer(
                "📭 У вас пока нет активных билетов.\nКупите подписку в разделе 'Розыгрыш'!",
                reply_markup=main_menu()
            )
            return

        text = "🎫 ВАШИ АКТИВНЫЕ БИЛЕТЫ:\n━━━━━━━━━━━━━━━━━\n"
        for ticket_num, purchase_date, confirmed in tickets:
            if confirmed:
                date_str = datetime.fromisoformat(purchase_date).strftime('%d.%m.%Y')
                text += f"🔸 Билет №{ticket_num} (куплен {date_str})\n"

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

            # Пытаемся получить username победителя
            try:
                user = await message.bot.get_chat(winner_id)
                username = f"@{user.username}" if user.username else f"ID: {winner_id}"
            except:
                username = f"ID: {winner_id}"

            await message.answer(
                f"🏆 ПОСЛЕДНИЙ РОЗЫГРЫШ\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🎲 ВЫИГРЫШНЫЙ БИЛЕТ: №{winner_ticket}\n"
                f"👤 ПОБЕДИТЕЛЬ: {username}\n"
                f"📅 ДАТА: {date_str}\n"
                f"🎁 ПРИЗ: {PRIZE_INFO['name']}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                reply_markup=main_menu()
            )
        else:
            await message.answer(
                "📭 Пока не было проведено ни одного розыгрыша.\n\n"
                "Первый розыгрыш состоится когда:\n"
                "• Будет продано 60+ билетов и\n"
                "• Пройдёт обратный отсчет 4 дня или\n"
                "• Будут проданы все 100 билетов",
                reply_markup=main_menu()
            )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
