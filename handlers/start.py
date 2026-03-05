"""Onboarding flow: /start command."""
import logging
import time

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from states.fsm import OnboardingStates
from database.queries import ensure_user, mark_onboarded, get_user, update_progress, save_response
from exercises.registry import select_onboarding_exercise
from llm.evaluator import evaluate_response, format_feedback
from keyboards.inline import main_menu_keyboard
from locales.ru import t

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    username = message.from_user.username

    user = await ensure_user(user_id, username)

    if user.get("onboarded"):
        await message.answer(
            "Ты уже настроен. Выбирай режим 👇",
            reply_markup=main_menu_keyboard(),
        )
        return

    await state.clear()
    await message.answer(t("onboarding_welcome_1"), parse_mode="Markdown")
    await message.answer(t("onboarding_welcome_2"), parse_mode="Markdown")

    ex = select_onboarding_exercise(step=0)
    await state.update_data(
        onboarding_step=0,
        exercise_type=ex.exercise_type,
        exercise_prompt=ex.prompt,
        exercise_level=ex.level,
        start_time=time.time(),
    )
    await state.set_state(OnboardingStates.exercise_1)
    await message.answer(ex.prompt, parse_mode="Markdown")


@router.message(OnboardingStates.exercise_1)
async def onboarding_answer_1(message: Message, state: FSMContext) -> None:
    await _handle_onboarding_answer(message, state, next_step=1, next_state=OnboardingStates.exercise_2)


@router.message(OnboardingStates.exercise_2)
async def onboarding_answer_2(message: Message, state: FSMContext) -> None:
    await _handle_onboarding_answer(message, state, next_step=2, next_state=OnboardingStates.exercise_3)


@router.message(OnboardingStates.exercise_3)
async def onboarding_answer_3(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    user_id = message.from_user.id
    response_text = message.text or ""
    elapsed = int(time.time() - data.get("start_time", time.time()))

    await message.answer(t("onboarding_analyzing"), parse_mode="Markdown")

    eval_result = await evaluate_response(
        exercise_type=data["exercise_type"],
        exercise_level=data["exercise_level"],
        exercise_prompt=data["exercise_prompt"],
        user_response=response_text,
    )
    await message.answer(format_feedback(eval_result), parse_mode="Markdown")

    await update_progress(
        user_id=user_id,
        exercise_type=data["exercise_type"],
        llm_score=eval_result["score"],
        user_difficulty="ok",  # default for onboarding
    )

    await mark_onboarded(user_id)
    await state.clear()
    await message.answer(
        t("onboarding_done"),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


async def _handle_onboarding_answer(
    message: Message,
    state: FSMContext,
    next_step: int,
    next_state,
) -> None:
    data = await state.get_data()
    user_id = message.from_user.id
    response_text = message.text or ""
    elapsed = int(time.time() - data.get("start_time", time.time()))

    await message.answer(t("onboarding_analyzing"), parse_mode="Markdown")

    eval_result = await evaluate_response(
        exercise_type=data["exercise_type"],
        exercise_level=data["exercise_level"],
        exercise_prompt=data["exercise_prompt"],
        user_response=response_text,
    )
    await message.answer(format_feedback(eval_result), parse_mode="Markdown")

    await update_progress(
        user_id=user_id,
        exercise_type=data["exercise_type"],
        llm_score=eval_result["score"],
        user_difficulty="ok",
    )

    ex = select_onboarding_exercise(step=next_step)
    await state.update_data(
        onboarding_step=next_step,
        exercise_type=ex.exercise_type,
        exercise_prompt=ex.prompt,
        exercise_level=ex.level,
        start_time=time.time(),
    )
    await state.set_state(next_state)
    await message.answer(ex.prompt, parse_mode="Markdown")
