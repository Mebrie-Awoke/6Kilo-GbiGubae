from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    entering_name = State()
    choosing_batch = State()


class AdminBroadcast(StatesGroup):
    choosing_target = State()
    entering_message = State()
    confirming = State()
