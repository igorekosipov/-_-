from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def main_menu():
    """Главное меню - кнопки которые видит пользователь"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎁 Розыгрыш")],
            [KeyboardButton(text="📋 Правила"), KeyboardButton(text="🎫 Купленные билеты")],
            [KeyboardButton(text="🏆 Последний билет"), KeyboardButton(text="📦 Как получить приз")]
        ],
        resize_keyboard=True
    )
    return keyboard


def admin_menu():
    """Меню для администратора"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Ожидают оплаты")],
            [KeyboardButton(text="🎲 Запустить розыгрыш")],
            [KeyboardButton(text="📊 Статистика")]
        ],
        resize_keyboard=True
    )
    return keyboard


def ticket_selection_keyboard(available_tickets):
    """Клавиатура с номерами билетов"""
    buttons = []
    # Распределяем билеты в строки по 5 штук
    for i in range(0, len(available_tickets), 5):
        row = []
        for num in available_tickets[i:i + 5]:
            row.append(InlineKeyboardButton(text=str(num), callback_data=f"buy_{num}"))
        buttons.append(row)

    # Добавляем кнопку отмены
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_payment_keyboard(subscription_id):
    """Клавиатура для администратора: подтвердить или отказать оплату"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПОДТВЕРДИТЬ", callback_data=f"confirm_{subscription_id}")],
        [InlineKeyboardButton(text="❌ ОТКАЗАТЬ", callback_data=f"reject_{subscription_id}")]
    ])
    return keyboard


def full_ticket_keyboard(all_tickets, start_index=0, tickets_per_page=20):
    """Клавиатура со ВСЕМИ билетами и пагинацией"""
    buttons = []

    # Показываем текущую страницу билетов
    end_index = min(start_index + tickets_per_page, len(all_tickets))
    current_page_tickets = all_tickets[start_index:end_index]

    for i in range(0, len(current_page_tickets), 5):
        row = []
        for num in current_page_tickets[i:i + 5]:
            row.append(InlineKeyboardButton(text=str(num), callback_data=f"buy_{num}"))
        buttons.append(row)

    # Кнопки навигации
    nav_row = []
    if start_index > 0:
        nav_row.append(
            InlineKeyboardButton(text="◀️ НАЗАД", callback_data=f"prev_page_{start_index - tickets_per_page}"))
    if end_index < len(all_tickets):
        nav_row.append(InlineKeyboardButton(text="ВПЕРЕД ▶️", callback_data=f"next_page_{end_index}"))

    if nav_row:
        buttons.append(nav_row)

    # Кнопка для ручного ввода
    buttons.append([InlineKeyboardButton(text="🔢 ВВЕСТИ НОМЕР", callback_data="select_number")])
    buttons.append([InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def number_input_keyboard():
    """Клавиатура для выбора диапазона номеров"""
    buttons = [
        [
            InlineKeyboardButton(text="1-20", callback_data="range_1_20"),
            InlineKeyboardButton(text="21-40", callback_data="range_21_40"),
            InlineKeyboardButton(text="41-60", callback_data="range_41_60"),
        ],
        [
            InlineKeyboardButton(text="61-80", callback_data="range_61_80"),
            InlineKeyboardButton(text="81-100", callback_data="range_81_100"),
        ],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def range_selection_keyboard(start_num, end_num, available_tickets):
    """Клавиатура для выбора из диапазона"""
    buttons = []
    range_tickets = [t for t in available_tickets if start_num <= t <= end_num]

    for i in range(0, len(range_tickets), 5):
        row = []
        for num in range_tickets[i:i + 5]:
            row.append(InlineKeyboardButton(text=str(num), callback_data=f"buy_{num}"))
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="◀️ НАЗАД", callback_data="back_to_numbers")])
    buttons.append([InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
