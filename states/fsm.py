from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    exercise_1 = State()   # AUT baseline
    exercise_2 = State()   # Forced Connections baseline
    exercise_3 = State()   # RAT baseline
    done = State()


class SessionStates(StatesGroup):
    waiting_answer = State()    # Упражнение выдано, ждём ответ
    waiting_difficulty = State()  # Ответ получен, ждём кнопку сложности
    round_two_offer = State()   # Предложение второго раунда


class IncubationStates(StatesGroup):
    waiting_answer = State()  # /answer — ждём ответ на задачу инкубации
