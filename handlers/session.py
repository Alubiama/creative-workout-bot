"""Session handlers: /deep and /quick — полноценные сессии."""
import logging
import time

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states.fsm import SessionStates
from database.queries import (
    get_user, ensure_user, get_all_progress,
    create_session, complete_session,
    save_response, update_progress, update_streak,
)
from exercises.registry import select_session_exercises
from exercises.scales import get_scale
from llm.evaluator import evaluate_response, format_feedback
from keyboards.inline import difficulty_keyboard
from locales.ru import t
from config import MODE_DEEP, MODE_QUICK

logger = logging.getLogger(__name__)
router = Router()

# Deep = 3 упражнения, Quick = 1
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

MOTIVATION_BY_SCORE = [
    (4.5, "🔥 Исключительная сессия. Так держать."),
    (3.5, "💡 Сильная работа — неожиданные связи были."),
    (2.5, "⚡️ Хорошее начало. В следующий раз копай глубже."),
    (0.0, "🧠 Мозг разогревается. Главное — не останавливаться."),
]


def _motivation(avg: float) -> str:
    for threshold, phrase in MOTIVATION_BY_SCORE:
        if avg >= threshold:
            return phrase
    return MOTIVATION_BY_SCORE[-1][1]


async def _start_session(message: Message, state: FSMContext, mode: str) -> None:
    user_id = message.from_user.id
    await ensure_user(user_id, message.from_user.username)
    user = await get_user(user_id)

    if not user or not user.get("onboarded"):
        await message.answer(t("not_onboarded"))
        return

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
    )

    session_id = await create_session(
        user_id=user_id,
        mode=mode,
        exercise_type=exercises[0].exercise_type,
        exercise_level=exercises[0].level,
    )

    exercises_data = [
        {"type": ex.exercise_type, "level": ex.level, "prompt": ex.prompt}
        for ex in exercises
    ]

    await state.update_data(
        session_id=session_id,
        mode=mode,
        exercises=exercises_data,
        current_idx=0,
        results=[],
        exercise_start_time=time.time(),
    )
    await state.set_state(SessionStates.waiting_answer)

    # ── Стартовый экран ──
    icon = "🏠" if mode == MODE_DEEP else "🚇"
    mode_name = "Глубокая" if mode == MODE_DEEP else "Быстрая"
    ex_list = "\n".join(
        f"  {i+1}. {EXERCISE_TYPE_NAMES.get(ex['type'], ex['type'])}"
        for i, ex in enumerate(exercises_data)
    )
    word = "упражнение" if count == 1 else "упражнения"
    start_text = (
        f"{icon} *{mode_name} сессия началась*\n"
        f"🔥 Стрик: {streak} дн.\n\n"
        f"Сегодня {count} {word}:\n"
        f"{ex_list}\n\n"
        "_Поехали._"
    )
    await message.answer(start_text, parse_mode="Markdown")
    await _send_exercise(message, exercises_data[0], idx=0, total=count)


async def _send_exercise(message: Message, ex: dict, idx: int, total: int) -> None:
    name = EXERCISE_TYPE_NAMES.get(ex["type"], ex["type"])
    header = f"*Упражнение {idx + 1} из {total} — {name}*\n\n"
    await message.answer(header + ex["prompt"], parse_mode="Markdown")

    scale = get_scale(ex["type"])
    if scale:
        await message.answer(scale, parse_mode="Markdown")


# ─── Команды ──────────────────────────────────────────────────────────────────

@router.message(Command("deep"))
@router.message(F.text == "🏠 Глубокий")
async def cmd_deep(message: Message, state: FSMContext) -> None:
    await _start_session(message, state, MODE_DEEP)


@router.message(Command("quick"))
@router.message(F.text == "🚇 Быстрый")
async def cmd_quick(message: Message, state: FSMContext) -> None:
    await _start_session(message, state, MODE_QUICK)


# ─── Ответ на упражнение ──────────────────────────────────────────────────────

@router.message(SessionStates.waiting_answer)
async def receive_answer(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    user_response = message.text or ""
    elapsed = int(time.time() - data.get("exercise_start_time", time.time()))
    exercises = data["exercises"]
    idx = data["current_idx"]
    ex = exercises[idx]

    await message.answer("...")

    # Для eval_ideas добавляем правильный ответ в контекст оценщика
    eval_prompt = ex["prompt"]
    if ex["type"] == "eval_ideas" and ex.get("correct_answer"):
        eval_prompt = (
            eval_prompt
            + f"\n\n[Правильный ответ: {ex['correct_answer'].upper()}. "
            f"Почему он оригинален: {ex.get('why_original', '')}]"
        )

    eval_result = await evaluate_response(
        exercise_type=ex["type"],
        exercise_level=ex["level"],
        exercise_prompt=eval_prompt,
        user_response=user_response,
    )

    await state.update_data(
        pending_response=user_response,
        pending_score=eval_result["score"],
        pending_elapsed=elapsed,
    )
    await state.set_state(SessionStates.waiting_difficulty)

    await message.answer(
        format_feedback(eval_result, exercise_type=ex["type"]),
        parse_mode="Markdown",
    )
    await message.answer(t("session_ask_difficulty"), reply_markup=difficulty_keyboard())


# ─── Оценка сложности ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("difficulty:"), SessionStates.waiting_difficulty)
async def receive_difficulty(callback: CallbackQuery, state: FSMContext) -> None:
    difficulty = callback.data.split(":")[1]
    data = await state.get_data()
    user_id = callback.from_user.id

    exercises = data["exercises"]
    idx = data["current_idx"]
    ex = exercises[idx]
    total = len(exercises)
    score = data.get("pending_score", 3)

    await save_response(
        session_id=data["session_id"],
        user_response=data.get("pending_response", ""),
        llm_score=score,
        user_difficulty=difficulty,
        response_time_sec=data.get("pending_elapsed", 0),
    )

    new_level = await update_progress(
        user_id=user_id,
        exercise_type=ex["type"],
        llm_score=score,
        user_difficulty=difficulty,
    )

    results = data.get("results", [])
    results.append({
        "type": ex["type"],
        "score": score,
        "difficulty": difficulty,
        "level_up": new_level > ex["level"],
    })

    await callback.message.edit_reply_markup(reply_markup=None)

    next_idx = idx + 1

    if next_idx < total:
        # ── Переход к следующему упражнению ──
        next_ex = exercises[next_idx]

        # Динамическая генерация eval_ideas после первого упражнения
        if next_ex["type"] == "eval_ideas" and next_ex.get("prompt") is None:
            await callback.message.answer("⏳ Генерирую следующее упражнение...")
            from exercises.eval_ideas import generate_exercise as gen_eval_ideas
            prev_ex = exercises[idx]
            try:
                eval_data = await gen_eval_ideas(
                    prev_prompt=prev_ex["prompt"],
                    prev_type=prev_ex["type"],
                    level=next_ex["level"],
                )
                next_ex = dict(next_ex)
                next_ex["prompt"] = eval_data["prompt"]
                next_ex["correct_answer"] = eval_data["correct_answer"]
                next_ex["why_original"] = eval_data["why_original"]
            except Exception as e:
                logger.error("eval_ideas dynamic generation failed: %s", e)
                # Фолбэк — не блокируем сессию
                next_ex = dict(next_ex)
                next_ex["prompt"] = (
                    "*Оценка идей*\n\n"
                    "Три человека ответили на то же задание что и ты.\n"
                    "Прочитай — и выбери самый оригинальный ответ.\n\n"
                    "*A.* Стандартный, предсказуемый ответ без усилия.\n\n"
                    "*B.* Нестандартный, но не выходящий за очевидное.\n\n"
                    "*C.* Неожиданный угол — связь через нетипичный домен.\n\n"
                    "Напиши букву (A, B или C) и объясни почему именно этот ответ "
                    "самый оригинальный. Что делает его неожиданным?"
                )
                next_ex["correct_answer"] = "c"
                next_ex["why_original"] = "Неожиданная связь через нетипичный контекст"
            exercises = list(exercises)
            exercises[next_idx] = next_ex
            await state.update_data(exercises=exercises)

        next_name = EXERCISE_TYPE_NAMES.get(next_ex["type"], next_ex["type"])
        await callback.message.answer(
            f"✅ *{idx + 1}/{total} готово* → {next_name}",
            parse_mode="Markdown",
        )
        await state.update_data(
            current_idx=next_idx,
            results=results,
            exercise_start_time=time.time(),
        )
        await state.set_state(SessionStates.waiting_answer)
        await _send_exercise(callback.message, next_ex, idx=next_idx, total=total)

    else:
        # ── Финальный экран ──
        await update_streak(user_id)
        await complete_session(data["session_id"])
        await state.clear()

        avg_score = sum(r["score"] for r in results) / len(results)

        lines = ["🎯 *Сессия завершена!*\n\n"]
        for r in results:
            name = EXERCISE_TYPE_NAMES.get(r["type"], r["type"])
            bar = "⬛" * r["score"] + "⬜" * (5 - r["score"])
            lvl_up = "  ⬆️ уровень" if r["level_up"] else ""
            lines.append(f"• {name}: {r['score']}/5 {bar}{lvl_up}\n")

        lines.append(f"\n*Средняя: {avg_score:.1f}/5*\n")
        lines.append(f"\n{_motivation(avg_score)}")

        await callback.message.answer("".join(lines), parse_mode="Markdown")

    await callback.answer()
