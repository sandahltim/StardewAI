from typing import Any, Dict, List, Optional

import httpx


class UIClient:
    """Lightweight client for the StardewAI UI API."""

    def __init__(self, base_url: str = "http://localhost:9001", timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout)

    def send_message(self, role: str, content: str, reasoning: Optional[str] = None) -> Dict[str, Any]:
        payload = {"role": role, "content": content, "reasoning": reasoning}
        return self._post("/api/messages", payload)

    def list_messages(self, limit: int = 50, since_id: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {}
        if limit:
            params["limit"] = limit
        if since_id:
            params["since_id"] = since_id
        response = self.client.get(f"{self.base_url}/api/messages", params=params)
        response.raise_for_status()
        return response.json()

    def stream_message(
        self,
        message_id: Optional[int],
        role: str = "agent",
        content: Optional[str] = None,
        reasoning: Optional[str] = None,
        append: bool = True,
    ) -> Dict[str, Any]:
        payload = {
            "message_id": message_id,
            "role": role,
            "content": content,
            "reasoning": reasoning,
            "append": append,
        }
        return self._post("/api/messages/stream", payload)

    def set_pending_action(
        self,
        text: str,
        action_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "pending_action": text,
            "pending_action_id": action_id,
            "pending_action_at": timestamp,
        }
        return self._post("/api/action/pending", payload)

    def clear_pending_action(self) -> Dict[str, Any]:
        return self._post("/api/action/clear", {})

    def update_status(self, **fields: Any) -> Dict[str, Any]:
        return self._post("/api/status", fields)

    def request_tts(self, message_id: Optional[int] = None, text: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if message_id is not None:
            payload["message_id"] = message_id
        if text is not None:
            payload["text"] = text
        return self._post("/api/tts", payload)

    def add_session_event(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {"event_type": event_type, "data": data or {}}
        return self._post("/api/session-memory", payload)

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self.client.post(f"{self.base_url}{path}", json=payload)
        response.raise_for_status()
        return response.json()
