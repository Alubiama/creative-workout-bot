"""Exercise registry — выбор упражнения на основе прогресса и режима."""
import random
from dataclasses import dataclass
from typing import Optional

from exercises import aut, rat, forced, constraints, triz, pitch, frames, quantity
from config import MODE_DEEP, MODE_QUICK

EXERCISE_TYPES = [
    aut.EXERCISE_TYPE,
    rat.EXERCISE_TYPE,
    forced.EXERCISE_TYPE,
    constraints.EXERCISE_TYPE,
    triz.EXERCISE_TYPE,
    pitch.EXERCISE_TYPE,
    frames.EXERCISE_TYPE,
    quantity.EXERCISE_TYPE,
]

# ── Дивергентные: генерация, расширение, беглость ────────────────────────────
DIVERGENT_TYPES = [
    aut.EXERCISE_TYPE,         # Alternative Uses
    constraints.EXERCISE_TYPE, # Constraint thinking
    triz.EXERCISE_TYPE,        # TRIZ
    pitch.EXERCISE_TYPE,       # Pitch
    frames.EXERCISE_TYPE,      # Frame mixing
    quantity.EXERCISE_TYPE,    # Quantity drill
    forced.EXERCISE_TYPE,      # Forced connections
]

# ── Конвергентные: выбор, оценка, фокус ──────────────────────────────────────
CONVERGENT_TYPES = [
    rat.EXERCISE_TYPE,  # Remote Associates — найти одно слово-связь
    "eval_ideas",       # Оценка идей — выбрать самый оригинальный ответ
]

# Упражнения для быстрого режима (короткие ответы)
QUICK_TYPES = [
    rat.EXERCISE_TYPE,
    forced.EXERCISE_TYPE,
    quantity.EXERCISE_TYPE,
    aut.EXERCISE_TYPE,
]

# Упражнения для онбординга — baseline
ONBOARDING_SEQUENCE = [
    aut.EXERCISE_TYPE,
    forced.EXERCISE_TYPE,
    rat.EXERCISE_TYPE,
]


@dataclass
class SelectedExercise:
    exercise_type: str
    level: int
    prompt: Optional[str]  # None для eval_ideas (генерируется динамически)


def select_exercise(
    mode: str,
    progress: dict[str, dict],
    seed: int | None = None,
) -> SelectedExercise:
    """Select a single exercise based on mode and user progress."""
    if seed is None:
        import time
        seed = int(time.time())

    rng = random.Random(seed)
    pool = QUICK_TYPES if mode == MODE_QUICK else DIVERGENT_TYPES

    type_sessions = {
        t: progress.get(t, {}).get("sessions_count", 0)
        for t in pool
    }
    sorted_types = sorted(type_sessions.items(), key=lambda x: x[1])
    candidates = [t for t, _ in sorted_types[: max(1, len(sorted_types) // 2)]]
    exercise_type = rng.choice(candidates)

    level = progress.get(exercise_type, {}).get("current_level", 1)
    prompt = _build_prompt(exercise_type, level, seed)
    return SelectedExercise(exercise_type=exercise_type, level=level, prompt=prompt)


def select_onboarding_exercise(step: int) -> SelectedExercise:
    """Return fixed onboarding exercise by step (0-indexed)."""
    exercise_type = ONBOARDING_SEQUENCE[step]
    level = 1
    prompt = _build_prompt(exercise_type, level, seed=step)
    return SelectedExercise(exercise_type=exercise_type, level=level, prompt=prompt)


def select_session_exercises(
    mode: str,
    progress: dict[str, dict],
    count: int,
    seed: int | None = None,
) -> list[SelectedExercise]:
    """
    Select exercises for a session.

    Deep mode (count=3): дивергентное → конвергентное → дивергентное.
    Quick mode (count=1): одно упражнение из QUICK_TYPES.
    """
    import time
    if seed is None:
        seed = int(time.time())
    rng = random.Random(seed)

    # ── Quick: одно упражнение ────────────────────────────────────────────────
    if mode == MODE_QUICK or count == 1:
        pool = QUICK_TYPES
        type_sessions = {t: progress.get(t, {}).get("sessions_count", 0) for t in pool}
        sorted_types = sorted(type_sessions.items(), key=lambda x: x[1])
        chosen_types: list[str] = []
        for t, _ in sorted_types:
            if t not in chosen_types:
                chosen_types.append(t)
            if len(chosen_types) == count:
                break
        while len(chosen_types) < count:
            extras = [t for t in pool if t not in chosen_types] or pool[:]
            chosen_types.append(rng.choice(extras))

        exercises = []
        for i, ex_type in enumerate(chosen_types):
            level = progress.get(ex_type, {}).get("current_level", 1)
            prompt = _build_prompt(ex_type, level, seed + i)
            exercises.append(SelectedExercise(exercise_type=ex_type, level=level, prompt=prompt))
        return exercises

    # ── Deep: дивергентное → конвергентное → дивергентное ────────────────────
    # Шаг 1: выбираем два разных дивергентных упражнения
    div_sessions = {t: progress.get(t, {}).get("sessions_count", 0) for t in DIVERGENT_TYPES}
    sorted_div = sorted(div_sessions.items(), key=lambda x: x[1])

    div_type_0 = sorted_div[0][0]
    # Второй дивергентный — отличается от первого
    div_type_2_candidates = [t for t, _ in sorted_div if t != div_type_0]
    div_type_2 = div_type_2_candidates[0] if div_type_2_candidates else rng.choice(DIVERGENT_TYPES)

    div_level_0 = progress.get(div_type_0, {}).get("current_level", 1)
    div_level_2 = progress.get(div_type_2, {}).get("current_level", 1)

    ex_0 = SelectedExercise(
        exercise_type=div_type_0,
        level=div_level_0,
        prompt=_build_prompt(div_type_0, div_level_0, seed),
    )
    ex_2 = SelectedExercise(
        exercise_type=div_type_2,
        level=div_level_2,
        prompt=_build_prompt(div_type_2, div_level_2, seed + 2),
    )

    # Шаг 2: конвергентное — чередуем RAT и eval_ideas по сиду
    convergent_type = CONVERGENT_TYPES[seed % len(CONVERGENT_TYPES)]
    conv_level = progress.get(convergent_type, {}).get("current_level", 1)

    if convergent_type == "eval_ideas":
        # Промпт генерируется динамически после первого упражнения
        ex_1 = SelectedExercise(
            exercise_type="eval_ideas",
            level=div_level_0,  # берём уровень первого упражнения
            prompt=None,
        )
    else:
        ex_1 = SelectedExercise(
            exercise_type=convergent_type,
            level=conv_level,
            prompt=_build_prompt(convergent_type, conv_level, seed + 1),
        )

    return [ex_0, ex_1, ex_2]


def select_round_two(exercise_type: str, current_level: int, seed: int = 0) -> SelectedExercise:
    """Same exercise type but add one constraint layer."""
    prompt = _build_prompt(exercise_type, min(current_level + 1, 4), seed + 100)
    return SelectedExercise(
        exercise_type=exercise_type,
        level=min(current_level + 1, 4),
        prompt=prompt,
    )


def _build_prompt(exercise_type: str, level: int, seed: int = 0) -> str:
    if exercise_type == aut.EXERCISE_TYPE:
        ex = aut.get_exercise(level, seed)
        return ex.to_prompt()
    elif exercise_type == rat.EXERCISE_TYPE:
        return rat.get_exercise(level, seed)["prompt"]
    elif exercise_type == forced.EXERCISE_TYPE:
        return forced.get_exercise(level, seed)["prompt"]
    elif exercise_type == constraints.EXERCISE_TYPE:
        return constraints.get_exercise(level, seed)["prompt"]
    elif exercise_type == triz.EXERCISE_TYPE:
        return triz.get_exercise(level, seed)["prompt"]
    elif exercise_type == pitch.EXERCISE_TYPE:
        return pitch.get_exercise(level, seed)["prompt"]
    elif exercise_type == frames.EXERCISE_TYPE:
        return frames.get_exercise(level, seed)["prompt"]
    elif exercise_type == quantity.EXERCISE_TYPE:
        return quantity.get_exercise(level, seed)["prompt"]
    else:
        return f"Упражнение: {exercise_type} уровень {level}"
