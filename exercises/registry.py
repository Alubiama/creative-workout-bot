"""Exercise registry: choose exercises from progress, mode, and optional focus."""
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

DIVERGENT_TYPES = [
    aut.EXERCISE_TYPE,
    constraints.EXERCISE_TYPE,
    triz.EXERCISE_TYPE,
    pitch.EXERCISE_TYPE,
    frames.EXERCISE_TYPE,
    quantity.EXERCISE_TYPE,
    forced.EXERCISE_TYPE,
]

CONVERGENT_TYPES = [
    rat.EXERCISE_TYPE,
    "eval_ideas",
]

QUICK_TYPES = [
    rat.EXERCISE_TYPE,
    forced.EXERCISE_TYPE,
    quantity.EXERCISE_TYPE,
    aut.EXERCISE_TYPE,
]

ONBOARDING_SEQUENCE = [
    aut.EXERCISE_TYPE,
    forced.EXERCISE_TYPE,
    rat.EXERCISE_TYPE,
]


@dataclass
class SelectedExercise:
    exercise_type: str
    level: int
    prompt: Optional[str]


def select_exercise(
    mode: str,
    progress: dict[str, dict],
    seed: int | None = None,
    preferred_type: str | None = None,
) -> SelectedExercise:
    exercises = select_session_exercises(
        mode=mode,
        progress=progress,
        count=1,
        seed=seed,
        preferred_type=preferred_type,
    )
    return exercises[0]


def select_onboarding_exercise(step: int) -> SelectedExercise:
    exercise_type = ONBOARDING_SEQUENCE[step]
    level = 1
    prompt = _build_prompt(exercise_type, level, seed=step)
    return SelectedExercise(exercise_type=exercise_type, level=level, prompt=prompt)


def select_session_exercises(
    mode: str,
    progress: dict[str, dict],
    count: int,
    seed: int | None = None,
    preferred_type: str | None = None,
) -> list[SelectedExercise]:
    """Select exercises for a session, optionally forcing one exercise type."""
    import time

    if seed is None:
        seed = int(time.time())
    rng = random.Random(seed)

    if preferred_type:
        level = progress.get(preferred_type, {}).get("current_level", 1)
        return [
            SelectedExercise(
                exercise_type=preferred_type,
                level=level,
                prompt=_build_prompt(preferred_type, level, seed + i),
            )
            for i in range(count)
        ]

    if mode == MODE_QUICK or count == 1:
        pool = QUICK_TYPES
        type_sessions = {t: progress.get(t, {}).get("sessions_count", 0) for t in pool}
        sorted_types = sorted(type_sessions.items(), key=lambda x: x[1])
        chosen_types: list[str] = []
        for ex_type, _ in sorted_types:
            if ex_type not in chosen_types:
                chosen_types.append(ex_type)
            if len(chosen_types) == count:
                break
        while len(chosen_types) < count:
            extras = [t for t in pool if t not in chosen_types] or pool[:]
            chosen_types.append(rng.choice(extras))

        return [
            SelectedExercise(
                exercise_type=ex_type,
                level=progress.get(ex_type, {}).get("current_level", 1),
                prompt=_build_prompt(ex_type, progress.get(ex_type, {}).get("current_level", 1), seed + i),
            )
            for i, ex_type in enumerate(chosen_types)
        ]

    div_sessions = {t: progress.get(t, {}).get("sessions_count", 0) for t in DIVERGENT_TYPES}
    sorted_div = sorted(div_sessions.items(), key=lambda x: x[1])

    div_type_0 = sorted_div[0][0]
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

    convergent_type = CONVERGENT_TYPES[seed % len(CONVERGENT_TYPES)]
    conv_level = progress.get(convergent_type, {}).get("current_level", 1)

    if convergent_type == "eval_ideas":
        ex_1 = SelectedExercise(
            exercise_type="eval_ideas",
            level=div_level_0,
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
    if exercise_type == rat.EXERCISE_TYPE:
        return rat.get_exercise(level, seed)["prompt"]
    if exercise_type == forced.EXERCISE_TYPE:
        return forced.get_exercise(level, seed)["prompt"]
    if exercise_type == constraints.EXERCISE_TYPE:
        return constraints.get_exercise(level, seed)["prompt"]
    if exercise_type == triz.EXERCISE_TYPE:
        return triz.get_exercise(level, seed)["prompt"]
    if exercise_type == pitch.EXERCISE_TYPE:
        return pitch.get_exercise(level, seed)["prompt"]
    if exercise_type == frames.EXERCISE_TYPE:
        return frames.get_exercise(level, seed)["prompt"]
    if exercise_type == quantity.EXERCISE_TYPE:
        return quantity.get_exercise(level, seed)["prompt"]
    return f"Exercise: {exercise_type} level {level}"
