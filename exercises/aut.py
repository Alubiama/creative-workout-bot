"""Alternative Uses Task — беглость и оригинальность."""
from dataclasses import dataclass, field

EXERCISE_TYPE = "aut"

# Предметы по уровням
_OBJECTS_BY_LEVEL: dict[int, list[str]] = {
    1: ["кирпич", "ложка", "газета", "ведро", "верёвка", "пластиковая бутылка"],
    2: ["тень", "пробел", "тишина", "граница", "задержка", "ожидание"],
    3: ["стоп-кадр", "маска", "шрифт", "сетка", "прокси-сервер", "рендер"],
    4: ["шрифт + тишина", "граница + задержка", "маска + пробел"],
}

_IDEAS_COUNT = {1: 5, 2: 7, 3: 10, 4: 10}
_TIME_LIMITS = {1: None, 2: "3 минуты", 3: "2 минуты", 4: "2 минуты"}


@dataclass
class AUTExercise:
    type: str = EXERCISE_TYPE
    level: int = 1
    obj: str = ""
    ideas_count: int = 5
    time_limit: str | None = None
    is_pair: bool = False

    def to_prompt(self) -> str:
        lines = [f"*Альтернативное применение — уровень {self.level}*\n"]
        if self.is_pair:
            parts = self.obj.split(" + ")
            lines.append(
                f"Два предмета: *{parts[0]}* и *{parts[1]}*\n"
                f"Найди {self.ideas_count} применений на их _пересечении_ — "
                "что получается если их совместить."
            )
        else:
            lines.append(
                f"Придумай *{self.ideas_count} нестандартных применений* предмета: *{self.obj}*"
            )
        if self.time_limit:
            lines.append(f"\n_Лимит: {self.time_limit}_")
        lines.append("\nПиши списком.")
        return "\n".join(lines)


def get_exercise(level: int, seed: int = 0) -> AUTExercise:
    import random
    rng = random.Random(seed)
    objects = _OBJECTS_BY_LEVEL.get(level, _OBJECTS_BY_LEVEL[1])
    obj = rng.choice(objects)
    is_pair = " + " in obj
    return AUTExercise(
        level=level,
        obj=obj,
        ideas_count=_IDEAS_COUNT.get(level, 5),
        time_limit=_TIME_LIMITS.get(level),
        is_pair=is_pair,
    )
