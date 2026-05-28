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


# ========== ОТМЕНА ЛЮБОГО СОСТОЯНИЯ ==========
@router.message(Command("cancel"))
async def cancel_all(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("✅ Действие отменено. Возврат в главное меню.", reply_markup=main_menu())


# ========== СТАРТ ==========
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].split("_")[1])
            if referrer_id == message.from_user.id:
                referrer_id = None
        except:
            pass

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

🎁 Розыгрыши с реальными призами
💫 Честно и прозрачно
🚚 Доставка СДЭК по всей России

🎁 АКЦИИ:
• Первая подписка — 800₽ (в подарок билет)
• Последующие подписки — 700₽ (в подарок билет)
• Приведи 5 друзей → получи бесплатный билет
• Друзья получат первую подписку за 500₽

Используйте меню для навигации
"""
    await message.answer(welcome_text, reply_markup=main_menu())


# ========== ПРАВИЛА ==========
@router.message(F.text == "📋 Правила")
async def show_rules(message: Message, state: FSMContext):
    await state.clear()
    rules = """
📜 ПРАВИЛА РОЗЫГРЫША

✅ Все честно и без обмана
✅ Розыгрыш проводится рандомно
✅ Если вы находитесь не в Бийске, выигрыш отправится СДЭКом до вашего города
✅ Приз высылается в течение 3 дней после розыгрыша

Как участвовать:
1. Оформите подписку на бота (в подарок получаете лотерейный билет)
2. Ждите розыгрыша
3. Забирайте приз!

ЦЕНЫ ПОДПИСОК:
• Первая подписка — 800₽ (билет в подарок)
• Последующие подписки — 700₽ (билет в подарок)
• Для приведённых друзей: первая подписка — 500₽
"""
    await message.answer(rules, reply_markup=main_menu())


# ========== КАК ПОЛУЧИТЬ ПРИЗ ==========
@router.message(F.text == "📦 Как получить приз")
async def how_to_get_prize(message: Message, state: FSMContext):
    await state.clear()
    text = """
🎁 КАК ПОЛУЧИТЬ ПРИЗ:

1️⃣ После розыгрыша победителю приходит уведомление
2️⃣ С вами свяжется менеджер в течение 24 часов
3️⃣ Менеджер уточнит данные для отправки
4️⃣ Приз отправляется СДЭКом в течение 3 дней

Для связи с менеджером: @manager_username
"""
    await message.answer(text, reply_markup=main_menu())


# ========== РОЗЫГРЫШ (ПОКАЗ БИЛЕТОВ) ==========
@router.message(F.text == "🎁 Розыгрыш")
async def show_lottery(message: Message, state: FSMContext):
    await state.clear()
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

        user_ticket_count = await db.get_user_ticket_count(message.from_user.id)

        async with aiosqlite.connect(db.DATABASE_PATH) as conn:
            cursor = await conn.execute("SELECT referrer_id FROM users WHERE user_id = ?", (message.from_user.id,))
            referrer_data = await cursor.fetchone()
            if referrer_data and referrer_data[0] and user_ticket_count == 0:
                price = 500
            else:
                price = PRICE_FIRST if user_ticket_count == 0 else PRICE_DISCOUNT

        # Доступные билеты
        available = [num for num in range(1, TOTAL_TICKETS + 1) if num not in taken]
        total_available = len(available)

        buttons = []
        for i in range(0, 104, 8):
            row_buttons = []
            for j in range(1, 9):
                ticket_num = i + j
                if 1 <= ticket_num <= TOTAL_TICKETS:
                    if ticket_num in taken:
                        row_buttons.append(InlineKeyboardButton(text="🔒", callback_data="sold"))
                    else:
                        # Без выделения огнём – просто номер
                        row_buttons.append(InlineKeyboardButton(text=str(ticket_num), callback_data=f"buy_{ticket_num}"))
            if row_buttons:
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
            elif hours > 0:
                timer_text = f"⏰ ДО РОЗЫГРЫША: {hours}ч {minutes}мин"
            else:
                timer_text = f"⏰ ДО РОЗЫГРЫША: {minutes}мин"
        elif sold >= 70 and not is_timer_active:
            timer_text = "🎯 ТАЙМЕР ЗАПУСТИТСЯ ПРИ ДОСТИЖЕНИИ 70 ПРОДАННЫХ ПОДПИСОК!"
        elif sold >= TOTAL_TICKETS:
            timer_text = "🎲 ВСЕ БИЛЕТЫ РАЗЫГРАНЫ! РОЗЫГРЫШ СОСТОИТСЯ СЕЙЧАС!"
        elif sold < 70:
            timer_text = f"⏳ ДО ЗАПУСКА ТАЙМЕРА: {70 - sold} подписок"

        lottery_text = f"""
🎰 АКТУАЛЬНЫЙ РОЗЫГРЫШ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 ПРИЗ: {PRIZE_INFO['name']}
📝 ОПИСАНИЕ: {PRIZE_INFO['description']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎫 ПРОДАНО ПОДПИСОК: {sold}/{TOTAL_TICKETS}
✨ ДОСТУПНО БИЛЕТОВ-ПОДАРКОВ: {total_available}
💰 ЦЕНА ПОДПИСКИ: {price}₽
{timer_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👇 ВЫБЕРИТЕ НОМЕР БИЛЕТА (1-100):
"""

        if PRIZE_INFO.get("photo") and PRIZE_INFO["photo"]:
            try:
                await message.answer_photo(
                    photo=PRIZE_INFO["photo"],
                    caption=lottery_text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
                )
            except:
                await message.answer(lottery_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        else:
            await message.answer(lottery_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
        print(f"Ошибка: {e}")

# ========== ПОКУПКА БИЛЕТА (ОФОРМЛЕНИЕ ПОДПИСКИ) ==========
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

        # Количество уже подтверждённых подписок
        async with aiosqlite.connect(db.DATABASE_PATH) as conn:
            cursor = await conn.execute("""
                SELECT COUNT(*) FROM subscriptions 
                WHERE user_id = ? AND payment_confirmed = 1 AND expires_at > ?
            """, (callback.from_user.id, datetime.now()))
            confirmed_count = (await cursor.fetchone())[0]

        async with aiosqlite.connect(db.DATABASE_PATH) as conn:
            cursor = await conn.execute("SELECT referrer_id FROM users WHERE user_id = ?", (callback.from_user.id,))
            referrer_data = await cursor.fetchone()
            if referrer_data and referrer_data[0] and confirmed_count == 0:
                price = 500
            else:
                price = PRICE_DISCOUNT if confirmed_count > 0 else PRICE_FIRST

        await state.update_data(ticket_number=ticket_num, price=price)

        payment_text = f"""
💳 ОФОРМЛЕНИЕ ПОДПИСКИ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Вы оформляете подписку на 10 дней.
В ПОДАРОК вы получите лотерейный билет №{ticket_num}

🏦 РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ:
Т-Банк: 2200 7004 3556 8828
Получатель: Наталья О.
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


# ========== ОТМЕНА ПОКУПКИ ==========
@router.callback_query(F.data == "cancel")
async def cancel_purchase(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("❌ Покупка отменена", reply_markup=main_menu())
    await callback.answer()


# ========== ОБНОВЛЕНИЕ РОЗЫГРЫША ==========
@router.callback_query(F.data == "refresh")
async def refresh_lottery(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await show_lottery(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "sold")
async def sold_ticket(callback: CallbackQuery):
    await callback.answer("❌ Этот билет уже куплен!", show_alert=True)


# ========== ОБРАБОТКА ЧЕКА ==========
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
🎫 Билет в подарок №{ticket_num}
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
                print(f"Ошибка отправки админу: {e}")

        await message.answer(
            "✅ Чек отправлен на проверку!\nМенеджер проверит оплату в ближайшее время.",
            reply_markup=main_menu()
        )
        await state.clear()

    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear()


@router.message(PaymentStates.waiting_for_receipt)
async def invalid_receipt(message: Message, state: FSMContext):
    await message.answer(
        "❌ Пожалуйста, отправьте ФОТО чека об оплате.\n\n"
        "Если хотите отменить покупку, напишите /cancel",
        reply_markup=main_menu()
    )


# ========== ТВОИ БИЛЕТЫ ==========
@router.message(F.text == "🎫 Твои билеты")
async def show_my_tickets(message: Message, state: FSMContext):
    await state.clear()
    try:
        tickets = await db.get_user_tickets(message.from_user.id)
        confirmed_tickets = [t for t in tickets if t[2] == 1]
        if not confirmed_tickets:
            await message.answer("📭 У вас пока нет активных билетов-подарков.", reply_markup=main_menu())
            return
        text = "🎫 ТВОИ БИЛЕТЫ (ПОДАРКИ ЗА ПОДПИСКУ):\n━━━━━━━━━━━━━━━━━\n"
        for ticket_num, purchase_date, confirmed in confirmed_tickets:
            date_str = datetime.fromisoformat(purchase_date).strftime('%d.%m.%Y')
            text += f"🔸 Билет №{ticket_num} (получен {date_str})\n"
        await message.answer(text, reply_markup=main_menu())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")


# ========== ПОСЛЕДНИЙ БИЛЕТ ==========
@router.message(F.text == "🏆 Последний билет")
async def last_draw_winner(message: Message, state: FSMContext):
    await state.clear()
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
                "📭 Пока не было проведено ни одного розыгрыша.\n\n"
                "Розыгрыш состоится когда:\n"
                "• Будет продано 70+ подписок, или\n"
                "• Пройдёт 4 дня, или\n"
                "• Будут разыграны все 100 билетов",
                reply_markup=main_menu()
            )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")


# ========== АКЦИИ ==========
@router.message(F.text == "🎁 Акции")
async def show_promotions(message: Message, state: FSMContext):
    await state.clear()
    ticket_count = await db.get_user_ticket_count(message.from_user.id)
    referrals_count = await db.get_five_referrals_count(message.from_user.id)
    referrals_needed = 5 - referrals_count if referrals_count < 5 else 0
    text = f"""
🎁 АКТУАЛЬНЫЕ АКЦИИ 🎁
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ ПЕРВАЯ ПОДПИСКА СО СКИДКОЙ
• Первая подписка — 800₽ (билет в подарок)
• Последующие подписки — 700₽ (билет в подарок)

2️⃣ ПРИВЕДИ 5 ДРУЗЕЙ
• Приведи 5 друзей, которые оформят подписку
• Ты получишь БЕСПЛАТНЫЙ билет на выбор!
• Друзья получат первую подписку за 500₽

📊 Ваш прогресс: {referrals_count}/5 друзей
{'🎉 ВЫ УЖЕ ПОЛУЧИЛИ БЕСПЛАТНЫЙ БИЛЕТ!' if referrals_count >= 5 else f'🎯 Осталось привести: {referrals_needed} друзей'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💫 Активируйте акции, участвуя в розыгрышах!
"""
    await message.answer(text, reply_markup=main_menu())


# ========== РЕФЕРАЛЬНАЯ ССЫЛКА ==========
@router.message(F.text == "👥 Реферальная ссылка")
async def show_referral(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    bot_username = (await message.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    referrals_count = await db.get_referrals_count(user_id)
    referrals_list = await db.get_referral_list(user_id)

    text = f"""
👥 **РЕФЕРАЛЬНАЯ ПРОГРАММА**

🔗 **ВАША ССЫЛКА:**  
`{referral_link}`

📊 **СТАТИСТИКА:**  
• Приглашено друзей: {len(referrals_list)}  
• Из них купили подписку: {referrals_count}

🎁 **ВОЗНАГРАЖДЕНИЕ:**  
За каждых 5 друзей, которые оформят подписку:  
• ВЫ получаете **БЕСПЛАТНЫЙ** билет!  
• ДРУЗЬЯ получают первую подписку за **500₽**

👥 **ПРИГЛАШЁННЫЕ ДРУЗЬЯ:**  
{chr(10).join([f"• @{u[1]}" if u[1] else f"• ID:{u[0]}" for u in referrals_list]) if referrals_list else "Пока нет"}
"""
    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu())


# ========== ПОЛУЧИТЬ БОНУС ==========
@router.message(F.text == "🎁 Получить бонус")
async def get_bonus(message: Message, state: FSMContext):
    await state.clear()
    text = """
🎁 *Ты можешь получить 50 монет в нашем боте "Прозрачный Генератор"!*

🤖 Бот @OsipovIIbot генерирует и редактирует фото с помощью ИИ.

📌 *ЧТОБЫ ПОЛУЧИТЬ БОНУС:*

1️⃣ Перейди в бота @OsipovIIbot
2️⃣ Нажми кнопку *"Пополнить"*
3️⃣ Выбери *"Бонус за розыгрыш"*
4️⃣ Отправь скриншот этого чека (или скриншот подтверждённой оплаты подписки)

✨ Бонус будет начислен автоматически после проверки!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 *50 монет* уже ждут тебя!

[👉 ПЕРЕЙТИ В БОТА 👈](https://t.me/OsipovIIbot)
"""
    await message.answer(text, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=main_menu())
