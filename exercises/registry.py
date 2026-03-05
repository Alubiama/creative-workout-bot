"""Exercise registry — выбор упражнения на основе прогресса и режима."""
import random
from dataclasses import dataclass

from exercises import aut, rat, forced, constraints, triz, pitch, frames, quantity

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

# Упражнения для быстрого режима (короткие ответы)
QUICK_TYPES = [
    rat.EXERCISE_TYPE,
    forced.EXERCISE_TYPE,
    quantity.EXERCISE_TYPE,
    aut.EXERCISE_TYPE,
]

# Упражнения для глубокого режима (развёрнутые ответы)
DEEP_TYPES = [
    constraints.EXERCISE_TYPE,
    triz.EXERCISE_TYPE,
    pitch.EXERCISE_TYPE,
    frames.EXERCISE_TYPE,
    forced.EXERCISE_TYPE,
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
    prompt: str


def select_exercise(
    mode: str,  # 'deep' | 'quick'
    progress: dict[str, dict],  # {exercise_type: {current_level, sessions_count, ...}}
    seed: int | None = None,
) -> SelectedExercise:
    """Select exercise based on mode and user progress."""
    if seed is None:
        import time
        seed = int(time.time())

    rng = random.Random(seed)

    pool = QUICK_TYPES if mode == "quick" else DEEP_TYPES

    # Rotate: prefer types with fewer sessions in this pool
    type_sessions = {
        t: progress.get(t, {}).get("sessions_count", 0)
        for t in pool
    }
    # Pick from least-used types (bottom 50%)
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
    """Select `count` exercises of different types for a session."""
    import time
    if seed is None:
        seed = int(time.time())
    rng = random.Random(seed)

    pool = QUICK_TYPES if mode == "quick" else DEEP_TYPES

    # Sort by least used, pick `count` different types
    type_sessions = {
        t: progress.get(t, {}).get("sessions_count", 0)
        for t in pool
    }
    sorted_types = sorted(type_sessions.items(), key=lambda x: x[1])
    chosen_types: list[str] = []
    for t, _ in sorted_types:
        if t not in chosen_types:
            chosen_types.append(t)
        if len(chosen_types) == count:
            break
    # If pool smaller than count, repeat with shuffle
    while len(chosen_types) < count:
        extras = [t for t in pool if t not in chosen_types]
        if not extras:
            extras = pool[:]
        chosen_types.append(rng.choice(extras))

    exercises = []
    for i, ex_type in enumerate(chosen_types):
        level = progress.get(ex_type, {}).get("current_level", 1)
        prompt = _build_prompt(ex_type, level, seed + i)
        exercises.append(SelectedExercise(exercise_type=ex_type, level=level, prompt=prompt))
    return exercises


def select_round_two(exercise_type: str, current_level: int, seed: int = 0) -> SelectedExercise:
    """Same exercise type but add one constraint layer."""
    # For round two we bump difficulty by adding constraint framing
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
