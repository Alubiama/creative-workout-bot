"""Incubation handlers: /incubate and /answer commands."""
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from states.fsm import IncubationStates
from database.queries import (
    get_user, ensure_user, create_incubation, get_active_incubation, answer_incubation
)
from llm.generator import generate_incubation_task
from locales.ru import t

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("incubate"))
@router.message(F.text == "🌱 Инкубация")
async def cmd_incubate(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    await ensure_user(user_id, message.from_user.username)
    user = await get_user(user_id)

    if not user or not user.get("onboarded"):
        await message.answer(t("not_onboarded"))
        return

    task_text = await generate_incubation_task()
    await create_incubation(user_id=user_id, task_text=task_text)
    await message.answer(t("incubation_task", task=task_text), parse_mode="Markdown")


@router.message(Command("answer"))
async def cmd_answer(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    await ensure_user(user_id, message.from_user.username)

    active = await get_active_incubation(user_id)
    if not active:
        await message.answer(t("incubation_no_active"))
        return

    await state.update_data(incubation_id=active["id"], incubation_task=active["task_text"])
    await state.set_state(IncubationStates.waiting_answer)
    await message.answer(
        t("incubation_ask_answer", task=active["task_text"]),
        parse_mode="Markdown",
    )


@router.message(IncubationStates.waiting_answer)
async def receive_incubation_answer(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    answer_text = message.text or ""

    await answer_incubation(
        incubation_id=data["incubation_id"],
        answer_text=answer_text,
    )
    await state.clear()
    await message.answer(t("incubation_saved"))
