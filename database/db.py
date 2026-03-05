import aiosqlite
from config import DB_PATH

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _init_schema(_db)
    return _db


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


async def _init_schema(db: aiosqlite.Connection) -> None:
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            onboarded   INTEGER DEFAULT 0,
            streak_days INTEGER DEFAULT 0,
            last_session_date TEXT
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER,
            date            TEXT,
            mode            TEXT,
            exercise_type   TEXT,
            exercise_level  INTEGER,
            completed_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS responses (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id          INTEGER,
            user_response       TEXT,
            llm_score           INTEGER,
            user_difficulty     TEXT,
            response_time_sec   INTEGER
        );

        CREATE TABLE IF NOT EXISTS progress (
            user_id         INTEGER,
            exercise_type   TEXT,
            current_level   INTEGER DEFAULT 1,
            sessions_count  INTEGER DEFAULT 0,
            avg_score       REAL    DEFAULT 0,
            last_three_difficulties TEXT DEFAULT '',
            PRIMARY KEY (user_id, exercise_type)
        );

        CREATE TABLE IF NOT EXISTS incubation (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            task_text   TEXT,
            created_at  TEXT,
            answered_at TEXT,
            answer_text TEXT
        );
    """)
    await db.commit()
