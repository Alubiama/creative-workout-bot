"""Weekly report: /report command."""
import logging
from datetime import date

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile

from database.queries import ensure_user, get_weekly_report_data

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

DIFFICULTY_LABELS = {
    "easy": "Легко 😴",
    "ok": "Нормально 😐",
    "hard": "Сложно 🔥",
    None: "—",
}


def _build_report_text(data: dict) -> str:
    today = date.today().isoformat()
    lines = [
        f"═══ WEEKLY REPORT — Creative Workout Bot ═══",
        f"Дата: {today} | Период: последние {data['days']} дней",
        f"Стрик: {data['streak']} дн.",
        "",
    ]

    sessions = data["sessions"]
    if not sessions:
        lines.append("Сессий за период не было.")
    else:
        # Group by date
        by_date: dict[str, list] = {}
        for s in sessions:
            d = s["date"] or "unknown"
            by_date.setdefault(d, []).append(s)

        lines.append(f"СЕССИИ ({len(sessions)} всего):")
        lines.append("─" * 40)

        for day in sorted(by_date.keys()):
            lines.append(f"\n📅 {day}")
            for s in by_date[day]:
                mode_icon = "🏠" if s["mode"] == "deep" else "🚇"
                ex_name = EXERCISE_TYPE_NAMES.get(s["exercise_type"], s["exercise_type"])
                score = s["llm_score"] or "—"
                diff = DIFFICULTY_LABELS.get(s["user_difficulty"], "—")
                resp_time = f"{s['response_time_sec']}с" if s["response_time_sec"] else "—"

                lines.append(
                    f"  {mode_icon} {ex_name} (ур.{s['exercise_level']}) | "
                    f"Оценка: {score}/5 | {diff} | ⏱ {resp_time}"
                )
                if s["user_response"]:
                    # Truncate long responses
                    resp = s["user_response"]
                    if len(resp) > 200:
                        resp = resp[:200] + "..."
                    lines.append(f"  └ Ответ: {resp}")

    # Incubations
    incubations = data["incubations"]
    if incubations:
        lines.append("")
        lines.append(f"ИНКУБАЦИИ ({len(incubations)}):")
        lines.append("─" * 40)
        for inc in incubations:
            lines.append(f"\n🌱 Задача: {inc['task_text']}")
            if inc["answer_text"]:
                lines.append(f"   Ответ: {inc['answer_text']}")
            else:
                lines.append("   Ответ: ещё не дан")

    # Progress summary
    progress = [p for p in data["progress"] if p["sessions_count"] > 0]
    if progress:
        lines.append("")
        lines.append("ПРОГРЕСС ПО ТИПАМ:")
        lines.append("─" * 40)
        for p in sorted(progress, key=lambda x: x["avg_score"]):
            name = EXERCISE_TYPE_NAMES.get(p["exercise_type"], p["exercise_type"])
            lines.append(
                f"  {name}: ур.{p['current_level']} | "
                f"сессий {p['sessions_count']} | ср.оценка {p['avg_score']:.1f}"
            )

    lines.append("")
    lines.append("═" * 43)
    lines.append("Скинь этот файл Claude для разбора недели.")

    return "\n".join(lines)


@router.message(Command("report"))
@router.message(F.text == "📋 Отчёт")
async def cmd_report(message: Message) -> None:
    user_id = message.from_user.id
    await ensure_user(user_id, message.from_user.username)

    data = await get_weekly_report_data(user_id, days=7)

    if not data["sessions"] and not data["incubations"]:
        await message.answer(
            "За последние 7 дней данных нет. Потренируйся сначала 😏"
        )
        return

    report_text = _build_report_text(data)

    # Send as .txt file — удобно скинуть в Claude
    filename = f"workout_report_{date.today().isoformat()}.txt"
    file_bytes = report_text.encode("utf-8")
    doc = BufferedInputFile(file_bytes, filename=filename)

    await message.answer_document(
        doc,
        caption=(
            "Твой отчёт за неделю 👆\n\n"
            "Скинь этот файл в чат с Claude — "
            "он разберёт что происходит, что растёт, где застрял."
        ),
    )
