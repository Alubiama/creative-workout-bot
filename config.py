import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env относительно этого файла — работает из любой папки
_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)

TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
OPENROUTER_API_KEY: str = os.environ["OPENROUTER_API_KEY"]
DB_PATH: str = str(Path(__file__).parent / os.getenv("DB_PATH", "creative_bot.db"))

# Модель через OpenRouter. Варианты:
# "anthropic/claude-3.5-sonnet"  — Claude (платно, но дёшево)
# "google/gemini-flash-1.5"      — Gemini (дешевле)
# "meta-llama/llama-3.1-8b-instruct:free" — бесплатно (лимиты)
CLAUDE_MODEL = "google/gemini-2.0-flash-001"

# Режимы сессии
MODE_DEEP = "deep"
MODE_QUICK = "quick"

# Уровни сложности (пользовательская оценка)
DIFFICULTY_EASY = "easy"
DIFFICULTY_OK = "ok"
DIFFICULTY_HARD = "hard"

# Порог повышения уровня: 3 сессии подряд "easy"
LEVEL_UP_THRESHOLD = 3

# Максимальный уровень упражнений
MAX_LEVEL = 4
