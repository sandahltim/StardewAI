import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = Path("/home/tim/StardewAI/logs/ui/agent_ui.db")


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    _ensure_dir(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                reasoning TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                details_json TEXT,
                status TEXT NOT NULL DEFAULT 'queued',
                priority INTEGER NOT NULL DEFAULT 0,
                mode TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS team_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                data_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def add_message(
    role: str,
    content: str,
    reasoning: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    created_at = datetime.utcnow().isoformat()
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO messages (role, content, reasoning, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (role, content, reasoning, created_at),
        )
        message_id = cur.lastrowid
    return {
        "id": message_id,
        "role": role,
        "content": content,
        "reasoning": reasoning,
        "created_at": created_at,
    }


def list_messages(
    limit: int = 200,
    since_id: Optional[int] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    with _connect(db_path) as conn:
        if since_id:
            rows = conn.execute(
                """
                SELECT id, role, content, reasoning, created_at
                FROM messages
                WHERE id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (since_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, role, content, reasoning, created_at
                FROM messages
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]


def get_message(message_id: int, db_path: Path = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, role, content, reasoning, created_at
            FROM messages
            WHERE id = ?
            """,
            (message_id,),
        ).fetchone()
    return dict(row) if row else None


def update_message(
    message_id: int,
    content: Optional[str] = None,
    reasoning: Optional[str] = None,
    append: bool = False,
    db_path: Path = DEFAULT_DB_PATH,
) -> Optional[Dict[str, Any]]:
    message = get_message(message_id, db_path)
    if not message:
        return None

    new_content = message["content"]
    new_reasoning = message["reasoning"]

    if content is not None:
        new_content = f"{new_content}{content}" if append else content

    if reasoning is not None:
        new_reasoning = f"{new_reasoning or ''}{reasoning}" if append else reasoning

    with _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE messages
            SET content = ?, reasoning = ?
            WHERE id = ?
            """,
            (new_content, new_reasoning, message_id),
        )

    return {
        "id": message_id,
        "role": message["role"],
        "content": new_content,
        "reasoning": new_reasoning,
        "created_at": message["created_at"],
    }


def set_goal(text: str, db_path: Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    created_at = datetime.utcnow().isoformat()
    with _connect(db_path) as conn:
        conn.execute("UPDATE goals SET active = 0")
        cur = conn.execute(
            """
            INSERT INTO goals (text, active, created_at)
            VALUES (?, 1, ?)
            """,
            (text, created_at),
        )
        goal_id = cur.lastrowid
    return {"id": goal_id, "text": text, "active": 1, "created_at": created_at}


def get_active_goal(db_path: Path = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, text, active, created_at
            FROM goals
            WHERE active = 1
            ORDER BY id DESC
            LIMIT 1
            """,
        ).fetchone()
    return dict(row) if row else None


def list_goals(limit: int = 50, db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, text, active, created_at
            FROM goals
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def add_task(
    title: str,
    details: Optional[Dict[str, Any]] = None,
    status: str = "queued",
    priority: int = 0,
    mode: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    created_at = datetime.utcnow().isoformat()
    details_json = json.dumps(details or {})
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO tasks (title, details_json, status, priority, mode, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, details_json, status, priority, mode, created_at),
        )
        task_id = cur.lastrowid
    return {
        "id": task_id,
        "title": title,
        "details": details or {},
        "status": status,
        "priority": priority,
        "mode": mode,
        "created_at": created_at,
    }


def list_tasks(db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, title, details_json, status, priority, mode, created_at
            FROM tasks
            ORDER BY priority DESC, id ASC
            """,
        ).fetchall()
    tasks: List[Dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        data["details"] = json.loads(data.pop("details_json") or "{}")
        tasks.append(data)
    return tasks


def update_task(
    task_id: int,
    fields: Dict[str, Any],
    db_path: Path = DEFAULT_DB_PATH,
) -> Optional[Dict[str, Any]]:
    updates = []
    values: List[Any] = []

    if "title" in fields:
        updates.append("title = ?")
        values.append(fields["title"])

    if "status" in fields:
        updates.append("status = ?")
        values.append(fields["status"])

    if "priority" in fields:
        updates.append("priority = ?")
        values.append(fields["priority"])

    if "mode" in fields:
        updates.append("mode = ?")
        values.append(fields["mode"])

    if "details" in fields:
        updates.append("details_json = ?")
        values.append(json.dumps(fields["details"] or {}))

    if not updates:
        return None

    values.append(task_id)
    with _connect(db_path) as conn:
        conn.execute(
            f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
            values,
        )
        row = conn.execute(
            """
            SELECT id, title, details_json, status, priority, mode, created_at
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

    if not row:
        return None

    data = dict(row)
    data["details"] = json.loads(data.pop("details_json") or "{}")
    return data


# --- Team Chat ---

def add_team_message(
    sender: str,
    content: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    """Add a team chat message. Sender should be 'claude', 'codex', or 'tim'."""
    created_at = datetime.utcnow().isoformat()
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO team_messages (sender, content, created_at)
            VALUES (?, ?, ?)
            """,
            (sender, content, created_at),
        )
        message_id = cur.lastrowid
    return {
        "id": message_id,
        "sender": sender,
        "content": content,
        "created_at": created_at,
    }


def list_team_messages(
    limit: int = 100,
    since_id: Optional[int] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """List team messages, optionally filtered to messages after since_id."""
    with _connect(db_path) as conn:
        if since_id:
            rows = conn.execute(
                """
                SELECT id, sender, content, created_at
                FROM team_messages
                WHERE id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (since_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, sender, content, created_at
                FROM team_messages
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            rows = list(reversed(rows))  # Return in chronological order
    return [dict(row) for row in rows]


# --- Session Memory ---

def add_session_event(
    event_type: str,
    data: Dict[str, Any],
    db_path: Path = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    created_at = datetime.utcnow().isoformat()
    data_json = json.dumps(data or {})
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO session_events (event_type, data_json, created_at)
            VALUES (?, ?, ?)
            """,
            (event_type, data_json, created_at),
        )
        event_id = cur.lastrowid
    return {
        "id": event_id,
        "event_type": event_type,
        "data": data or {},
        "created_at": created_at,
    }


def list_session_events(
    limit: int = 100,
    event_type: Optional[str] = None,
    since_id: Optional[int] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    with _connect(db_path) as conn:
        if since_id:
            if event_type:
                rows = conn.execute(
                    """
                    SELECT id, event_type, data_json, created_at
                    FROM session_events
                    WHERE id > ? AND event_type = ?
                    ORDER BY id ASC
                    LIMIT ?
                    """,
                    (since_id, event_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, event_type, data_json, created_at
                    FROM session_events
                    WHERE id > ?
                    ORDER BY id ASC
                    LIMIT ?
                    """,
                    (since_id, limit),
                ).fetchall()
        else:
            if event_type:
                rows = conn.execute(
                    """
                    SELECT id, event_type, data_json, created_at
                    FROM session_events
                    WHERE event_type = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (event_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, event_type, data_json, created_at
                    FROM session_events
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            rows = list(reversed(rows))
    events: List[Dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        data["data"] = json.loads(data.pop("data_json") or "{}")
        events.append(data)
    return events
