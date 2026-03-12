"""Improved evaluation and appeal flow for creative workout sessions."""
import json
import logging

from llm.client import ask

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — требовательный, но полезный тренер по креативному мышлению.
Оцени ответ не абстрактно, а по тому, помогает ли он человеку мыслить более оригинально и прикладно.

Контекст пользователя: моушен-дизайнер / 3D-художник, работает с клиентскими брифами и концепциями.

Верни ТОЛЬКО JSON без markdown:
{
  "score": <1-5>,
  "what_was_predictable": "<что было слишком очевидным>",
  "unexpected_angle": "<какой сильный угол пользователь не использовал>",
  "professional_link": "<как это связано с реальной креативной работой>",
  "feedback_text": "<короткий честный вердикт, 2-4 предложения>",
  "next_step": "<одно конкретное действие для следующей попытки>"
}

Шкала:
1 — банально, почти без усилия
2 — есть попытка, но ход в основном очевидный
3 — есть рабочие моменты, но не хватает силы или глубины
4 — заметно неочевидно и полезно
5 — сильный, точный и оригинальный ответ"""

APPEAL_SYSTEM_PROMPT = """Ты — тот же тренер, но теперь рассматриваешь апелляцию пользователя на свою оценку.
Твоя задача — быть честным, а не защищать исходный вердикт любой ценой.
Если аргумент пользователя сильный, пересмотри балл. Если аргумент слабый, оставь балл и ясно объясни почему.

Верни ТОЛЬКО JSON без markdown:
{
  "score": <1-5>,
  "decision": "upheld" | "revised",
  "appeal_feedback": "<что в аргументе пользователя реально убедительно или неубедительно>",
  "feedback_text": "<обновленный финальный вердикт>",
  "next_step": "<одно конкретное действие для следующей попытки>"
}"""


def _strip_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


async def evaluate_response(
    exercise_type: str,
    exercise_level: int,
    exercise_prompt: str,
    user_response: str,
) -> dict:
    user_message = (
        f"Тип упражнения: {exercise_type}, уровень {exercise_level}\n\n"
        f"Задание:\n{exercise_prompt}\n\n"
        f"Ответ пользователя:\n{user_response}"
    )
    try:
        raw = await ask(system=SYSTEM_PROMPT, user=user_message, max_tokens=700)
        result = json.loads(_strip_json(raw))
        for key in ("score", "feedback_text", "unexpected_angle", "next_step"):
            if key not in result:
                raise ValueError(f"Missing key: {key}")
        return result
    except Exception as exc:
        logger.error("Evaluation failed: %s", exc)
        return {
            "score": 3,
            "what_was_predictable": "—",
            "unexpected_angle": "—",
            "professional_link": "—",
            "feedback_text": "Не удалось получить оценку. Попробуем еще раз позже.",
            "next_step": "Попробуй дать на один ход менее очевидный ответ и привязать его к рабочему контексту.",
        }


async def appeal_evaluation(
    exercise_type: str,
    exercise_level: int,
    exercise_prompt: str,
    user_response: str,
    original_evaluation: dict,
    user_appeal: str,
) -> dict:
    user_message = (
        f"Тип упражнения: {exercise_type}, уровень {exercise_level}\n\n"
        f"Задание:\n{exercise_prompt}\n\n"
        f"Ответ пользователя:\n{user_response}\n\n"
        f"Исходная оценка:\n{json.dumps(original_evaluation, ensure_ascii=False)}\n\n"
        f"Апелляция пользователя:\n{user_appeal}"
    )
    try:
        raw = await ask(system=APPEAL_SYSTEM_PROMPT, user=user_message, max_tokens=700)
        result = json.loads(_strip_json(raw))
        for key in ("score", "decision", "appeal_feedback", "feedback_text", "next_step"):
            if key not in result:
                raise ValueError(f"Missing key: {key}")
        return result
    except Exception as exc:
        logger.error("Appeal evaluation failed: %s", exc)
        return {
            "score": original_evaluation.get("score", 3),
            "decision": "upheld",
            "appeal_feedback": "Апелляцию не удалось разобрать, поэтому исходный балл оставлен без изменения.",
            "feedback_text": original_evaluation.get("feedback_text", "Исходная оценка сохранена."),
            "next_step": original_evaluation.get(
                "next_step",
                "Сделай следующий ответ конкретнее и менее предсказуемым.",
            ),
        }



def metric_improvement_tip(score: int) -> str:
    if score <= 2:
        return "\u0427\u0442\u043e\u0431\u044b \u043f\u043e\u0434\u043d\u044f\u0442\u044c \u0431\u0430\u043b\u043b: \u0441\u0434\u0435\u043b\u0430\u0439 2 \u0432\u0435\u0440\u0441\u0438\u0438 \u043e\u0442\u0432\u0435\u0442\u0430 (\u0431\u0430\u0437\u0430 \u0438 \u043d\u0435\u043e\u0436\u0438\u0434\u0430\u043d\u043d\u044b\u0439 \u0445\u043e\u0434) \u0438 \u0432\u044b\u0431\u0435\u0440\u0438 \u0432\u0442\u043e\u0440\u0443\u044e."
    if score == 3:
        return "\u0427\u0442\u043e\u0431\u044b \u0432\u044b\u0439\u0442\u0438 \u043d\u0430 4/5: \u0434\u043e\u0431\u0430\u0432\u044c \u043e\u0434\u043d\u043e \u043d\u0435\u043e\u0447\u0435\u0432\u0438\u0434\u043d\u043e\u0435 \u043e\u0433\u0440\u0430\u043d\u0438\u0447\u0435\u043d\u0438\u0435 \u0438 \u043f\u0440\u0438\u0432\u044f\u0436\u0438 \u043e\u0442\u0432\u0435\u0442 \u043a \u0440\u0435\u0430\u043b\u044c\u043d\u043e\u043c\u0443 \u043a\u0435\u0439\u0441\u0443."
    if score == 4:
        return "\u0427\u0442\u043e\u0431\u044b \u0434\u043e\u0439\u0442\u0438 \u0434\u043e 5/5: \u0434\u043e\u0431\u0430\u0432\u044c \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0443 \u0440\u0438\u0441\u043a\u043e\u0432 \u0438 \u043a\u0440\u0438\u0442\u0435\u0440\u0438\u0439 \u043f\u0440\u0438\u043c\u0435\u043d\u0435\u043d\u0438\u043c\u043e\u0441\u0442\u0438 (\u0433\u0434\u0435 \u044d\u0442\u043e \u0441\u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442 / \u043d\u0435 \u0441\u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442)."
    return "\u0414\u0435\u0440\u0436\u0438 \u0443\u0440\u043e\u0432\u0435\u043d\u044c: \u0432 \u043a\u0430\u0436\u0434\u043e\u0439 \u043d\u043e\u0432\u043e\u0439 \u043f\u043e\u043f\u044b\u0442\u043a\u0435 \u043c\u0435\u043d\u044f\u0439 \u043e\u0434\u0438\u043d \u043a\u043b\u044e\u0447\u0435\u0432\u043e\u0439 \u043f\u0430\u0440\u0430\u043c\u0435\u0442\u0440 (\u0440\u0430\u043a\u0443\u0440\u0441, \u043a\u043e\u043d\u0442\u0435\u043a\u0441\u0442 \u0438\u043b\u0438 \u043e\u0433\u0440\u0430\u043d\u0438\u0447\u0435\u043d\u0438\u0435)."

def format_feedback(eval_result: dict) -> str:
    score = int(eval_result.get("score", 0) or 0)
    score_bar = "█" * score + "░" * max(0, 5 - score)

    lines = [
        f"*Оценка: {score}/5* {score_bar}\n",
        eval_result.get("feedback_text", ""),
    ]

    predictable = (eval_result.get("what_was_predictable") or "").strip()
    if predictable and predictable != "—":
        lines.append(f"\n*Что было слишком очевидным:* {predictable}")

    angle = (eval_result.get("unexpected_angle") or "").strip()
    if angle and angle != "—":
        lines.append(f"\n*Какой угол ты не использовал:* {angle}")

    professional_link = (eval_result.get("professional_link") or "").strip()
    if professional_link and professional_link != "—":
        lines.append(f"\n*Где это пригодится в работе:* {professional_link}")

    next_step = (eval_result.get("next_step") or "").strip()
    if next_step:
        lines.append(f"\n*Что исправить в следующей попытке:* {next_step}")

    lines.append(f"\n*\u041a\u0430\u043a \u043f\u043e\u0434\u043d\u044f\u0442\u044c \u043c\u0435\u0442\u0440\u0438\u043a\u0443:* {metric_improvement_tip(score)}")

    return "\n".join(lines)


def format_appeal_feedback(appeal_result: dict) -> str:
    score = int(appeal_result.get("score", 0) or 0)
    decision = appeal_result.get("decision", "upheld")
    verdict = "Вердикт пересмотрен" if decision == "revised" else "Исходный вердикт оставлен"
    score_bar = "█" * score + "░" * max(0, 5 - score)

    lines = [
        f"*{verdict}*\n",
        f"*Новый балл: {score}/5* {score_bar}",
    ]

    appeal_feedback = (appeal_result.get("appeal_feedback") or "").strip()
    if appeal_feedback:
        lines.append(f"\n*По твоему аргументу:* {appeal_feedback}")

    feedback_text = (appeal_result.get("feedback_text") or "").strip()
    if feedback_text:
        lines.append(f"\n{feedback_text}")

    next_step = (appeal_result.get("next_step") or "").strip()
    if next_step:
        lines.append(f"\n*Что исправить в следующей попытке:* {next_step}")

    lines.append(f"\n*\u041a\u0430\u043a \u043f\u043e\u0434\u043d\u044f\u0442\u044c \u043c\u0435\u0442\u0440\u0438\u043a\u0443:* {metric_improvement_tip(score)}")

    return "\n".join(lines)
