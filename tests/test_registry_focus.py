import os
import sys
import types
import unittest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")

dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv_stub)

from exercises import aut
from exercises.registry import select_round_two, select_session_exercises


class RegistryFocusTests(unittest.TestCase):
    def test_select_session_exercises_keeps_preferred_type_for_quick(self) -> None:
        exercises = select_session_exercises(
            mode="quick",
            progress={"aut": {"current_level": 2, "sessions_count": 5}},
            count=1,
            seed=123,
            preferred_type="aut",
        )

        self.assertEqual(1, len(exercises))
        self.assertEqual("aut", exercises[0].exercise_type)
        self.assertEqual(2, exercises[0].level)

    def test_select_session_exercises_keeps_preferred_type_for_deep(self) -> None:
        exercises = select_session_exercises(
            mode="deep",
            progress={"aut": {"current_level": 3, "sessions_count": 2}},
            count=3,
            seed=123,
            preferred_type="aut",
        )

        self.assertEqual(3, len(exercises))
        self.assertTrue(all(ex.exercise_type == aut.EXERCISE_TYPE for ex in exercises))
        self.assertTrue(all(ex.level == 3 for ex in exercises))

    def test_round_two_caps_level(self) -> None:
        exercise = select_round_two("aut", current_level=4, seed=10)

        self.assertEqual(4, exercise.level)


if __name__ == "__main__":
    unittest.main()
