"""Eval Ideas — оценка чужих ответов.

Бот показывает 3 ответа разной оригинальности на предыдущее упражнение.
Пользователь выбирает самый оригинальный и объясняет почему.

Исследования: тренировка оценки (evaluative thinking) даёт больший
эффект на развитие креативности чем только генерация идей.
"""
import json
import logging
from llm.client import ask

logger = logging.getLogger(__name__)

EXERCISE_TYPE = "eval_ideas"

_GENERATION_SYSTEM = """Ты — тренер по креативному мышлению.
Твоя задача: сгенерировать 3 ответа разного уровня оригинальности на упражнение.

Правила:
- Ответ A: предсказуемый, первое что приходит в голову, банальный
- Ответ B: нестандартный, есть идея, но исполнение среднее
- Ответ C: по-настоящему оригинальный — неожиданная связь, нетипичный домен или угол

Верни ТОЛЬКО JSON без markdown-обёрток:
{
  "a": "текст ответа A",
  "b": "текст ответа B",
  "c": "текст ответа C",
  "most_original": "c",
  "why_original": "одно предложение — в чём именно оригинальность ответа C"
}

Ответы должны быть реалистичными — как будто их написали реальные люди.
A — как написал бы человек который не старается.
B — как написал бы человек который старается но не вышел за очевидное.
C — как написал бы человек с действительно нетипичным мышлением."""


async def generate_exercise(
    prev_prompt: str,
    prev_type: str,
    level: int,
) -> dict:
    """
    Generate eval_ideas exercise based on previous exercise.
    Returns exercise dict with prompt, correct_answer, why_original.
    """
    user_msg = (
        f"Тип упражнения: {prev_type}\n\n"
        f"Задание:\n{prev_prompt}\n\n"
        "Сгенерируй 3 ответа разного уровня оригинальности."
    )

    try:
        raw = await ask(system=_GENERATION_SYSTEM, user=user_msg, max_tokens=600)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        a, b, c = data["a"], data["b"], data["c"]
        most_original = data.get("most_original", "c").lower()
        why = data.get("why_original", "")
    except Exception as e:
        logger.error("eval_ideas generation failed: %s", e)
        # Fallback — не падаем, даём заглушку
        a = "Стандартный предсказуемый ответ"
        b = "Нестандартный но не удивительный ответ"
        c = "Действительно неожиданный угол зрения"
        most_original = "c"
        why = "Неожиданная связь через нетипичный контекст"

    prompt = (
        "*Оценка идей*\n\n"
        "Три человека ответили на то же задание что и ты.\n"
        "Прочитай — и выбери самый оригинальный ответ.\n\n"
        f"*A.* {a}\n\n"
        f"*B.* {b}\n\n"
        f"*C.* {c}\n\n"
        "Напиши букву (A, B или C) и объясни почему именно этот ответ "
        "самый оригинальный. Что делает его неожиданным?"
    )

    return {
        "type": EXERCISE_TYPE,
        "level": level,
        "prompt": prompt,
        "correct_answer": most_original,
        "why_original": why,
    }
