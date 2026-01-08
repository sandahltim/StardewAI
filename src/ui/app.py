from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json
import os
import shutil
import subprocess

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.requests import Request
import sqlite3

try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMA = True
except ImportError:  # pragma: no cover - optional dependency
    HAS_CHROMA = False
    chromadb = None
    Settings = None

from . import storage

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
STATUS_PATH = Path("/home/tim/StardewAI/logs/ui/status.json")
GAME_KNOWLEDGE_DB = BASE_DIR.parents[1] / "data" / "game_knowledge.db"
CHROMA_DIR = BASE_DIR.parents[1] / "data" / "chromadb"
CHROMA_COLLECTION = "rusty_memories"
_chroma_collection = None
TTS_OUTPUT_DIR = Path("/home/tim/StardewAI/logs/ui/tts")
TTS_CACHE_DIR = TTS_OUTPUT_DIR / "cache"
TTS_MODEL_DIR = Path("/home/tim/StardewAI/models/tts")
DEFAULT_TTS_VOICE = "en_US-amy-medium"
PIPER_CMD = os.environ.get("PIPER_CMD", "piper")
APLAYER_CMD = os.environ.get("APLAYER_CMD", "aplay")

app = FastAPI(title="StardewAI UI")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class MessageCreate(BaseModel):
    role: str = Field(default="user")
    content: str
    reasoning: Optional[str] = None


class MessageUpdate(BaseModel):
    content: Optional[str] = None
    reasoning: Optional[str] = None


class GoalCreate(BaseModel):
    text: str


class TaskCreate(BaseModel):
    title: str
    details: Optional[Dict[str, Any]] = None
    status: str = "queued"
    priority: int = 0
    mode: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    mode: Optional[str] = None


class StatusUpdate(BaseModel):
    mode: Optional[str] = None
    running: Optional[bool] = None
    last_tick: Optional[str] = None
    last_error: Optional[str] = None
    desired_mode: Optional[str] = None
    confirm_before_execute: Optional[bool] = None
    confirm_granted: Optional[bool] = None
    pending_action: Optional[str] = None
    pending_action_id: Optional[str] = None
    pending_action_at: Optional[str] = None
    tts_enabled: Optional[bool] = None
    tts_voice: Optional[str] = None
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    weather: Optional[str] = None
    energy: Optional[str] = None
    holding: Optional[str] = None
    mood: Optional[str] = None
    menu_open: Optional[bool] = None
    nearby: Optional[List[str]] = None
    action_plan: Optional[List[str]] = None
    last_reasoning: Optional[str] = None
    last_actions: Optional[List[str]] = None
    vlm_status: Optional[str] = None
    player_tile_x: Optional[int] = None
    player_tile_y: Optional[int] = None


class MessageStream(BaseModel):
    message_id: Optional[int] = None
    role: str = "agent"
    content: Optional[str] = None
    reasoning: Optional[str] = None
    append: bool = True


class TtsRequest(BaseModel):
    message_id: Optional[int] = None
    text: Optional[str] = None
    voice: Optional[str] = None


class TeamMessageCreate(BaseModel):
    sender: str = Field(description="Sender identifier: 'claude', 'codex', or 'tim'")
    content: str = Field(description="Message content")


class SessionEventCreate(BaseModel):
    event_type: str = Field(description="Event type: position, action, tool_use")
    data: Dict[str, Any] = Field(default_factory=dict)


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, event_type: str, payload: Any) -> None:
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_json({"type": event_type, "payload": payload})
            except RuntimeError:
                dead.append(connection)
        for connection in dead:
            self.disconnect(connection)


manager = ConnectionManager()


def _default_status() -> Dict[str, Any]:
    return {
        "mode": "helper",
        "running": False,
        "last_tick": None,
        "last_error": None,
        "desired_mode": "helper",
        "confirm_before_execute": False,
        "confirm_granted": False,
        "pending_action": None,
        "pending_action_id": None,
        "pending_action_at": None,
        "tts_enabled": False,
        "tts_voice": DEFAULT_TTS_VOICE,
        "location": None,
        "time_of_day": None,
        "weather": None,
        "energy": None,
        "holding": None,
        "mood": None,
        "menu_open": None,
        "nearby": [],
        "action_plan": [],
        "last_reasoning": None,
        "last_actions": [],
        "vlm_status": "Idle",
        "player_tile_x": None,
        "player_tile_y": None,
    }


def _read_status() -> Dict[str, Any]:
    defaults = _default_status()
    if not STATUS_PATH.exists():
        return defaults
    try:
        data = json.loads(STATUS_PATH.read_text())
    except json.JSONDecodeError:
        defaults["last_error"] = "Invalid status JSON"
        return defaults
    defaults.update(data)
    return defaults


def _write_status(update: Dict[str, Any], allow_none_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    status = _read_status()
    allow_none = set(allow_none_keys or [])
    for key, value in update.items():
        if value is None and key not in allow_none:
            continue
        status[key] = value
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, indent=2))
    return status


def _resolve_tts_model(voice: str) -> Dict[str, Optional[Path]]:
    model_path = TTS_MODEL_DIR / f"{voice}.onnx"
    config_path = TTS_MODEL_DIR / f"{voice}.onnx.json"
    return {
        "model": model_path if model_path.exists() else None,
        "config": config_path if config_path.exists() else None,
    }


def _query_game_knowledge(entity_type: str, name: str) -> Optional[Dict[str, Any]]:
    if not GAME_KNOWLEDGE_DB.exists():
        return None
    conn = sqlite3.connect(GAME_KNOWLEDGE_DB)
    conn.row_factory = sqlite3.Row
    try:
        row = None
        if entity_type == "npc":
            row = conn.execute(
                "SELECT * FROM npcs WHERE lower(name) = lower(?)",
                (name,),
            ).fetchone()
        elif entity_type == "crop":
            row = conn.execute(
                "SELECT * FROM crops WHERE lower(name) = lower(?)",
                (name,),
            ).fetchone()
        elif entity_type == "item":
            row = conn.execute(
                "SELECT * FROM items WHERE lower(name) = lower(?)",
                (name,),
            ).fetchone()
        elif entity_type == "location":
            row = conn.execute(
                "SELECT * FROM locations WHERE lower(name) = lower(?)",
                (name,),
            ).fetchone()
        elif entity_type == "recipe":
            row = conn.execute(
                "SELECT * FROM recipes WHERE lower(name) = lower(?)",
                (name,),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        for key in [
            "loved_gifts",
            "liked_gifts",
            "neutral_gifts",
            "disliked_gifts",
            "hated_gifts",
            "locations",
            "notable_features",
            "ingredients",
        ]:
            if key in data and data[key]:
                data[key] = json.loads(data[key])
        return data
    finally:
        conn.close()


def _get_chroma_collection():
    global _chroma_collection
    if not HAS_CHROMA:
        return None
    if _chroma_collection is None:
        client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False)
        )
        _chroma_collection = client.get_or_create_collection(
            name=CHROMA_COLLECTION,
            metadata={"description": "Rusty's episodic memories from Stardew Valley"}
        )
    return _chroma_collection


def _get_recent_memories(limit: int = 10) -> List[Dict[str, Any]]:
    collection = _get_chroma_collection()
    if not collection:
        return []
    results = collection.get(include=["documents", "metadatas"])
    if not results.get("ids"):
        return []
    memories = []
    for i, mem_id in enumerate(results["ids"]):
        memories.append({
            "id": mem_id,
            "text": results["documents"][i],
            "metadata": results["metadatas"][i] if results["metadatas"] else {},
        })
    memories.sort(key=lambda m: m["metadata"].get("timestamp", ""), reverse=True)
    return memories[:limit]


def _search_memories(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    collection = _get_chroma_collection()
    if not collection or not query:
        return []
    results = collection.query(query_texts=[query], n_results=limit)
    memories = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0] if results.get("distances") else []
    for idx, doc in enumerate(docs):
        memories.append({
            "id": ids[idx] if idx < len(ids) else None,
            "text": doc,
            "metadata": metas[idx] if idx < len(metas) else {},
            "distance": distances[idx] if idx < len(distances) else None,
        })
    return memories


def _speak_text(text: str, voice: str) -> Dict[str, Any]:
    if not shutil.which(PIPER_CMD):
        return {"ok": False, "error": f"Piper not found at '{PIPER_CMD}'"}

    if not shutil.which(APLAYER_CMD):
        return {"ok": False, "error": f"Audio player not found at '{APLAYER_CMD}'"}

    model_info = _resolve_tts_model(voice)
    if not model_info["model"]:
        return {"ok": False, "error": f"TTS model not found for voice '{voice}'"}

    TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(f"{voice}:{text}".encode("utf-8")).hexdigest()[:16]
    cache_path = TTS_CACHE_DIR / f"{voice}-{cache_key}.wav"
    output_path = TTS_OUTPUT_DIR / "latest.wav"

    if cache_path.exists():
        try:
            subprocess.run([APLAYER_CMD, str(cache_path)], check=True)
            return {"ok": True, "output": str(cache_path), "voice": voice, "cached": True}
        except subprocess.CalledProcessError as exc:
            return {"ok": False, "error": f"TTS playback failed: {exc}"}

    try:
        command = [
            PIPER_CMD,
            "--model",
            str(model_info["model"]),
            "--output_file",
            str(cache_path),
        ]
        if model_info["config"]:
            command.extend(["--config", str(model_info["config"])])
        subprocess.run(command, input=text.encode("utf-8"), check=True)
        subprocess.run([APLAYER_CMD, str(cache_path)], check=True)
        try:
            shutil.copyfile(cache_path, output_path)
        except OSError:
            pass
        return {"ok": True, "output": str(cache_path), "voice": voice, "cached": False}
    except subprocess.CalledProcessError as exc:
        return {"ok": False, "error": f"TTS command failed: {exc}"}


@app.on_event("startup")
def on_startup() -> None:
    storage.init_db()
    _write_status({})


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    messages = storage.list_messages(limit=200)
    messages = messages[-10:]
    active_goal = storage.get_active_goal()
    tasks = storage.list_tasks()
    status = _read_status()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "messages": messages,
            "active_goal": active_goal,
            "tasks": tasks,
            "status": status,
        },
    )


@app.get("/api/status")
def get_status() -> Dict[str, Any]:
    return _read_status()


@app.post("/api/status")
async def update_status(payload: StatusUpdate) -> Dict[str, Any]:
    status = _write_status(payload.dict(exclude_unset=True), allow_none_keys=[
        "pending_action",
        "pending_action_id",
        "pending_action_at",
    ])
    await manager.broadcast("status_updated", status)
    return status


@app.post("/api/confirm")
async def confirm_next_action() -> Dict[str, Any]:
    status = _write_status({"confirm_granted": True})
    await manager.broadcast("status_updated", status)
    return status


@app.post("/api/action/pending")
async def set_pending_action(payload: StatusUpdate) -> Dict[str, Any]:
    update = payload.dict(exclude_unset=True)
    status = _write_status(update, allow_none_keys=[
        "pending_action",
        "pending_action_id",
        "pending_action_at",
    ])
    await manager.broadcast("status_updated", status)
    return status


@app.post("/api/action/clear")
async def clear_pending_action() -> Dict[str, Any]:
    status = _write_status(
        {
            "pending_action": None,
            "pending_action_id": None,
            "pending_action_at": None,
            "confirm_granted": False,
        },
        allow_none_keys=["pending_action", "pending_action_id", "pending_action_at"],
    )
    await manager.broadcast("status_updated", status)
    return status


@app.get("/api/messages")
def get_messages(limit: int = 200, since_id: Optional[int] = None) -> List[Dict[str, Any]]:
    return storage.list_messages(limit=limit, since_id=since_id)


@app.get("/api/game-knowledge")
def get_game_knowledge(entity_type: str = Query(..., alias="type"), name: str = "") -> Dict[str, Any]:
    data = _query_game_knowledge(entity_type, name)
    if not data:
        raise HTTPException(status_code=404, detail="Game knowledge not found")
    storage.add_session_event("knowledge_lookup", {"type": entity_type, "name": name})
    return data


@app.get("/api/episodic-memories")
def get_episodic_memories(limit: int = 10, query: Optional[str] = None) -> List[Dict[str, Any]]:
    if query:
        return _search_memories(query, limit=limit)
    return _get_recent_memories(limit=limit)


@app.post("/api/messages")
async def create_message(payload: MessageCreate) -> Dict[str, Any]:
    message = storage.add_message(payload.role, payload.content, payload.reasoning)
    await manager.broadcast("message_created", message)
    return message


@app.patch("/api/messages/{message_id}")
async def update_message(message_id: int, payload: MessageUpdate) -> Dict[str, Any]:
    updated = storage.update_message(
        message_id,
        content=payload.content,
        reasoning=payload.reasoning,
        append=False,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Message not found")
    await manager.broadcast("message_updated", updated)
    return updated


@app.post("/api/messages/stream")
async def stream_message(payload: MessageStream) -> Dict[str, Any]:
    if payload.message_id is None:
        message = storage.add_message(payload.role, payload.content or "", payload.reasoning)
        await manager.broadcast("message_created", message)
        return message

    updated = storage.update_message(
        payload.message_id,
        content=payload.content,
        reasoning=payload.reasoning,
        append=payload.append,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Message not found")
    await manager.broadcast("message_updated", updated)
    return updated


@app.post("/api/tts")
async def speak_message(payload: TtsRequest) -> Dict[str, Any]:
    voice = payload.voice or _read_status().get("tts_voice") or DEFAULT_TTS_VOICE

    text = payload.text
    if payload.message_id is not None:
        message = storage.get_message(payload.message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        text = message["content"]

    if not text:
        raise HTTPException(status_code=400, detail="No text provided for TTS")

    return _speak_text(text, voice)


@app.get("/api/goals")
def get_goals() -> Dict[str, Any]:
    return {"active": storage.get_active_goal(), "history": storage.list_goals()}


@app.post("/api/goals")
async def create_goal(payload: GoalCreate) -> Dict[str, Any]:
    goal = storage.set_goal(payload.text)
    await manager.broadcast("goal_updated", goal)
    return goal


@app.get("/api/tasks")
def get_tasks() -> List[Dict[str, Any]]:
    return storage.list_tasks()


@app.post("/api/tasks")
async def create_task(payload: TaskCreate) -> Dict[str, Any]:
    task = storage.add_task(
        title=payload.title,
        details=payload.details,
        status=payload.status,
        priority=payload.priority,
        mode=payload.mode,
    )
    await manager.broadcast("task_created", task)
    return task


@app.patch("/api/tasks/{task_id}")
async def patch_task(task_id: int, payload: TaskUpdate) -> Dict[str, Any]:
    updated = storage.update_task(task_id, payload.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    await manager.broadcast("task_updated", updated)
    return updated


# --- Team Chat ---

@app.get("/api/team")
def get_team_messages(limit: int = 100, since_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get team chat messages. Use since_id for polling new messages."""
    return storage.list_team_messages(limit=limit, since_id=since_id)


@app.post("/api/team")
async def create_team_message(payload: TeamMessageCreate) -> Dict[str, Any]:
    """Post a team chat message. Broadcasts via WebSocket."""
    message = storage.add_team_message(payload.sender, payload.content)
    await manager.broadcast("team_message_created", message)
    return message


# --- Session Memory ---

@app.get("/api/session-memory")
def get_session_memory(
    limit: int = 100,
    event_type: Optional[str] = None,
    since_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    return storage.list_session_events(limit=limit, event_type=event_type, since_id=since_id)


@app.post("/api/session-memory")
async def create_session_event(payload: SessionEventCreate) -> Dict[str, Any]:
    event = storage.add_session_event(payload.event_type, payload.data)
    await manager.broadcast("session_event_created", event)
    return event


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
