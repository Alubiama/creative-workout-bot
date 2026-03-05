"""Session handlers: /deep and /quick commands."""
import logging
import time

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states.fsm import SessionStates
from database.queries import (
    get_user, ensure_user, get_all_progress, create_session,
    complete_session, save_response, update_progress, update_streak
)
from exercises.registry import select_exercise, select_round_two, EXERCISE_TYPES
from llm.evaluator import evaluate_response, format_feedback
from keyboards.inline import difficulty_keyboard, round_two_keyboard
from locales.ru import t
from config import MODE_DEEP, MODE_QUICK

logger = logging.getLogger(__name__)
router = Router()


async def _start_session(message: Message, state: FSMContext, mode: str) -> None:
    user_id = message.from_user.id
    await ensure_user(user_id, message.from_user.username)
    user = await get_user(user_id)

    if not user or not user.get("onboarded"):
        await message.answer(t("not_onboarded"))
        return

    await state.clear()

    # Load progress for all exercise types
    all_progress = await get_all_progress(user_id)
    progress_map = {p["exercise_type"]: p for p in all_progress}

    streak = user.get("streak_days", 0)
    ex = select_exercise(mode=mode, progress=progress_map)

    session_id = await create_session(
        user_id=user_id,
        mode=mode,
        exercise_type=ex.exercise_type,
        exercise_level=ex.level,
    )

    if mode == MODE_DEEP:
        header = t("session_start_deep", streak=streak, exercise_type=ex.exercise_type, level=ex.level)
    else:
        header = t("session_start_quick", streak=streak, exercise_type=ex.exercise_type, level=ex.level)

    await state.update_data(
        session_id=session_id,
        mode=mode,
        exercise_type=ex.exercise_type,
        exercise_level=ex.level,
        exercise_prompt=ex.prompt,
        start_time=time.time(),
    )
    await state.set_state(SessionStates.waiting_answer)
    await message.answer(header, parse_mode="Markdown")
    await message.answer(ex.prompt, parse_mode="Markdown")


@router.message(Command("deep"))
@router.message(F.text == "🏠 Глубокий")
async def cmd_deep(message: Message, state: FSMContext) -> None:
    await _start_session(message, state, MODE_DEEP)


@router.message(Command("quick"))
@router.message(F.text == "🚇 Быстрый")
async def cmd_quick(message: Message, state: FSMContext) -> None:
    await _start_session(message, state, MODE_QUICK)


@router.message(SessionStates.waiting_answer)
async def receive_answer(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    user_id = message.from_user.id
    response_text = message.text or ""
    elapsed = int(time.time() - data.get("start_time", time.time()))

    await message.answer(t("session_thinking"), parse_mode="Markdown")

    eval_result = await evaluate_response(
        exercise_type=data["exercise_type"],
        exercise_level=data["exercise_level"],
        exercise_prompt=data["exercise_prompt"],
        user_response=response_text,
    )

    await state.update_data(
        user_response=response_text,
        llm_score=eval_result["score"],
        response_time_sec=elapsed,
        eval_result=eval_result,
    )
    await state.set_state(SessionStates.waiting_difficulty)

    await message.answer(format_feedback(eval_result), parse_mode="Markdown")
    await message.answer(t("session_ask_difficulty"), reply_markup=difficulty_keyboard())


@router.callback_query(F.data.startswith("difficulty:"), SessionStates.waiting_difficulty)
async def receive_difficulty(callback: CallbackQuery, state: FSMContext) -> None:
    difficulty = callback.data.split(":")[1]  # easy | ok | hard
    data = await state.get_data()
    user_id = callback.from_user.id

    await save_response(
        session_id=data["session_id"],
        user_response=data.get("user_response", ""),
        llm_score=data.get("llm_score", 3),
        user_difficulty=difficulty,
        response_time_sec=data.get("response_time_sec", 0),
    )

    new_level = await update_progress(
        user_id=user_id,
        exercise_type=data["exercise_type"],
        llm_score=data.get("llm_score", 3),
        user_difficulty=difficulty,
    )

    await update_streak(user_id)

    # Notify about level up
    if new_level > data["exercise_level"]:
        await callback.message.answer(
            f"⬆️ Уровень поднят! *{data['exercise_type']}* → уровень {new_level}",
            parse_mode="Markdown",
        )

    await state.update_data(current_level=data["exercise_level"])
    await state.set_state(SessionStates.round_two_offer)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        t("session_round_two_offer"),
        reply_markup=round_two_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("roundtwo:"), SessionStates.round_two_offer)
async def receive_round_two(callback: CallbackQuery, state: FSMContext) -> None:
    choice = callback.data.split(":")[1]
    data = await state.get_data()

    await callback.message.edit_reply_markup(reply_markup=None)

    if choice == "no":
        await complete_session(data["session_id"])
        await state.clear()
        await callback.message.answer(t("session_done"), parse_mode="Markdown")
    else:
        ex = select_round_two(
            exercise_type=data["exercise_type"],
            current_level=data.get("current_level", data["exercise_level"]),
            seed=int(time.time()),
        )
        await state.update_data(
            exercise_type=ex.exercise_type,
            exercise_level=ex.level,
            exercise_prompt=ex.prompt,
            start_time=time.time(),
        )
        await state.set_state(SessionStates.waiting_answer)
        await callback.message.answer(ex.prompt, parse_mode="Markdown")

    await callback.answer()
