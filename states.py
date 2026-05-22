from aiogram.fsm.state import State, StatesGroup

# Это состояния - как этапы разговора с ботом
class PaymentStates(StatesGroup):
    waiting_for_receipt = State()  # Ждем когда пользователь отправит чек

class LotteryStates(StatesGroup):
    waiting_for_admin_action = State()  # Ждем действие админа
