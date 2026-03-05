"""All database operations."""
from datetime import date, datetime
from database.db import get_db
from config import LEVEL_UP_THRESHOLD, MAX_LEVEL, DIFFICULTY_EASY


# ─── Users ────────────────────────────────────────────────────────────────────

async def ensure_user(user_id: int, username: str | None = None) -> dict:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM users WHERE user_id = ?", (user_id,)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        await db.execute(
            "INSERT INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username),
        )
        await db.commit()
        return {"user_id": user_id, "onboarded": 0, "streak_days": 0, "last_session_date": None}
    return dict(row)


async def mark_onboarded(user_id: int) -> None:
    db = await get_db()
    await db.execute("UPDATE users SET onboarded = 1 WHERE user_id = ?", (user_id,))
    await db.commit()


async def get_user(user_id: int) -> dict | None:
    db = await get_db()
    async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def update_streak(user_id: int) -> int:
    """Update streak counter. Returns new streak value."""
    db = await get_db()
    today = date.today().isoformat()
    user = await get_user(user_id)
    if not user:
        return 0

    last = user.get("last_session_date")
    streak = user.get("streak_days", 0)

    if last == today:
        return streak  # already logged today

    from datetime import timedelta
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    new_streak = (streak + 1) if last == yesterday else 1

    await db.execute(
        "UPDATE users SET streak_days = ?, last_session_date = ? WHERE user_id = ?",
        (new_streak, today, user_id),
    )
    await db.commit()
    return new_streak


# ─── Sessions ─────────────────────────────────────────────────────────────────

async def create_session(user_id: int, mode: str, exercise_type: str, exercise_level: int) -> int:
    db = await get_db()
    today = date.today().isoformat()
    cur = await db.execute(
        "INSERT INTO sessions (user_id, date, mode, exercise_type, exercise_level) VALUES (?,?,?,?,?)",
        (user_id, today, mode, exercise_type, exercise_level),
    )
    await db.commit()
    return cur.lastrowid


async def complete_session(session_id: int) -> None:
    db = await get_db()
    now = datetime.now().isoformat()
    await db.execute(
        "UPDATE sessions SET completed_at = ? WHERE id = ?", (now, session_id)
    )
    await db.commit()


# ─── Responses ────────────────────────────────────────────────────────────────

async def save_response(
    session_id: int,
    user_response: str,
    llm_score: int,
    user_difficulty: str,
    response_time_sec: int,
) -> None:
    db = await get_db()
    await db.execute(
        """INSERT INTO responses
           (session_id, user_response, llm_score, user_difficulty, response_time_sec)
           VALUES (?,?,?,?,?)""",
        (session_id, user_response, llm_score, user_difficulty, response_time_sec),
    )
    await db.commit()


# ─── Progress ─────────────────────────────────────────────────────────────────

async def get_progress(user_id: int, exercise_type: str) -> dict:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM progress WHERE user_id = ? AND exercise_type = ?",
        (user_id, exercise_type),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        await db.execute(
            "INSERT OR IGNORE INTO progress (user_id, exercise_type) VALUES (?,?)",
            (user_id, exercise_type),
        )
        await db.commit()
        return {"user_id": user_id, "exercise_type": exercise_type, "current_level": 1,
                "sessions_count": 0, "avg_score": 0, "last_three_difficulties": ""}
    return dict(row)


async def update_progress(
    user_id: int,
    exercise_type: str,
    llm_score: int,
    user_difficulty: str,
) -> int:
    """Update progress and check for level-up. Returns current level."""
    prog = await get_progress(user_id, exercise_type)
    db = await get_db()

    sessions_count = prog["sessions_count"] + 1

    # Rolling average score
    old_avg = prog["avg_score"]
    old_count = prog["sessions_count"]
    new_avg = ((old_avg * old_count) + llm_score) / sessions_count

    # Track last 3 difficulties as CSV
    history = prog["last_three_difficulties"] or ""
    parts = [p for p in history.split(",") if p]
    parts.append(user_difficulty)
    parts = parts[-3:]  # keep only last 3
    new_history = ",".join(parts)

    # Level-up logic
    current_level = prog["current_level"]
    if (
        len(parts) >= LEVEL_UP_THRESHOLD
        and all(p == DIFFICULTY_EASY for p in parts)
        and current_level < MAX_LEVEL
    ):
        current_level += 1
        parts = []  # reset history after level up
        new_history = ""

    await db.execute(
        """UPDATE progress SET
            sessions_count = ?,
            avg_score = ?,
            current_level = ?,
            last_three_difficulties = ?
           WHERE user_id = ? AND exercise_type = ?""",
        (sessions_count, new_avg, current_level, new_history, user_id, exercise_type),
    )
    await db.commit()
    return current_level


async def get_all_progress(user_id: int) -> list[dict]:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM progress WHERE user_id = ?", (user_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ─── Incubation ───────────────────────────────────────────────────────────────

async def create_incubation(user_id: int, task_text: str) -> int:
    db = await get_db()
    now = datetime.now().isoformat()
    cur = await db.execute(
        "INSERT INTO incubation (user_id, task_text, created_at) VALUES (?,?,?)",
        (user_id, task_text, now),
    )
    await db.commit()
    return cur.lastrowid


async def get_active_incubation(user_id: int) -> dict | None:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM incubation WHERE user_id = ? AND answered_at IS NULL ORDER BY id DESC LIMIT 1",
        (user_id,),
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def answer_incubation(incubation_id: int, answer_text: str) -> None:
    db = await get_db()
    now = datetime.now().isoformat()
    await db.execute(
        "UPDATE incubation SET answered_at = ?, answer_text = ? WHERE id = ?",
        (now, answer_text, incubation_id),
    )
    await db.commit()


# ─── Stats ────────────────────────────────────────────────────────────────────

async def get_stats_summary(user_id: int) -> dict:
    db = await get_db()

    async with db.execute(
        "SELECT COUNT(*) as total FROM sessions WHERE user_id = ? AND completed_at IS NOT NULL",
        (user_id,),
    ) as cur:
        row = await cur.fetchone()
    total_sessions = row["total"] if row else 0

    progress_rows = await get_all_progress(user_id)

    user = await get_user(user_id)
    streak = user.get("streak_days", 0) if user else 0

    return {
        "total_sessions": total_sessions,
        "streak": streak,
        "progress": progress_rows,
    }


async def get_weekly_report_data(user_id: int, days: int = 7) -> dict:
    """Fetch all data for weekly report: sessions + responses + incubations."""
    db = await get_db()
    from datetime import timedelta
    since = (date.today() - timedelta(days=days)).isoformat()

    # Sessions with responses joined
    async with db.execute(
        """SELECT s.date, s.mode, s.exercise_type, s.exercise_level,
                  r.user_response, r.llm_score, r.user_difficulty, r.response_time_sec
           FROM sessions s
           LEFT JOIN responses r ON r.session_id = s.id
           WHERE s.user_id = ? AND s.date >= ?
           ORDER BY s.date, s.id""",
        (user_id, since),
    ) as cur:
        rows = await cur.fetchall()
    sessions = [dict(r) for r in rows]

    # Incubations this week
    async with db.execute(
        """SELECT task_text, created_at, answered_at, answer_text
           FROM incubation
           WHERE user_id = ? AND date(created_at) >= ?
           ORDER BY created_at""",
        (user_id, since),
    ) as cur:
        rows = await cur.fetchall()
    incubations = [dict(r) for r in rows]

    # Overall progress
    progress = await get_all_progress(user_id)
    user = await get_user(user_id)

    return {
        "sessions": sessions,
        "incubations": incubations,
        "progress": progress,
        "streak": user.get("streak_days", 0) if user else 0,
        "days": days,
    }
