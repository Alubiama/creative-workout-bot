from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def difficulty_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="😴 Легко", callback_data="difficulty:easy"),
        InlineKeyboardButton(text="😐 Нормально", callback_data="difficulty:ok"),
        InlineKeyboardButton(text="🔥 Сложно", callback_data="difficulty:hard"),
    )
    return builder.as_markup()


def round_two_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💪 Ещё раунд", callback_data="roundtwo:yes"),
        InlineKeyboardButton(text="✅ Закончить", callback_data="roundtwo:no"),
    )
    return builder.as_markup()


def start_session_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏠 Глубокий", callback_data="start_mode:deep"),
        InlineKeyboardButton(text="🚇 Быстрый", callback_data="start_mode:quick"),
    )
    return builder.as_markup()


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Persistent bottom keyboard — главная навигация."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🏠 Глубокий"),
        KeyboardButton(text="🚇 Быстрый"),
    )
    builder.row(
        KeyboardButton(text="🌱 Инкубация"),
        KeyboardButton(text="📊 Прогресс"),
    )
    builder.row(
        KeyboardButton(text="🔥 Стрик"),
        KeyboardButton(text="❓ Помощь"),
    )
    builder.row(
        KeyboardButton(text="📋 Отчёт"),
    )
    return builder.as_markup(resize_keyboard=True, is_persistent=True)
