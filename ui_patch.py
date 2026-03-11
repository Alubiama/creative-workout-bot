from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


LABEL_EASY = "😴 Легко"
LABEL_OK = "😐 Нормально"
LABEL_HARD = "🔥 Сложно"

MENU_DEEP = "🏠 Глубокий"
MENU_QUICK = "🚇 Быстрый"
MENU_FOCUS = "🎯 Фокус"
MENU_INCUBATION = "🌱 Инкубация"
MENU_PROGRESS = "📊 Прогресс"
MENU_REPORT = "📋 Отчёт"
MENU_STREAK = "🔥 Стрик"
MENU_HELP = "❓ Помощь"
MENU_RESET = "\u267b\ufe0f \u0421\u0431\u0440\u043e\u0441"


def difficulty_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=LABEL_EASY, callback_data="difficulty:easy"),
        InlineKeyboardButton(text=LABEL_OK, callback_data="difficulty:ok"),
        InlineKeyboardButton(text=LABEL_HARD, callback_data="difficulty:hard"),
    )
    return builder.as_markup()


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=MENU_DEEP),
        KeyboardButton(text=MENU_QUICK),
    )
    builder.row(
        KeyboardButton(text=MENU_FOCUS),
        KeyboardButton(text=MENU_INCUBATION),
    )
    builder.row(
        KeyboardButton(text=MENU_PROGRESS),
        KeyboardButton(text=MENU_REPORT),
    )
    builder.row(
        KeyboardButton(text=MENU_STREAK),
        KeyboardButton(text=MENU_RESET),
    )
    builder.row(
        KeyboardButton(text=MENU_HELP),
    )
    return builder.as_markup(resize_keyboard=True, is_persistent=True)
