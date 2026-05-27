from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def main_menu():
    """Главное меню"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎁 Розыгрыш")],
            [KeyboardButton(text="📋 Правила"), KeyboardButton(text="🎫 Твои билеты")],
            [KeyboardButton(text="🏆 Последний билет"), KeyboardButton(text="📦 Как получить приз")],
            [KeyboardButton(text="🎁 Акции"), KeyboardButton(text="👥 Реферальная ссылка")],
            [KeyboardButton(text="🎁 Получить бонус")]
        ],
        resize_keyboard=True
    )
    return keyboard

def admin_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Ожидают оплаты")],
            [KeyboardButton(text="🎲 Запустить розыгрыш")],
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="🗑 Сбросить все билеты")],
            
        ],
        resize_keyboard=True
    )
    return keyboard


def confirm_payment_keyboard(subscription_id):
    """Клавиатура для администратора"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПОДТВЕРДИТЬ", callback_data=f"confirm_{subscription_id}")],
        [InlineKeyboardButton(text="❌ ОТКАЗАТЬ", callback_data=f"reject_{subscription_id}")]
    ])
    return keyboard
    
