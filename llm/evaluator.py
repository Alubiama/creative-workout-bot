"""Evaluate user responses to creative exercises."""
import json
import logging
from llm.client import ask

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — строгий, но справедливый тренер по креативному мышлению.
Твоя задача — дать конкретную и честную обратную связь на ответ пользователя.

Контекст: пользователь — моушен-дизайнер / 3D-художник, работает с клиентами в агентстве.
Цель тренировки: развить беглость, оригинальность, ассоциативность.

Никогда не говори просто "отлично" или "хорошо" — это бесполезно.
Будь прямым. Если ответ предсказуемый — скажи об этом.
Если есть интересные моменты — укажи конкретно какие и почему.

Верни ТОЛЬКО валидный JSON без markdown-обёрток, вот так:
{
  "score": <число 1-5>,
  "what_was_predictable": "<что было банальным или ожидаемым>",
  "unexpected_angle": "<один угол который пользователь НЕ назвал, но было бы интересно>",
  "professional_link": "<как это применимо к моушену / 3D / работе с клиентами>",
  "feedback_text": "<итоговая обратная связь, 2-4 предложения, прямая и конкретная>"
}

Шкала оценки (score):
1 — банально, предсказуемо, нет усилия
2 — есть попытка, но большинство ответов очевидны
3 — несколько интересных моментов, но есть потенциал
4 — оригинально, есть неожиданные связи
5 — исключительно — неожиданно и при этом точно"""


async def evaluate_response(
    exercise_type: str,
    exercise_level: int,
    exercise_prompt: str,
    user_response: str,
) -> dict:
    """
    Returns dict with keys: score, what_was_predictable, unexpected_angle,
    professional_link, feedback_text.
    Falls back to defaults on error.
    """
    user_message = (
        f"Тип упражнения: {exercise_type}, уровень {exercise_level}\n\n"
        f"Задание:\n{exercise_prompt}\n\n"
        f"Ответ пользователя:\n{user_response}"
    )
    try:
        raw = await ask(system=SYSTEM_PROMPT, user=user_message, max_tokens=600)
        # Strip potential markdown fences if model adds them
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        # Validate required keys
        for key in ("score", "feedback_text", "unexpected_angle"):
            if key not in result:
                raise ValueError(f"Missing key: {key}")
        return result
    except Exception as e:
        logger.error("Evaluation failed: %s", e)
        return {
            "score": 3,
            "what_was_predictable": "—",
            "unexpected_angle": "—",
            "professional_link": "—",
            "feedback_text": "Не удалось получить оценку. Попробуем в следующий раз.",
        }


def format_feedback(eval_result: dict) -> str:
    """Format evaluation result into a readable message."""
    score = eval_result.get("score", "?")
    score_bar = "⬛" * score + "⬜" * (5 - score)

    lines = [
        f"*Оценка: {score}/5* {score_bar}\n",
        eval_result.get("feedback_text", ""),
    ]

    predictable = eval_result.get("what_was_predictable", "").strip()
    if predictable and predictable != "—":
        lines.append(f"\n🔍 *Что было предсказуемо:* {predictable}")

    angle = eval_result.get("unexpected_angle", "").strip()
    if angle and angle != "—":
        lines.append(f"\n💡 *Угол который ты не назвал:* {angle}")

    prof_link = eval_result.get("professional_link", "").strip()
    if prof_link and prof_link != "—":
        lines.append(f"\n🎬 *В работе:* {prof_link}")

    return "\n".join(lines)
