from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import asyncio
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

try:
    from . import storage
except ImportError:
    import storage

AGENT_DIR = (Path(__file__).resolve().parent.parent / "python-agent").resolve()
if AGENT_DIR.exists() and str(AGENT_DIR) not in sys.path:
    sys.path.append(str(AGENT_DIR))

try:
    from memory.spatial_map import SpatialMap
except Exception:  # pragma: no cover - optional for UI
    SpatialMap = None

try:
    from commentary.rusty_character import TTS_VOICES, get_voice_list
    # Legacy compat - map to new structure
    COMMENTARY_PERSONALITIES = {k: v["name"] for k, v in TTS_VOICES.items()}
    COMMENTARY_VOICES = {k: v["id"] for k, v in TTS_VOICES.items()}
except Exception:  # pragma: no cover - optional for UI
    COMMENTARY_PERSONALITIES = None
    COMMENTARY_VOICES = None
    TTS_VOICES = None
    get_voice_list = None

try:
    from memory.rusty_memory import get_rusty_memory
except Exception:  # pragma: no cover - optional for UI
    get_rusty_memory = None

try:
    from memory.daily_planner import get_daily_planner
except Exception:  # pragma: no cover - optional for UI
    get_daily_planner = None

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
STATUS_PATH = Path("/home/tim/StardewAI/logs/ui/status.json")
FARM_PLAN_PATH = Path("/home/tim/StardewAI/logs/farm_plans/current.json")
LESSONS_PATH = Path("/home/tim/StardewAI/logs/lessons.json")
RUSTY_STATE_PATH = Path("/home/tim/StardewAI/logs/rusty_state.json")
DAILY_SUMMARY_PATH = Path("/home/tim/StardewAI/logs/daily_summary.json")
GAME_KNOWLEDGE_DB = BASE_DIR.parents[1] / "data" / "game_knowledge.db"
CHROMA_DIR = BASE_DIR.parents[1] / "data" / "chromadb"
CHROMA_COLLECTION = "rusty_memories"
_chroma_collection = None
TTS_OUTPUT_DIR = Path("/home/tim/StardewAI/logs/ui/tts")
TTS_CACHE_DIR = TTS_OUTPUT_DIR / "cache"
TTS_MODEL_DIRS = [
    Path("/Gary/models/piper"),  # Shared voice collection
    Path("/home/tim/StardewAI/models/tts"),
    Path.home() / ".local/share/piper-voices",
    Path("/usr/share/piper-voices"),
]
DEFAULT_TTS_VOICE = "en_US-lessac-medium"
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


class ShippingItemCreate(BaseModel):
    item_name: str
    quantity: int = 1
    value: int = 0
    shipped_at: Optional[str] = None
    game_day: Optional[int] = None


class SkillHistoryCreate(BaseModel):
    skill_name: str
    success: bool = True
    failure_reason: Optional[str] = None
    created_at: Optional[str] = None


class CommentaryUpdate(BaseModel):
    text: Optional[str] = None
    personality: Optional[str] = None
    voice: Optional[str] = None
    tts_enabled: Optional[bool] = None
    volume: Optional[int] = None


class CommentaryPersonalityUpdate(BaseModel):
    personality: str


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
    vlm_parse_success: Optional[int] = None
    vlm_parse_fail: Optional[int] = None
    vlm_errors: Optional[List[Dict[str, Any]]] = None
    available_skills_count: Optional[int] = None
    session_started_at: Optional[str] = None
    think_count: Optional[int] = None
    action_count: Optional[int] = None
    action_fail_count: Optional[int] = None
    action_type_counts: Optional[Dict[str, int]] = None
    distance_traveled: Optional[int] = None
    crops_watered_count: Optional[int] = None
    crops_harvested_count: Optional[int] = None
    latency_history: Optional[List[float]] = None
    player_tile_x: Optional[int] = None
    player_tile_y: Optional[int] = None
    current_instruction: Optional[str] = None
    navigation_target: Optional[str] = None
    navigation_blocked: Optional[str] = None
    navigation_attempts: Optional[int] = None
    commentary_text: Optional[str] = None
    commentary_personality: Optional[str] = None
    commentary_voice: Optional[str] = None
    commentary_tts_enabled: Optional[bool] = None
    commentary_volume: Optional[int] = None


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


class SpatialTile(BaseModel):
    x: int
    y: int
    state: Optional[str] = None
    crop: Optional[str] = None
    watered: Optional[bool] = None
    obstacle: Optional[str] = None
    worked_at: Optional[str] = None


class SpatialMapUpdate(BaseModel):
    location: str = Field(default="Farm")
    tiles: List[SpatialTile] = Field(default_factory=list)
    tile: Optional[SpatialTile] = None


class FarmPlotCreate(BaseModel):
    origin_x: int
    origin_y: int
    width: int
    height: int
    crop_type: Optional[str] = None


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
        "vlm_parse_success": 0,
        "vlm_parse_fail": 0,
        "vlm_errors": [],
        "available_skills_count": 0,
        "session_started_at": None,
        "think_count": 0,
        "action_count": 0,
        "action_fail_count": 0,
        "action_type_counts": {},
        "distance_traveled": 0,
        "crops_watered_count": 0,
        "crops_harvested_count": 0,
        "latency_history": [],
        "player_tile_x": None,
        "player_tile_y": None,
        "current_instruction": None,
        "navigation_target": None,
        "navigation_blocked": None,
        "navigation_attempts": 0,
        "commentary_text": "",
        "commentary_personality": "enthusiastic",
        "commentary_voice": "",  # Empty = use personality default
        "commentary_tts_enabled": False,
        "commentary_volume": 70,
        "vlm_observation": None,
        "proposed_action": None,
        "validation_status": None,
        "validation_reason": None,
        "executed_action": None,
        "executed_outcome": None,
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


def _default_farm_plan() -> Dict[str, Any]:
    return {
        "active": False,
        "plots": [],
        "current_tile": None,
        "next_tile": None,
        "active_plot_id": None,
    }


def _read_farm_plan() -> Dict[str, Any]:
    defaults = _default_farm_plan()
    if not FARM_PLAN_PATH.exists():
        return defaults
    try:
        data = json.loads(FARM_PLAN_PATH.read_text())
    except json.JSONDecodeError:
        defaults["active"] = False
        return defaults
    if not isinstance(data, dict):
        return defaults
    defaults.update(data)
    if not isinstance(defaults.get("plots"), list):
        defaults["plots"] = []
    return defaults


def _write_farm_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    FARM_PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    FARM_PLAN_PATH.write_text(json.dumps(plan, indent=2))
    return plan


def _next_plot_id(plots: List[Dict[str, Any]]) -> str:
    max_id = 0
    for plot in plots:
        plot_id = str(plot.get("id", ""))
        if plot_id.startswith("plot_"):
            suffix = plot_id.replace("plot_", "")
            if suffix.isdigit():
                max_id = max(max_id, int(suffix))
    return f"plot_{max_id + 1}"


def _read_lessons() -> Dict[str, Any]:
    if not LESSONS_PATH.exists():
        return {"lessons": [], "count": 0}
    try:
        data = json.loads(LESSONS_PATH.read_text())
    except json.JSONDecodeError:
        return {"lessons": [], "count": 0}
    if isinstance(data, dict):
        lessons = data.get("lessons")
        if not isinstance(lessons, list):
            lessons = []
        return {"lessons": lessons, "count": data.get("count", len(lessons))}
    if isinstance(data, list):
        return {"lessons": data, "count": len(data)}
    return {"lessons": [], "count": 0}


def _write_lessons(payload: Dict[str, Any]) -> Dict[str, Any]:
    LESSONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LESSONS_PATH.write_text(json.dumps(payload, indent=2))
    return payload


def _read_rusty_state() -> Dict[str, Any]:
    if not RUSTY_STATE_PATH.exists():
        return {}
    try:
        data = json.loads(RUSTY_STATE_PATH.read_text())
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _write_rusty_state(payload: Dict[str, Any]) -> Dict[str, Any]:
    RUSTY_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUSTY_STATE_PATH.write_text(json.dumps(payload, indent=2))
    return payload


def _summarize_action_failures(limit: int = 50, lesson_limit: int = 10) -> Dict[str, Any]:
    events = storage.list_session_events(limit=limit, event_type="action")
    stats: Dict[str, Dict[str, int]] = {}
    for event in events:
        data = event.get("data") or {}
        action = data.get("action_type") or data.get("action") or data.get("type")
        success = data.get("success")
        if not action:
            continue
        entry = stats.setdefault(action, {"success": 0, "fail": 0, "total": 0})
        entry["total"] += 1
        if success is False:
            entry["fail"] += 1
        else:
            entry["success"] += 1

    stats_list = []
    for action, entry in stats.items():
        total = entry["total"] or 1
        rate = entry["success"] / total
        stats_list.append({
            "action": action,
            "success": entry["success"],
            "fail": entry["fail"],
            "total": entry["total"],
            "success_rate": rate,
        })
    stats_list.sort(key=lambda item: (item["total"], item["success_rate"]), reverse=True)

    lessons_data = _read_lessons().get("lessons", [])
    lessons = lessons_data[-lesson_limit:] if isinstance(lessons_data, list) else []
    failure_counts: Dict[str, Dict[str, Any]] = {}
    for lesson in lessons:
        attempted = lesson.get("attempted") or lesson.get("action") or "unknown"
        blocked_by = lesson.get("blocked_by") or lesson.get("blocker") or "unknown"
        key = f"{attempted}::{blocked_by}"
        entry = failure_counts.setdefault(key, {
            "action": attempted,
            "reason": blocked_by,
            "count": 0,
        })
        entry["count"] += 1

    recent_failures = list(failure_counts.values())
    recent_failures.sort(key=lambda item: item["count"], reverse=True)

    return {"recent_failures": recent_failures, "stats": stats_list}


async def _watch_farm_plan() -> None:
    last_mtime = None
    while True:
        try:
            if FARM_PLAN_PATH.exists():
                mtime = FARM_PLAN_PATH.stat().st_mtime
                if last_mtime is None or mtime > last_mtime:
                    await manager.broadcast("farm_plan_updated", _read_farm_plan())
                    last_mtime = mtime
        except Exception:
            pass
        await asyncio.sleep(1.0)


def _resolve_tts_model(voice: str) -> Dict[str, Optional[Path]]:
    """Find TTS model files across multiple directories."""
    for model_dir in TTS_MODEL_DIRS:
        model_path = model_dir / f"{voice}.onnx"
        config_path = model_dir / f"{voice}.onnx.json"
        if model_path.exists():
            return {
                "model": model_path,
                "config": config_path if config_path.exists() else None,
            }
    return {"model": None, "config": None}


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
            # Non-blocking playback - don't wait for audio to finish
            subprocess.Popen(
                [APLAYER_CMD, str(cache_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return {"ok": True, "output": str(cache_path), "voice": voice, "cached": True}
        except Exception as exc:
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
        # Non-blocking playback - don't wait for audio to finish
        subprocess.Popen(
            [APLAYER_CMD, str(cache_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        try:
            shutil.copyfile(cache_path, output_path)
        except OSError:
            pass
        return {"ok": True, "output": str(cache_path), "voice": voice, "cached": False}
    except subprocess.CalledProcessError as exc:
        return {"ok": False, "error": f"TTS generation failed: {exc}"}


@app.on_event("startup")
async def on_startup() -> None:
    storage.init_db()
    _write_status({})
    asyncio.create_task(_watch_farm_plan())


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


@app.get("/api/commentary")
def get_commentary() -> Dict[str, Any]:
    status = _read_status()
    return {
        "text": status.get("commentary_text", ""),
        "personality": status.get("commentary_personality", "enthusiastic"),
        "voice": status.get("commentary_voice", ""),
        "tts_enabled": status.get("commentary_tts_enabled", False),
        "volume": status.get("commentary_volume", 70),
    }


@app.get("/api/commentary/voices")
def get_commentary_voices() -> Dict[str, Any]:
    """Return available TTS voices and their descriptions.
    
    Note: "personalities" is now just voice selection (cosmetic).
    Rusty's actual personality comes from VLM, not templates.
    """
    # Get voice options from rusty_character.py
    if get_voice_list:
        voice_list = get_voice_list()
        personalities = [v["key"] for v in voice_list]
        voice_descriptions = {v["key"]: v["description"] for v in voice_list}
    elif COMMENTARY_PERSONALITIES:
        personalities = sorted(COMMENTARY_PERSONALITIES.keys())
        voice_descriptions = {}
    else:
        personalities = ["default", "warm", "dry", "gravelly"]
        voice_descriptions = {}
    
    # Get available TTS voices from model files
    available_voices = []
    for model_dir in TTS_MODEL_DIRS:
        if model_dir.exists():
            for model in model_dir.glob("*.onnx"):
                voice_name = model.stem
                if voice_name not in available_voices:
                    available_voices.append(voice_name)
    available_voices.sort()
    
    # Get voice ID mappings
    voice_mappings = COMMENTARY_VOICES if COMMENTARY_VOICES else {}
    
    return {
        "personalities": personalities,  # Now voice options, not personality templates
        "voices": available_voices,
        "voice_mappings": voice_mappings,
        "voice_descriptions": voice_descriptions,  # New: descriptions for UI
    }


@app.post("/api/commentary")
async def update_commentary(payload: CommentaryUpdate) -> Dict[str, Any]:
    update: Dict[str, Any] = {}
    if payload.text is not None:
        update["commentary_text"] = payload.text
    if payload.personality is not None:
        update["commentary_personality"] = payload.personality
    if payload.voice is not None:
        update["commentary_voice"] = payload.voice
    if payload.tts_enabled is not None:
        update["commentary_tts_enabled"] = payload.tts_enabled
    if payload.volume is not None:
        update["commentary_volume"] = payload.volume
    status = _write_status(update)
    response = {
        "text": status.get("commentary_text", ""),
        "personality": status.get("commentary_personality", "enthusiastic"),
        "voice": status.get("commentary_voice", ""),
        "tts_enabled": status.get("commentary_tts_enabled", False),
        "volume": status.get("commentary_volume", 70),
    }
    await manager.broadcast("commentary_updated", response)
    return response


@app.post("/api/commentary/personality")
async def update_commentary_personality(payload: CommentaryPersonalityUpdate) -> Dict[str, Any]:
    status = _write_status({"commentary_personality": payload.personality})
    response = {
        "text": status.get("commentary_text", ""),
        "personality": status.get("commentary_personality", "enthusiastic"),
        "voice": status.get("commentary_voice", ""),
        "tts_enabled": status.get("commentary_tts_enabled", False),
        "volume": status.get("commentary_volume", 70),
    }
    await manager.broadcast("commentary_updated", response)
    return response


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


@app.get("/api/shipping")
def get_shipping(game_day: Optional[int] = None, limit: int = 200) -> List[Dict[str, Any]]:
    return storage.list_shipping_items(limit=limit, game_day=game_day)


@app.post("/api/shipping")
def add_shipping(payload: ShippingItemCreate) -> Dict[str, Any]:
    return storage.add_shipping_item(
        item_name=payload.item_name,
        quantity=payload.quantity,
        value=payload.value,
        shipped_at=payload.shipped_at,
        game_day=payload.game_day,
    )


@app.get("/api/skill-history")
def get_skill_history(limit: int = 200) -> List[Dict[str, Any]]:
    return storage.list_skill_history(limit=limit)


@app.post("/api/skill-history")
def add_skill_history(payload: SkillHistoryCreate) -> Dict[str, Any]:
    return storage.add_skill_execution(
        skill_name=payload.skill_name,
        success=payload.success,
        failure_reason=payload.failure_reason,
        created_at=payload.created_at,
    )


@app.get("/api/skill-stats")
def get_skill_stats(limit: int = 50) -> List[Dict[str, Any]]:
    return storage.list_skill_stats(limit=limit)


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

@app.get("/api/farm-plan")
def get_farm_plan() -> Dict[str, Any]:
    return _read_farm_plan()


@app.post("/api/farm-plan/plot")
async def update_farm_plan_plot(payload: FarmPlotCreate) -> Dict[str, Any]:
    plan = _read_farm_plan()
    plots = plan.get("plots", [])
    target = None
    for plot in plots:
        if (
            plot.get("origin_x") == payload.origin_x
            and plot.get("origin_y") == payload.origin_y
            and plot.get("width") == payload.width
            and plot.get("height") == payload.height
        ):
            target = plot
            break
    if target is None:
        target = {
            "id": _next_plot_id(plots),
            "origin_x": payload.origin_x,
            "origin_y": payload.origin_y,
            "width": payload.width,
            "height": payload.height,
            "phase": "clearing",
            "tiles": {},
        }
        plots.append(target)
    if payload.crop_type:
        target["crop_type"] = payload.crop_type
    plan["plots"] = plots
    plan["active"] = True
    plan.setdefault("active_plot_id", target.get("id"))
    updated = _write_farm_plan(plan)
    await manager.broadcast("farm_plan_updated", updated)
    return updated


@app.get("/api/lessons")
def get_lessons() -> Dict[str, Any]:
    return _read_lessons()


@app.post("/api/lessons/clear")
async def clear_lessons() -> Dict[str, Any]:
    payload = {"lessons": [], "count": 0}
    updated = _write_lessons(payload)
    await manager.broadcast("lessons_updated", updated)
    return updated


@app.post("/api/lessons/update")
async def update_lessons(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Receive lesson update from agent and broadcast to UI."""
    # Save to file and broadcast via WebSocket
    updated = _write_lessons(payload)
    await manager.broadcast("lessons_updated", updated)
    return {"status": "ok", "count": len(payload.get("lessons", []))}


@app.get("/api/rusty/memory")
def get_rusty_memory_api() -> Dict[str, Any]:
    data = _read_rusty_state()
    if data:
        return data
    if get_rusty_memory:
        try:
            return get_rusty_memory().to_api_format()
        except Exception:
            return {}
    return {}


@app.post("/api/rusty/memory")
async def update_rusty_memory_api(payload: Dict[str, Any]) -> Dict[str, Any]:
    updated = _write_rusty_state(payload)
    await manager.broadcast("rusty_memory_updated", updated)
    return updated


@app.get("/api/daily-plan")
def get_daily_plan() -> Dict[str, Any]:
    if get_daily_planner is None:
        raise HTTPException(status_code=503, detail="Daily planner unavailable")
    planner = get_daily_planner()
    return planner.to_api_format()


@app.get("/api/daily-summary")
def get_daily_summary() -> Dict[str, Any]:
    """Load yesterday's summary and today's derived goals."""
    try:
        return json.loads(DAILY_SUMMARY_PATH.read_text())
    except FileNotFoundError:
        return {"status": "no_summary", "message": "No summary yet. Complete a day first."}
    except json.JSONDecodeError:
        return {"status": "error", "message": "Summary file is invalid."}


@app.get("/api/action-failures")
def get_action_failures(limit: int = 50, lesson_limit: int = 10) -> Dict[str, Any]:
    return _summarize_action_failures(limit=limit, lesson_limit=lesson_limit)


@app.get("/api/spatial-map")
def get_spatial_map(
    location: str = "Farm",
    state: Optional[str] = None,
    crop: Optional[str] = None,
    watered: Optional[bool] = None,
    not_planted: bool = False,
    not_worked: bool = False,
) -> Dict[str, Any]:
    if SpatialMap is None:
        raise HTTPException(status_code=503, detail="Spatial map unavailable")
    spatial_map = SpatialMap(location)
    tiles = []
    for entry in spatial_map.find_tiles(
        state=state,
        crop=crop,
        watered=watered,
        not_planted=not_planted,
        not_worked=not_worked,
    ):
        data = dict(entry.data)
        data.setdefault("x", entry.x)
        data.setdefault("y", entry.y)
        tiles.append(data)
    return {"location": location, "tiles": tiles}


@app.post("/api/spatial-map")
async def update_spatial_map(payload: SpatialMapUpdate) -> Dict[str, Any]:
    if SpatialMap is None:
        raise HTTPException(status_code=503, detail="Spatial map unavailable")
    spatial_map = SpatialMap(payload.location)
    tiles = list(payload.tiles)
    if payload.tile:
        tiles.append(payload.tile)
    updated = spatial_map.update_tiles([tile.dict(exclude_none=True) for tile in tiles])
    await manager.broadcast("spatial_map_updated", {"location": payload.location, "tiles": updated})
    return {"location": payload.location, "tiles": updated}

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001)
