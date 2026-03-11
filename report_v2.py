"""Improved weekly report with full answers and clearer session status."""
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

DIFFICULTY_LABELS = {
    "easy": "\u041b\u0435\u0433\u043a\u043e \U0001f634",
    "ok": "\u041d\u043e\u0440\u043c\u0430\u043b\u044c\u043d\u043e \U0001f610",
    "hard": "\u0421\u043b\u043e\u0436\u043d\u043e \U0001f525",
    None: "\u2014",
}


def _indent_block(text: str, prefix: str = "      ") -> str:
    return "\n".join(f"{prefix}{line}" if line else prefix.rstrip() for line in text.splitlines())


def _session_status(session: dict) -> str:
    if session.get("llm_score") is None and not session.get("user_response"):
        return "\u043d\u0435\u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u043e"
    return "\u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u043e"


def _build_report_text(data: dict) -> str:
    today = date.today().isoformat()
    lines = [
        "\u2550\u2550\u2550 WEEKLY REPORT \u2014 Creative Workout Bot \u2550\u2550\u2550",
        f"\u0414\u0430\u0442\u0430: {today} | \u041f\u0435\u0440\u0438\u043e\u0434: \u043f\u043e\u0441\u043b\u0435\u0434\u043d\u0438\u0435 {data['days']} \u0434\u043d\u0435\u0439",
        f"\u0421\u0442\u0440\u0438\u043a: {data['streak']} \u0434\u043d.",
    ]

    focus = data.get("focus_exercise_type")
    if focus:
        lines.append(f"\u0424\u043e\u043a\u0443\u0441-\u0442\u0440\u0435\u043a: {EXERCISE_TYPE_NAMES.get(focus, focus)}")
    lines.append("")

    sessions = data["sessions"]
    completed_sessions = [session for session in sessions if session.get("llm_score") is not None]
    incomplete_sessions = [session for session in sessions if session.get("llm_score") is None]

    if not sessions:
        lines.append("\u0421\u0435\u0441\u0441\u0438\u0439 \u0437\u0430 \u043f\u0435\u0440\u0438\u043e\u0434 \u043d\u0435 \u0431\u044b\u043b\u043e.")
    else:
        if completed_sessions:
            lines.append(f"\u0417\u0410\u0412\u0415\u0420\u0428\u0401\u041d\u041d\u042b\u0415 \u0421\u0415\u0421\u0421\u0418\u0418 ({len(completed_sessions)}):")
            lines.append("\u2500" * 56)
            by_date: dict[str, list] = {}
            for session in completed_sessions:
                day = session["date"] or "unknown"
                by_date.setdefault(day, []).append(session)

            for day in sorted(by_date.keys()):
                lines.append(f"\n\U0001f4c5 {day}")
                for idx, session in enumerate(by_date[day], start=1):
                    mode_icon = "\U0001f3e0" if session["mode"] == "deep" else "\U0001f687"
                    ex_name = EXERCISE_TYPE_NAMES.get(session["exercise_type"], session["exercise_type"])
                    score = session["llm_score"]
                    diff = DIFFICULTY_LABELS.get(session["user_difficulty"], "\u2014")
                    resp_time = f"{session['response_time_sec']}\u0441" if session["response_time_sec"] else "\u2014"

                    lines.append(
                        f"  {idx}. {mode_icon} {ex_name} (\u0443\u0440.{session['exercise_level']}) | "
                        f"\u041e\u0446\u0435\u043d\u043a\u0430: {score}/5 | {diff} | \u23f1 {resp_time}"
                    )

                    initial_score = session.get("initial_llm_score")
                    appeal_decision = session.get("appeal_decision")
                    if initial_score is not None:
                        lines.append(f"      \u0418\u0441\u0445\u043e\u0434\u043d\u0430\u044f \u043e\u0446\u0435\u043d\u043a\u0430: {initial_score}/5")
                    if appeal_decision:
                        lines.append(f"      \u0410\u043f\u0435\u043b\u043b\u044f\u0446\u0438\u044f: {appeal_decision}")

                    response = session.get("user_response")
                    if response:
                        lines.append("      \u041e\u0442\u0432\u0435\u0442:")
                        lines.append(_indent_block(response))
                    else:
                        lines.append("      \u041e\u0442\u0432\u0435\u0442: \u2014")

                    lines.append("")

        if incomplete_sessions:
            lines.append(f"\u041d\u0415\u0417\u0410\u0412\u0415\u0420\u0428\u0401\u041d\u041d\u042b\u0415 \u041f\u041e\u041f\u042b\u0422\u041a\u0418 ({len(incomplete_sessions)}):")
            lines.append("\u2500" * 56)
            for idx, session in enumerate(incomplete_sessions, start=1):
                mode_icon = "\U0001f3e0" if session["mode"] == "deep" else "\U0001f687"
                ex_name = EXERCISE_TYPE_NAMES.get(session["exercise_type"], session["exercise_type"])
                resp_time = f"{session['response_time_sec']}\u0441" if session["response_time_sec"] else "\u2014"
                lines.append(
                    f"  {idx}. {mode_icon} {ex_name} (\u0443\u0440.{session['exercise_level']}) | \u23f1 {resp_time} | \u043d\u0435\u0442 \u043e\u0446\u0435\u043d\u043a\u0438 / \u043d\u0435\u0442 \u043e\u0442\u0432\u0435\u0442\u0430"
                )
            lines.append("")

    incubations = data["incubations"]
    if incubations:
        lines.append("\u0418\u041d\u041a\u0423\u0411\u0410\u0426\u0418\u0418:")
        lines.append("\u2500" * 56)
        for idx, incubation in enumerate(incubations, start=1):
            lines.append(f"  {idx}. \u0417\u0430\u0434\u0430\u0447\u0430:")
            lines.append(_indent_block(incubation["task_text"]))
            if incubation["answer_text"]:
                lines.append("      \u041e\u0442\u0432\u0435\u0442:")
                lines.append(_indent_block(incubation["answer_text"]))
            else:
                lines.append("      \u041e\u0442\u0432\u0435\u0442: \u0435\u0449\u0451 \u043d\u0435 \u0434\u0430\u043d")
            lines.append("")

    progress = [item for item in data["progress"] if item["sessions_count"] > 0]
    if progress:
        lines.append("\u041f\u0420\u041e\u0413\u0420\u0415\u0421\u0421 \u041f\u041e \u0422\u0418\u041f\u0410\u041c:")
        lines.append("\u2500" * 56)
        for item in sorted(progress, key=lambda x: x["avg_score"]):
            name = EXERCISE_TYPE_NAMES.get(item["exercise_type"], item["exercise_type"])
            lines.append(
                f"  {name}: \u0443\u0440.{item['current_level']} | "
                f"\u0441\u0435\u0441\u0441\u0438\u0439 {item['sessions_count']} | \u0441\u0440\u0435\u0434\u043d\u044f\u044f \u043e\u0446\u0435\u043d\u043a\u0430 {item['avg_score']:.1f}"
            )

    lines.append("")
    lines.append("\u2550\u2550\u2550 \u041a\u041e\u041d\u0415\u0426 \u041e\u0422\u0427\u0401\u0422\u0410 \u2550\u2550\u2550")
    lines.append("\u0412 \u044d\u0442\u043e\u043c \u0444\u0430\u0439\u043b\u0435 \u043e\u0442\u0432\u0435\u0442\u044b \u043d\u0435 \u043e\u0431\u0440\u0435\u0437\u0430\u044e\u0442\u0441\u044f: \u0435\u0433\u043e \u043c\u043e\u0436\u043d\u043e \u043e\u0442\u0434\u0430\u0432\u0430\u0442\u044c \u0434\u0440\u0443\u0433\u043e\u0439 \u043c\u043e\u0434\u0435\u043b\u0438 \u0434\u043b\u044f \u043d\u043e\u0440\u043c\u0430\u043b\u044c\u043d\u043e\u0433\u043e \u0440\u0430\u0437\u0431\u043e\u0440\u0430.")
    return "\n".join(lines)


@router.message(Command("report"))
@router.message(F.text == "\U0001f4cb \u041e\u0442\u0447\u0451\u0442")
async def cmd_report(message: Message) -> None:
    user_id = message.from_user.id
    await ensure_user(user_id, message.from_user.username)

    data = await get_weekly_report_data(user_id, days=7)

    if not data["sessions"] and not data["incubations"]:
        await message.answer("\u0417\u0430 \u043f\u043e\u0441\u043b\u0435\u0434\u043d\u0438\u0435 7 \u0434\u043d\u0435\u0439 \u0434\u0430\u043d\u043d\u044b\u0445 \u043d\u0435\u0442. \u041f\u043e\u0442\u0440\u0435\u043d\u0438\u0440\u0443\u0439\u0441\u044f \u0441\u043d\u0430\u0447\u0430\u043b\u0430 \U0001f60f")
        return

    report_text = _build_report_text(data)
    filename = f"workout_report_{date.today().isoformat()}.txt"
    doc = BufferedInputFile(report_text.encode("utf-8"), filename=filename)

    await message.answer_document(
        doc,
        caption=(
            "\u0422\u0432\u043e\u0439 \u043e\u0442\u0447\u0451\u0442 \u0437\u0430 \u043d\u0435\u0434\u0435\u043b\u044e.\n\n"
            "\u0422\u0435\u043f\u0435\u0440\u044c \u043e\u0442\u0432\u0435\u0442\u044b \u0432 \u0444\u0430\u0439\u043b\u0435 \u043d\u0435 \u0440\u0435\u0436\u0443\u0442\u0441\u044f \u043c\u043d\u043e\u0433\u043e\u0442\u043e\u0447\u0438\u0435\u043c, \u0442\u0430\u043a \u0447\u0442\u043e \u0435\u0433\u043e \u043c\u043e\u0436\u043d\u043e \u043d\u043e\u0440\u043c\u0430\u043b\u044c\u043d\u043e \u0430\u043d\u0430\u043b\u0438\u0437\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0434\u0430\u043b\u044c\u0448\u0435."
        ),
    )
