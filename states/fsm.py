from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    exercise_1 = State()
    exercise_2 = State()
    exercise_3 = State()


class SessionStates(StatesGroup):
    waiting_answer = State()     # Упражнение выдано, ждём ответ
    waiting_difficulty = State() # Ответ получен, ждём оценку сложности


class IncubationStates(StatesGroup):
    waiting_answer = State()
