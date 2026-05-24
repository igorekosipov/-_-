from aiogram.fsm.state import State, StatesGroup

class PaymentStates(StatesGroup):
    waiting_for_receipt = State()

class LotteryStates(StatesGroup):
    waiting_for_admin_action = State()
