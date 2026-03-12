"""Enhanced session router with focus mode, appeals, round two, and concrete feedback."""
import logging
import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from coach_evaluator import (
    appeal_evaluation,
    evaluate_response,
    format_appeal_feedback,
    format_feedback,
)
from config import MODE_DEEP, MODE_QUICK
from database.queries import (
    clear_focus_exercise_type,
    complete_session,
    create_session,
    ensure_user,
    get_all_progress,
    get_focus_exercise_type,
    get_stats_summary,
    get_user,
    save_response,
    set_focus_exercise_type,
    reset_user_progress,
    update_progress,
    update_streak,
)
from exercises.eval_ideas import generate_exercise as generate_eval_ideas
from exercises.registry import select_round_two, select_session_exercises
from exercises.scales import get_scale
from keyboards.inline import difficulty_keyboard
from locales.ru import t
from states.fsm import SessionStates
from handlers import incubation
import report_v2

logger = logging.getLogger(__name__)
router = Router()
BUILD_ID = "reset-fix-2026-03-10-01"

EXERCISES_COUNT = {MODE_DEEP: 3, MODE_QUICK: 1}

EXERCISE_TYPE_NAMES = {
    "aut": "Альт. применение",
    "rat": "Удалённые ассоциации",
    "forced": "Вынужденные связи",
    "constraints": "Ограничения",
    "triz": "ТРИЗ",
    "pitch": "Питч",
    "frames": "Смешение фреймов",
    "quantity": "Дрель количества",
    "eval_ideas": "Оценка идей",
}

MENU_DEEP = "\U0001f3e0 \u0413\u043b\u0443\u0431\u043e\u043a\u0438\u0439"
MENU_QUICK = "\U0001f687 \u0411\u044b\u0441\u0442\u0440\u044b\u0439"
MENU_FOCUS = "\U0001f3af \u0424\u043e\u043a\u0443\u0441"
MENU_INCUBATION = "\U0001f331 \u0418\u043d\u043a\u0443\u0431\u0430\u0446\u0438\u044f"
MENU_PROGRESS = "\U0001f4ca \u041f\u0440\u043e\u0433\u0440\u0435\u0441\u0441"
MENU_REPORT = "\U0001f4cb \u041e\u0442\u0447\u0451\u0442"
MENU_STREAK = "\U0001f525 \u0421\u0442\u0440\u0438\u043a"
MENU_HELP = "\u2753 \u041f\u043e\u043c\u043e\u0449\u044c"
MENU_RESET = "\u267b\ufe0f \u0421\u0431\u0440\u043e\u0441"
MENU_BUTTONS = {
    MENU_DEEP,
    MENU_QUICK,
    MENU_FOCUS,
    MENU_INCUBATION,
    MENU_PROGRESS,
    MENU_REPORT,
    MENU_STREAK,
    MENU_HELP,
    MENU_RESET,
}

MOTIVATION_BY_SCORE = [
    (4.5, "Сильная сессия. Здесь уже есть настоящее мышление, а не просто ответы."),
    (3.5, "Хороший уровень. Есть рабочие ходы, но ещё можно делать смелее и точнее."),
    (2.5, "Нормальная база. Следующая ступень — меньше очевидного, больше структуры и неожиданности."),
    (0.0, "Разогрев засчитан. Главное сейчас — не останавливаться и не играть в безопасные ответы."),
]


def _motivation(avg: float) -> str:
    for threshold, phrase in MOTIVATION_BY_SCORE:
        if avg >= threshold:
            return phrase
    return MOTIVATION_BY_SCORE[-1][1]


def _feedback_action_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Принять вердикт", callback_data="feedback:accept"),
        InlineKeyboardButton(text="Оспорить", callback_data="feedback:appeal"),
    )
    return builder.as_markup()


def _next_action_keyboard(can_round_two: bool, has_next: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_round_two:
        builder.row(InlineKeyboardButton(text="Ещё раунд этого навыка", callback_data="next:round_two"))
    label = "Дальше" if has_next else "Завершить сессию"
    builder.row(InlineKeyboardButton(text=label, callback_data="next:continue"))
    return builder.as_markup()


def _focus_scope_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Разовая quick-сессия", callback_data="focusscope:one:quick"),
        InlineKeyboardButton(text="Разовая deep-сессия", callback_data="focusscope:one:deep"),
    )
    builder.row(
        InlineKeyboardButton(text="Включить постоянный трек", callback_data="focusscope:track:none"),
        InlineKeyboardButton(text="Выключить трек", callback_data="focusscope:off:none"),
    )
    return builder.as_markup()


def _focus_type_keyboard(scope: str, mode: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for exercise_type, label in EXERCISE_TYPE_NAMES.items():
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"focusset:{scope}:{mode}:{exercise_type}",
            )
        )
    return builder.as_markup()


def _reset_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="\u0414\u0430, \u0441\u0431\u0440\u043e\u0441\u0438\u0442\u044c \u0432\u0441\u0451", callback_data="reset:confirm"),
        InlineKeyboardButton(text="\u041d\u0435\u0442, \u043e\u0442\u043c\u0435\u043d\u0430", callback_data="reset:cancel"),
    )
    return builder.as_markup()


async def _start_session(
    message: Message,
    state: FSMContext,
    mode: str,
    preferred_type: str | None = None,
    focus_reason: str | None = None,
) -> None:
    user_id = message.from_user.id
    await ensure_user(user_id, message.from_user.username)
    user = await get_user(user_id)

    if not user or not user.get("onboarded"):
        await message.answer(t("not_onboarded"))
        return

    if preferred_type is None:
        preferred_type = await get_focus_exercise_type(user_id)
        if preferred_type:
            focus_reason = "Постоянный фокус"

    await state.clear()

    all_progress = await get_all_progress(user_id)
    progress_map = {p["exercise_type"]: p for p in all_progress}
    streak = user.get("streak_days", 0)
    count = EXERCISES_COUNT[mode]

    exercises = select_session_exercises(
        mode=mode,
        progress=progress_map,
        count=count,
        seed=int(time.time()),
        preferred_type=preferred_type,
    )

    session_id = await create_session(
        user_id=user_id,
        mode=mode,
        exercise_type=exercises[0].exercise_type,
        exercise_level=exercises[0].level,
    )

    exercises_data = [
        {
            "type": ex.exercise_type,
            "level": ex.level,
            "prompt": ex.prompt,
            "is_round_two": False,
        }
        for ex in exercises
    ]

    await state.update_data(
        session_id=session_id,
        mode=mode,
        exercises=exercises_data,
        current_idx=0,
        results=[],
        exercise_start_time=time.time(),
        phase="answer",
        focus_type=preferred_type,
        focus_reason=focus_reason,
    )
    await state.set_state(SessionStates.waiting_answer)

    icon = "🏠" if mode == MODE_DEEP else "🚇"
    mode_name = "Глубокая" if mode == MODE_DEEP else "Быстрая"
    ex_list = "\n".join(
        f"  {i + 1}. {EXERCISE_TYPE_NAMES.get(ex['type'], ex['type'])}"
        for i, ex in enumerate(exercises_data)
    )
    start_text = (
        f"{icon} *{mode_name} сессия началась*\n"
        f"🔥 Стрик: {streak} дн.\n"
    )
    if preferred_type:
        start_text += f"🎯 {focus_reason or 'Фокус'}: {EXERCISE_TYPE_NAMES.get(preferred_type, preferred_type)}\n"
    start_text += f"\nСегодня:\n{ex_list}\n\n_Поехали._"
    await message.answer(start_text, parse_mode="Markdown")
    await _send_exercise(message, exercises_data[0], idx=0, total=len(exercises_data))


async def _send_exercise(message: Message, ex: dict, idx: int, total: int) -> None:
    name = EXERCISE_TYPE_NAMES.get(ex["type"], ex["type"])
    suffix = " (доп. раунд)" if ex.get("is_round_two") else ""
    header = f"*Упражнение {idx + 1} из {total} — {name}{suffix}*\n\n"
    await message.answer(header + ex["prompt"], parse_mode="Markdown")

    scale = get_scale(ex["type"])
    if scale:
        await message.answer(scale, parse_mode="Markdown")


async def _move_forward(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    exercises = data["exercises"]
    next_idx = data["current_idx"] + 1
    if next_idx < len(exercises):
        await state.update_data(
            current_idx=next_idx,
            exercise_start_time=time.time(),
            phase="answer",
            pending_response=None,
            pending_eval_result=None,
            pending_initial_score=None,
            pending_elapsed=None,
            pending_appeal_text=None,
            pending_appeal_feedback=None,
            pending_appeal_decision=None,
        )
        await state.set_state(SessionStates.waiting_answer)
        await _send_exercise(message, exercises[next_idx], idx=next_idx, total=len(exercises))
    else:
        await _finish_session(message, state)


async def _finish_session(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    user_id = message.chat.id
    results = data.get("results", [])

    await update_streak(user_id)
    await complete_session(data["session_id"])
    await state.clear()

    avg_score = sum(r["score"] for r in results) / len(results) if results else 0
    lines = ["🎯 *Сессия завершена!*\n\n"]
    for result in results:
        name = EXERCISE_TYPE_NAMES.get(result["type"], result["type"])
        bar = "в–€" * result["score"] + "в–‘" * (5 - result["score"])
        level_up = " ⬆️ уровень" if result["level_up"] else ""
        lines.append(f"• {name}: {result['score']}/5 {bar}{level_up}\n")

    if results:
        lines.append(f"\n*Средняя: {avg_score:.1f}/5*\n")
    lines.append(f"\n{_motivation(avg_score)}")
    await message.answer("".join(lines), parse_mode="Markdown")


def _build_eval_prompt(ex: dict) -> str:
    eval_prompt = ex["prompt"]
    if ex["type"] == "eval_ideas" and ex.get("correct_answer"):
        eval_prompt += (
            f"\n\n[Правильный ответ: {ex['correct_answer'].upper()}. "
            f"Почему он оригинален: {ex.get('why_original', '')}]"
        )
    return eval_prompt


async def _ensure_dynamic_eval_ideas(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    exercises = list(data["exercises"])
    idx = data["current_idx"] + 1
    if idx >= len(exercises):
        return

    next_ex = exercises[idx]
    if next_ex["type"] != "eval_ideas" or next_ex.get("prompt") is not None:
        return

    await message.answer("Генерирую следующее упражнение...")
    prev_ex = exercises[idx - 1]
    try:
        eval_data = await generate_eval_ideas(
            prev_prompt=prev_ex["prompt"],
            prev_type=prev_ex["type"],
            level=next_ex["level"],
        )
        next_ex = dict(next_ex)
        next_ex["prompt"] = eval_data["prompt"]
        next_ex["correct_answer"] = eval_data["correct_answer"]
        next_ex["why_original"] = eval_data["why_original"]
        exercises[idx] = next_ex
        await state.update_data(exercises=exercises)
    except Exception as exc:
        logger.error("eval_ideas dynamic generation failed: %s", exc)


@router.message(Command("version"))
async def cmd_version(message: Message) -> None:
    await message.answer(f"build={BUILD_ID}; router=session_v2")


@router.message(Command("deep"))
@router.message(F.text == MENU_DEEP)
async def cmd_deep(message: Message, state: FSMContext) -> None:
    await _start_session(message, state, MODE_DEEP)


@router.message(Command("quick"))
@router.message(F.text == MENU_QUICK)
async def cmd_quick(message: Message, state: FSMContext) -> None:
    await _start_session(message, state, MODE_QUICK)


@router.message(Command("focus"))
@router.message(F.text == MENU_FOCUS)
async def cmd_focus(message: Message) -> None:
    await message.answer(
        "Выбери, как использовать фокус: разово на одну сессию или как постоянный трек.",
        reply_markup=_focus_scope_keyboard(),
    )


@router.message(Command("focus_off"))
async def cmd_focus_off(message: Message) -> None:
    await clear_focus_exercise_type(message.from_user.id)
    await message.answer("Постоянный фокус выключен. Следующие /deep и /quick снова будут подбираться автоматически.")


@router.message(Command("reset"))
@router.message(Command("reset_progress"))
@router.message(F.text == MENU_RESET)
async def cmd_reset(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Это полный сброс: удалятся сессии, ответы, прогресс, инкубации и focus-трек.\n\n"
        "После сброса ты начнёшь с нуля и увидишь экран /start заново.",
        reply_markup=_reset_confirm_keyboard(),
    )


@router.callback_query(F.data.startswith("reset:"))
async def handle_reset(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data.split(":", 1)[1]
    await callback.message.edit_reply_markup(reply_markup=None)

    if action == "cancel":
        await callback.message.answer("Сброс отменён.")
        await callback.answer()
        return

    await state.clear()
    await reset_user_progress(callback.from_user.id)
    await callback.message.answer("Готово. Всё очищено полностью. Нажми /start, чтобы пройти путь заново.")
    await callback.answer()


@router.callback_query(F.data.startswith("focusscope:"))
async def handle_focus_scope(callback: CallbackQuery) -> None:
    _, scope, mode = callback.data.split(":")
    if scope == "off":
        await clear_focus_exercise_type(callback.from_user.id)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Постоянный фокус выключен.")
        await callback.answer()
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "Выбери тип упражнения для фокуса:",
        reply_markup=_focus_type_keyboard(scope, mode),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("focusset:"))
async def handle_focus_set(callback: CallbackQuery, state: FSMContext) -> None:
    _, scope, mode, exercise_type = callback.data.split(":")
    label = EXERCISE_TYPE_NAMES.get(exercise_type, exercise_type)
    await callback.message.edit_reply_markup(reply_markup=None)

    if scope == "track":
        await set_focus_exercise_type(callback.from_user.id, exercise_type)
        await callback.message.answer(
            f"Постоянный фокус включён: *{label}*.\nТеперь обычные /deep и /quick будут крутиться вокруг этого навыка.",
            parse_mode="Markdown",
        )
    else:
        await callback.message.answer(
            f"Запускаю разовую {mode}-сессию с фокусом на *{label}*.",
            parse_mode="Markdown",
        )
        await _start_session(
            callback.message,
            state,
            MODE_DEEP if mode == "deep" else MODE_QUICK,
            preferred_type=exercise_type,
            focus_reason="Разовый фокус",
        )
    await callback.answer()


@router.message(SessionStates.waiting_answer, F.text.in_(MENU_BUTTONS))
@router.message(SessionStates.waiting_difficulty, F.text.in_(MENU_BUTTONS))
async def handle_menu_during_session(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("session_id"):
        await state.clear()

    text = message.text or ""
    if text == MENU_DEEP:
        await message.answer("\u0422\u0435\u043a\u0443\u0449\u0430\u044f \u0441\u0435\u0441\u0441\u0438\u044f \u0441\u0431\u0440\u043e\u0448\u0435\u043d\u0430. \u041f\u0435\u0440\u0435\u043a\u043b\u044e\u0447\u0430\u044e \u043d\u0430 \u0433\u043b\u0443\u0431\u043e\u043a\u0438\u0439 \u0440\u0435\u0436\u0438\u043c.")
        await _start_session(message, state, MODE_DEEP)
        return
    if text == MENU_QUICK:
        await message.answer("\u0422\u0435\u043a\u0443\u0449\u0430\u044f \u0441\u0435\u0441\u0441\u0438\u044f \u0441\u0431\u0440\u043e\u0448\u0435\u043d\u0430. \u041f\u0435\u0440\u0435\u043a\u043b\u044e\u0447\u0430\u044e \u043d\u0430 \u0431\u044b\u0441\u0442\u0440\u044b\u0439 \u0440\u0435\u0436\u0438\u043c.")
        await _start_session(message, state, MODE_QUICK)
        return
    if text == MENU_FOCUS:
        await cmd_focus(message)
        return
    if text == MENU_INCUBATION:
        await message.answer("\u0422\u0435\u043a\u0443\u0449\u0430\u044f \u0441\u0435\u0441\u0441\u0438\u044f \u0441\u0431\u0440\u043e\u0448\u0435\u043d\u0430. \u041f\u0435\u0440\u0435\u0445\u043e\u0436\u0443 \u043a \u0438\u043d\u043a\u0443\u0431\u0430\u0446\u0438\u0438.")
        await incubation.cmd_incubate(message, state)
        return
    if text == MENU_PROGRESS:
        stats = await get_stats_summary(message.from_user.id)
        if not stats["total_sessions"] and not stats["progress"]:
            await message.answer(t("stats_no_data"))
            return
        lines = [
            "\U0001f4ca *\u0422\u0432\u043e\u0439 \u043f\u0440\u043e\u0433\u0440\u0435\u0441\u0441*\n",
            f"\U0001f525 \u0421\u0442\u0440\u0438\u043a: *{stats['streak']}* \u0434\u043d\u0435\u0439\n",
            f"\U0001f4c5 \u0412\u0441\u0435\u0433\u043e \u0441\u0435\u0441\u0441\u0438\u0439: *{stats['total_sessions']}*\n",
        ]
        focus = stats.get("focus_exercise_type")
        if focus:
            lines.append(f"\U0001f3af \u0424\u043e\u043a\u0443\u0441-\u0442\u0440\u0435\u043a: *{EXERCISE_TYPE_NAMES.get(focus, focus)}*\n")
        for prog in sorted(stats["progress"], key=lambda p: p["sessions_count"], reverse=True):
            if prog["sessions_count"] == 0:
                continue
            name = EXERCISE_TYPE_NAMES.get(prog["exercise_type"], prog["exercise_type"])
            lines.append(
                f"? {name}: \u0443\u0440.{prog['current_level']} | \u0441\u0435\u0441\u0441\u0438\u0439 {prog['sessions_count']} | \u0441\u0440\u0435\u0434\u043d\u044f\u044f {prog['avg_score']:.1f}\n"
            )
        await message.answer("".join(lines), parse_mode="Markdown")
        return
    if text == MENU_STREAK:
        stats = await get_stats_summary(message.from_user.id)
        await message.answer(f"\U0001f525 \u0422\u0432\u043e\u0439 \u0441\u0442\u0440\u0438\u043a: *{stats['streak']}* \u0434\u043d\u0435\u0439 \u043f\u043e\u0434\u0440\u044f\u0434.", parse_mode="Markdown")
        return
    if text == MENU_REPORT:
        await report_v2.cmd_report(message)
        return
    if text == MENU_HELP:
        await message.answer(t("help_text"), parse_mode="Markdown")
        return
    if text == MENU_RESET:
        await cmd_reset(message, state)
        return


@router.message(SessionStates.waiting_answer)
async def receive_answer(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    exercises = data["exercises"]
    idx = data["current_idx"]
    ex = exercises[idx]
    user_response = (message.text or "").strip()
    lowered = user_response.lower()
    if lowered.startswith("/reset") or lowered.startswith("/reset_progress"):
        await cmd_reset(message, state)
        return
    elapsed = int(time.time() - data.get("exercise_start_time", time.time()))

    await message.answer("Смотрю ответ...")

    eval_result = await evaluate_response(
        exercise_type=ex["type"],
        exercise_level=ex["level"],
        exercise_prompt=_build_eval_prompt(ex),
        user_response=user_response,
    )

    await state.update_data(
        pending_response=user_response,
        pending_eval_result=eval_result,
        pending_initial_score=eval_result["score"],
        pending_elapsed=elapsed,
        pending_appeal_text=None,
        pending_appeal_feedback=None,
        pending_appeal_decision=None,
        phase="feedback_action",
    )
    await state.set_state(SessionStates.waiting_difficulty)

    await message.answer(format_feedback(eval_result), parse_mode="Markdown")
    await message.answer(
        "Если не согласен с оценкой, можно оспорить. Если ок — принимаем вердикт и двигаемся дальше.",
        reply_markup=_feedback_action_keyboard(),
    )


@router.message(SessionStates.waiting_difficulty)
async def receive_appeal_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip().lower()
    if text.startswith("/reset") or text.startswith("/reset_progress"):
        await cmd_reset(message, state)
        return

    data = await state.get_data()
    phase = data.get("phase")
    if phase != "appeal":
        await message.answer("Сейчас жду не текст, а выбор кнопкой.")
        return

    exercises = data["exercises"]
    idx = data["current_idx"]
    ex = exercises[idx]
    appeal_text = message.text or ""

    await message.answer("Разбираю твою апелляцию...")
    appeal_result = await appeal_evaluation(
        exercise_type=ex["type"],
        exercise_level=ex["level"],
        exercise_prompt=_build_eval_prompt(ex),
        user_response=data["pending_response"],
        original_evaluation=data["pending_eval_result"],
        user_appeal=appeal_text,
    )

    updated_eval = dict(data["pending_eval_result"])
    updated_eval["score"] = appeal_result["score"]
    updated_eval["feedback_text"] = appeal_result["feedback_text"]
    updated_eval["next_step"] = appeal_result["next_step"]

    await state.update_data(
        pending_eval_result=updated_eval,
        pending_appeal_text=appeal_text,
        pending_appeal_feedback=appeal_result["appeal_feedback"],
        pending_appeal_decision=appeal_result["decision"],
        phase="rate",
    )

    await message.answer(format_appeal_feedback(appeal_result), parse_mode="Markdown")
    await message.answer("Теперь оцени субъективную сложность этого упражнения.", reply_markup=difficulty_keyboard())


@router.callback_query(F.data.startswith("feedback:"), SessionStates.waiting_difficulty)
async def handle_feedback_action(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("phase") != "feedback_action":
        await callback.answer()
        return

    action = callback.data.split(":", 1)[1]
    await callback.message.edit_reply_markup(reply_markup=None)

    if action == "appeal":
        await state.update_data(phase="appeal")
        await callback.message.answer(
            "Напиши, с чем именно ты не согласен. Лучше коротко и по делу: где оценка промахнулась или что она недоучла."
        )
    else:
        await state.update_data(phase="rate")
        await callback.message.answer(t("session_ask_difficulty"), reply_markup=difficulty_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("difficulty:"), SessionStates.waiting_difficulty)
async def receive_difficulty(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("phase") != "rate":
        await callback.answer()
        return

    difficulty = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    exercises = data["exercises"]
    idx = data["current_idx"]
    ex = exercises[idx]
    score = data["pending_eval_result"]["score"]

    await save_response(
        session_id=data["session_id"],
        user_response=data.get("pending_response", ""),
        llm_score=score,
        llm_feedback=data["pending_eval_result"].get("feedback_text", ""),
        user_difficulty=difficulty,
        response_time_sec=data.get("pending_elapsed", 0),
        initial_llm_score=data.get("pending_initial_score"),
        appeal_text=data.get("pending_appeal_text"),
        appeal_feedback=data.get("pending_appeal_feedback"),
        appeal_decision=data.get("pending_appeal_decision"),
    )

    new_level = await update_progress(
        user_id=user_id,
        exercise_type=ex["type"],
        llm_score=score,
        user_difficulty=difficulty,
    )

    results = data.get("results", [])
    results.append(
        {
            "type": ex["type"],
            "score": score,
            "difficulty": difficulty,
            "level_up": new_level > ex["level"],
        }
    )

    await callback.message.edit_reply_markup(reply_markup=None)
    has_next = idx + 1 < len(exercises)
    can_round_two = not ex.get("is_round_two", False)

    await state.update_data(results=results, phase="next_action")
    await callback.message.answer(
        "Ответ сохранён. Хочешь сразу взять ещё один раунд этого же навыка посложнее или идти дальше?",
        reply_markup=_next_action_keyboard(can_round_two=can_round_two, has_next=has_next),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("next:"), SessionStates.waiting_difficulty)
async def handle_next_action(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("phase") != "next_action":
        await callback.answer()
        return

    action = callback.data.split(":", 1)[1]
    exercises = list(data["exercises"])
    idx = data["current_idx"]
    current_ex = exercises[idx]
    await callback.message.edit_reply_markup(reply_markup=None)

    if action == "round_two":
        round_two = select_round_two(current_ex["type"], current_ex["level"], seed=int(time.time()))
        exercises.insert(
            idx + 1,
            {
                "type": round_two.exercise_type,
                "level": round_two.level,
                "prompt": round_two.prompt,
                "is_round_two": True,
            },
        )
        await state.update_data(exercises=exercises)

    await _ensure_dynamic_eval_ideas(callback.message, state)
    await _move_forward(callback.message, state)
    await callback.answer()
