"""Stats, streak, and help handlers."""
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from database.queries import ensure_user, get_stats_summary
from locales.ru import t

logger = logging.getLogger(__name__)
router = Router()

EXERCISE_TYPE_NAMES = {
    "aut": "Альт. применение",
    "rat": "Удалённые ассоциации",
    "forced": "Вынужденные связи",
    "constraints": "Ограничения",
    "triz": "ТРИЗ",
    "pitch": "Питч",
    "frames": "Смешение фреймов",
    "quantity": "Дрель количества",
}


@router.message(Command("stats"))
@router.message(F.text == "📊 Прогресс")
async def cmd_stats(message: Message) -> None:
    user_id = message.from_user.id
    await ensure_user(user_id, message.from_user.username)
    stats = await get_stats_summary(user_id)

    if not stats["total_sessions"] and not stats["progress"]:
        await message.answer(t("stats_no_data"))
        return

    text = t("stats_header")
    text += t("stats_streak", streak=stats["streak"])
    text += t("stats_total", total=stats["total_sessions"])

    for prog in sorted(stats["progress"], key=lambda p: p["sessions_count"], reverse=True):
        if prog["sessions_count"] == 0:
            continue
        name = EXERCISE_TYPE_NAMES.get(prog["exercise_type"], prog["exercise_type"])
        text += t(
            "stats_progress_row",
            exercise_type=name,
            level=prog["current_level"],
            count=prog["sessions_count"],
            avg=prog["avg_score"],
        )

    await message.answer(text, parse_mode="Markdown")


@router.message(Command("streak"))
@router.message(F.text == "🔥 Стрик")
async def cmd_streak(message: Message) -> None:
    user_id = message.from_user.id
    await ensure_user(user_id, message.from_user.username)
    stats = await get_stats_summary(user_id)
    await message.answer(t("streak_message", streak=stats["streak"]), parse_mode="Markdown")


@router.message(Command("help"))
@router.message(F.text == "❓ Помощь")
async def cmd_help(message: Message) -> None:
    await message.answer(t("help_text"), parse_mode="Markdown")
