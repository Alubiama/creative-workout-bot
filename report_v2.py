"""Concise weekly report focused on task-by-task learning evidence."""
import logging
from datetime import date

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from database.queries import ensure_user, get_weekly_report_data

logger = logging.getLogger(__name__)
router = Router()

EXERCISE_TYPE_NAMES = {
    "aut": "\u0410\u043b\u044c\u0442. \u043f\u0440\u0438\u043c\u0435\u043d\u0435\u043d\u0438\u0435",
    "rat": "\u0423\u0434\u0430\u043b\u0451\u043d\u043d\u044b\u0435 \u0430\u0441\u0441\u043e\u0446\u0438\u0430\u0446\u0438\u0438",
    "forced": "\u0412\u044b\u043d\u0443\u0436\u0434\u0435\u043d\u043d\u044b\u0435 \u0441\u0432\u044f\u0437\u0438",
    "constraints": "\u041e\u0433\u0440\u0430\u043d\u0438\u0447\u0435\u043d\u0438\u044f",
    "triz": "\u0422\u0420\u0418\u0417",
    "pitch": "\u041f\u0438\u0442\u0447",
    "frames": "\u0421\u043c\u0435\u0448\u0435\u043d\u0438\u0435 \u0444\u0440\u0435\u0439\u043c\u043e\u0432",
    "quantity": "\u0414\u0440\u0435\u043b\u044c \u043a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u0430",
    "eval_ideas": "\u041e\u0446\u0435\u043d\u043a\u0430 \u0438\u0434\u0435\u0439",
}

MODE_NAMES = {
    "deep": "\u0413\u043b\u0443\u0431\u043e\u043a\u0438\u0439",
    "quick": "\u0411\u044b\u0441\u0442\u0440\u044b\u0439",
}


def _safe(text: str | None) -> str:
    if not text:
        return "-"
    normalized = text.strip()
    return normalized if normalized else "-"


def _bot_answer(session: dict) -> str:
    feedback = _safe(session.get("llm_feedback"))
    score = session.get("llm_score")
    if feedback != "-":
        if score is None:
            return feedback
        return f"{feedback} (\u043e\u0446\u0435\u043d\u043a\u0430: {score}/5)"
    if score is not None:
        return f"\u041e\u0446\u0435\u043d\u043a\u0430: {score}/5"
    return "-"


def _appeal_answer(session: dict) -> str:
    feedback = _safe(session.get("appeal_feedback"))
    decision = _safe(session.get("appeal_decision"))
    if feedback == "-" and decision == "-":
        return "-"
    if feedback == "-":
        return f"\u0420\u0435\u0448\u0435\u043d\u0438\u0435: {decision}"
    if decision == "-":
        return feedback
    return f"{feedback} (\u0440\u0435\u0448\u0435\u043d\u0438\u0435: {decision})"


def _learning_block(sessions: list[dict]) -> list[str]:
    scored = [s for s in sessions if s.get("llm_score") is not None]
    if not scored:
        return [
            "\u0424\u0430\u043a\u0442\u043e\u0440 \u043e\u0431\u0443\u0447\u0435\u043d\u0438\u044f:",
            "- \u0417\u0430 \u043f\u0435\u0440\u0438\u043e\u0434 \u043d\u0435\u0442 \u043e\u0446\u0435\u043d\u0451\u043d\u043d\u044b\u0445 \u043e\u0442\u0432\u0435\u0442\u043e\u0432.",
        ]

    scores = [int(s["llm_score"]) for s in scored]
    avg = sum(scores) / len(scores)

    split = max(1, len(scores) // 2)
    first_part = scores[:split]
    second_part = scores[split:] if scores[split:] else scores[:split]
    first_avg = sum(first_part) / len(first_part)
    second_avg = sum(second_part) / len(second_part)
    delta = second_avg - first_avg

    if delta > 0.15:
        trend = "\u0440\u043e\u0441\u0442"
    elif delta < -0.15:
        trend = "\u0441\u043f\u0430\u0434"
    else:
        trend = "\u0441\u0442\u0430\u0431\u0438\u043b\u044c\u043d\u043e"

    appeals = sum(1 for s in sessions if _safe(s.get("appeal_text")) != "-")

    return [
        "\u0424\u0430\u043a\u0442\u043e\u0440 \u043e\u0431\u0443\u0447\u0435\u043d\u0438\u044f:",
        f"- \u041e\u0446\u0435\u043d\u0451\u043d\u043d\u044b\u0445 \u0437\u0430\u0434\u0430\u043d\u0438\u0439: {len(scored)}",
        f"- \u0421\u0440\u0435\u0434\u043d\u044f\u044f \u043e\u0446\u0435\u043d\u043a\u0430: {avg:.2f}/5",
        f"- \u0414\u0438\u043d\u0430\u043c\u0438\u043a\u0430 (\u043f\u0435\u0440\u0432\u0430\u044f \u043f\u043e\u043b\u043e\u0432\u0438\u043d\u0430 -> \u0432\u0442\u043e\u0440\u0430\u044f): {first_avg:.2f} -> {second_avg:.2f} ({delta:+.2f}, {trend})",
        f"- \u0410\u043f\u0435\u043b\u043b\u044f\u0446\u0438\u0439: {appeals}",
    ]


def _metric_guidance(sessions: list[dict]) -> list[str]:
    scored = [s for s in sessions if s.get("llm_score") is not None]
    if not scored:
        return []

    scores = [int(s["llm_score"]) for s in scored]
    avg = sum(scores) / len(scores)
    weak = sum(1 for score in scores if score <= 2)

    if avg < 3:
        step = "Сначала давай две версии ответа: очевидную и неочевидную. В сдачу бери вторую."
        target = "Цель на следующую сессию: сдвинуть средний балл до 3.0+."
    elif avg < 4:
        step = "Добавляй в каждый ответ одно неожиданное ограничение + один рабочий кейс."
        target = "Цель на следующую сессию: минимум половина ответов на 4/5."
    else:
        step = "Удерживай уровень: проверяй каждый ответ на риски и применимость перед отправкой."
        target = "Цель на следующую сессию: стабильно 4+/5 без просадок."

    return [
        "",
        "Как подступиться к метрике:",
        f"- Слабых ответов (<=2/5): {weak}",
        f"- Шаг: {step}",
        f"- {target}",
    ]


def _task_title(session: dict) -> str:
    mode = MODE_NAMES.get(session.get("mode"), session.get("mode") or "-")
    ex_name = EXERCISE_TYPE_NAMES.get(session.get("exercise_type"), session.get("exercise_type") or "-")
    level = session.get("exercise_level")
    if level:
        return f"{mode} | {ex_name} | \u0443\u0440.{level}"
    return f"{mode} | {ex_name}"


def _report_sessions(data: dict) -> list[dict]:
    sessions = data.get("sessions", [])
    return [
        s
        for s in sessions
        if _safe(s.get("user_response")) != "-"
        or s.get("llm_score") is not None
        or _safe(s.get("llm_feedback")) != "-"
        or _safe(s.get("appeal_text")) != "-"
        or _safe(s.get("appeal_feedback")) != "-"
    ]


def _build_report_text(data: dict) -> str:
    today = date.today().isoformat()
    sessions = _report_sessions(data)

    lines = [
        "CREATIVE WORKOUT REPORT",
        f"\u0414\u0430\u0442\u0430 \u043e\u0442\u0447\u0451\u0442\u0430: {today}",
        f"\u041f\u0435\u0440\u0438\u043e\u0434: \u043f\u043e\u0441\u043b\u0435\u0434\u043d\u0438\u0435 {data['days']} \u0434\u043d\u0435\u0439",
        f"\u0421\u0442\u0440\u0438\u043a: {data['streak']} \u0434\u043d.",
        "",
    ]

    lines.extend(_learning_block(sessions))
    lines.extend(_metric_guidance(sessions))
    lines.append("")
    lines.append("\u041f\u043e \u043a\u0430\u0436\u0434\u043e\u043c\u0443 \u0437\u0430\u0434\u0430\u043d\u0438\u044e:")

    if not sessions:
        lines.append("- \u0417\u0430 \u043f\u0435\u0440\u0438\u043e\u0434 \u043d\u0435\u0442 \u0434\u0430\u043d\u043d\u044b\u0445.")
        return "\n".join(lines)

    for idx, session in enumerate(sessions, start=1):
        lines.append("")
        lines.append(f"[{idx}]")
        lines.append(f"\u0434\u0430\u0442\u0430: {_safe(session.get('date'))}")
        lines.append(f"\u0437\u0430\u0434\u0430\u043d\u0438\u0435: {_task_title(session)}")
        lines.append(f"\u043c\u043e\u0439 \u043e\u0442\u0432\u0435\u0442: {_safe(session.get('user_response'))}")
        lines.append(f"\u043e\u0442\u0432\u0435\u0442 \u0431\u043e\u0442\u0430: {_bot_answer(session)}")
        lines.append(f"\u0430\u043f\u0435\u043b\u043b\u044f\u0446\u0438\u044f: {_safe(session.get('appeal_text'))}")
        lines.append(f"\u043e\u0442\u0432\u0435\u0442 \u043d\u0430 \u0430\u043f\u0435\u043b\u043b\u044f\u0446\u0438\u044e: {_appeal_answer(session)}")

    return "\n".join(lines)


@router.message(Command("report"))
@router.message(F.text == "\U0001f4cb \u041e\u0442\u0447\u0451\u0442")
async def cmd_report(message: Message) -> None:
    user_id = message.from_user.id
    await ensure_user(user_id, message.from_user.username)

    data = await get_weekly_report_data(user_id, days=7)
    sessions = _report_sessions(data)
    if not sessions:
        await message.answer("\u0417\u0430 \u043f\u043e\u0441\u043b\u0435\u0434\u043d\u0438\u0435 7 \u0434\u043d\u0435\u0439 \u043d\u0435\u0442 \u0434\u0430\u043d\u043d\u044b\u0445 \u0434\u043b\u044f \u043e\u0442\u0447\u0451\u0442\u0430.")
        return

    report_text = _build_report_text(data)
    filename = f"workout_report_{date.today().isoformat()}.txt"
    doc = BufferedInputFile(report_text.encode("utf-8-sig"), filename=filename)

    await message.answer_document(
        doc,
        caption=(
            "\u041a\u0440\u0430\u0442\u043a\u0438\u0439 \u043e\u0442\u0447\u0451\u0442: \u0434\u0430\u0442\u0430, \u0437\u0430\u0434\u0430\u043d\u0438\u0435, \u0432\u0430\u0448 \u043e\u0442\u0432\u0435\u0442, \u043e\u0442\u0432\u0435\u0442 \u0431\u043e\u0442\u0430, \u0430\u043f\u0435\u043b\u043b\u044f\u0446\u0438\u044f \u0438 \u0440\u0435\u0448\u0435\u043d\u0438\u0435 \u043f\u043e \u043d\u0435\u0439."
        ),
    )
