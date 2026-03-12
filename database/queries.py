"""All database operations."""
from datetime import date, datetime, timedelta

from config import DIFFICULTY_EASY, LEVEL_UP_THRESHOLD, MAX_LEVEL
from database.db import get_db


async def ensure_user(user_id: int, username: str | None = None) -> dict:
    db = await get_db()
    async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
        row = await cur.fetchone()
    if row is None:
        await db.execute(
            "INSERT INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username),
        )
        await db.execute(
            "INSERT OR IGNORE INTO user_settings (user_id, focus_exercise_type) VALUES (?, NULL)",
            (user_id,),
        )
        await db.commit()
        return {
            "user_id": user_id,
            "onboarded": 0,
            "streak_days": 0,
            "last_session_date": None,
        }

    await db.execute(
        "INSERT OR IGNORE INTO user_settings (user_id, focus_exercise_type) VALUES (?, NULL)",
        (user_id,),
    )
    await db.commit()
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
    db = await get_db()
    today = date.today().isoformat()
    user = await get_user(user_id)
    if not user:
        return 0

    last = user.get("last_session_date")
    streak = user.get("streak_days", 0)
    if last == today:
        return streak

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    new_streak = (streak + 1) if last == yesterday else 1
    await db.execute(
        "UPDATE users SET streak_days = ?, last_session_date = ? WHERE user_id = ?",
        (new_streak, today, user_id),
    )
    await db.commit()
    return new_streak


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
    await db.execute("UPDATE sessions SET completed_at = ? WHERE id = ?", (now, session_id))
    await db.commit()


async def save_response(
    session_id: int,
    user_response: str,
    llm_score: int,
    user_difficulty: str,
    response_time_sec: int,
    llm_feedback: str | None = None,
    initial_llm_score: int | None = None,
    appeal_text: str | None = None,
    appeal_feedback: str | None = None,
    appeal_decision: str | None = None,
) -> None:
    db = await get_db()
    await db.execute(
        """
        INSERT INTO responses (
            session_id,
            user_response,
            llm_score,
            llm_feedback,
            user_difficulty,
            response_time_sec,
            initial_llm_score,
            appeal_text,
            appeal_feedback,
            appeal_decision
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            session_id,
            user_response,
            llm_score,
            llm_feedback,
            user_difficulty,
            response_time_sec,
            initial_llm_score,
            appeal_text,
            appeal_feedback,
            appeal_decision,
        ),
    )
    await db.commit()


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
        return {
            "user_id": user_id,
            "exercise_type": exercise_type,
            "current_level": 1,
            "sessions_count": 0,
            "avg_score": 0,
            "last_three_difficulties": "",
        }
    return dict(row)


async def update_progress(user_id: int, exercise_type: str, llm_score: int, user_difficulty: str) -> int:
    prog = await get_progress(user_id, exercise_type)
    db = await get_db()

    sessions_count = prog["sessions_count"] + 1
    old_avg = prog["avg_score"]
    old_count = prog["sessions_count"]
    new_avg = ((old_avg * old_count) + llm_score) / sessions_count

    history = prog["last_three_difficulties"] or ""
    parts = [part for part in history.split(",") if part]
    parts.append(user_difficulty)
    parts = parts[-3:]
    new_history = ",".join(parts)

    current_level = prog["current_level"]
    if (
        len(parts) >= LEVEL_UP_THRESHOLD
        and all(part == DIFFICULTY_EASY for part in parts)
        and current_level < MAX_LEVEL
    ):
        current_level += 1
        new_history = ""

    await db.execute(
        """
        UPDATE progress SET
            sessions_count = ?,
            avg_score = ?,
            current_level = ?,
            last_three_difficulties = ?
        WHERE user_id = ? AND exercise_type = ?
        """,
        (sessions_count, new_avg, current_level, new_history, user_id, exercise_type),
    )
    await db.commit()
    return current_level


async def get_all_progress(user_id: int) -> list[dict]:
    db = await get_db()
    async with db.execute("SELECT * FROM progress WHERE user_id = ?", (user_id,)) as cur:
        rows = await cur.fetchall()
    return [dict(row) for row in rows]


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


async def get_focus_exercise_type(user_id: int) -> str | None:
    db = await get_db()
    async with db.execute(
        "SELECT focus_exercise_type FROM user_settings WHERE user_id = ?",
        (user_id,),
    ) as cur:
        row = await cur.fetchone()
    return row[0] if row and row[0] else None


async def set_focus_exercise_type(user_id: int, exercise_type: str) -> None:
    db = await get_db()
    await db.execute(
        "INSERT INTO user_settings (user_id, focus_exercise_type) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET focus_exercise_type = excluded.focus_exercise_type",
        (user_id, exercise_type),
    )
    await db.commit()


async def clear_focus_exercise_type(user_id: int) -> None:
    db = await get_db()
    await db.execute(
        "INSERT INTO user_settings (user_id, focus_exercise_type) VALUES (?, NULL) "
        "ON CONFLICT(user_id) DO UPDATE SET focus_exercise_type = NULL",
        (user_id,),
    )
    await db.commit()


async def reset_user_progress(user_id: int) -> None:
    db = await get_db()

    async with db.execute("SELECT id FROM sessions WHERE user_id = ?", (user_id,)) as cur:
        session_rows = await cur.fetchall()
    session_ids = [row[0] for row in session_rows]

    if session_ids:
        placeholders = ",".join("?" for _ in session_ids)
        await db.execute(
            f"DELETE FROM responses WHERE session_id IN ({placeholders})",
            session_ids,
        )

    await db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    await db.execute("DELETE FROM progress WHERE user_id = ?", (user_id,))
    await db.execute("DELETE FROM incubation WHERE user_id = ?", (user_id,))
    await db.execute(
        "UPDATE users SET onboarded = 0, streak_days = 0, last_session_date = NULL WHERE user_id = ?",
        (user_id,),
    )
    await db.execute(
        "INSERT INTO user_settings (user_id, focus_exercise_type) VALUES (?, NULL) "
        "ON CONFLICT(user_id) DO UPDATE SET focus_exercise_type = NULL",
        (user_id,),
    )
    await db.commit()


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
    focus = await get_focus_exercise_type(user_id)

    return {
        "total_sessions": total_sessions,
        "streak": streak,
        "progress": progress_rows,
        "focus_exercise_type": focus,
    }


async def get_weekly_report_data(user_id: int, days: int = 7) -> dict:
    db = await get_db()
    since = (date.today() - timedelta(days=days)).isoformat()

    async with db.execute(
        """
        SELECT s.date, s.mode, s.exercise_type, s.exercise_level,
               r.user_response, r.llm_score, r.llm_feedback, r.user_difficulty, r.response_time_sec,
               r.initial_llm_score, r.appeal_text, r.appeal_feedback, r.appeal_decision
        FROM sessions s
        LEFT JOIN responses r ON r.session_id = s.id
        WHERE s.user_id = ? AND s.date >= ?
        ORDER BY s.date, s.id
        """,
        (user_id, since),
    ) as cur:
        rows = await cur.fetchall()
    sessions = [dict(row) for row in rows]

    async with db.execute(
        """
        SELECT task_text, created_at, answered_at, answer_text
        FROM incubation
        WHERE user_id = ? AND date(created_at) >= ?
        ORDER BY created_at
        """,
        (user_id, since),
    ) as cur:
        rows = await cur.fetchall()
    incubations = [dict(row) for row in rows]

    progress = await get_all_progress(user_id)
    user = await get_user(user_id)
    focus = await get_focus_exercise_type(user_id)
    return {
        "sessions": sessions,
        "incubations": incubations,
        "progress": progress,
        "streak": user.get("streak_days", 0) if user else 0,
        "days": days,
        "focus_exercise_type": focus,
    }
