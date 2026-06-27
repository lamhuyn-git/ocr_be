from __future__ import annotations
import logging
from uuid import UUID
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:

    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = {} 

    def register(self, user_id: UUID, websocket: WebSocket) -> None:
        self._connections.setdefault(user_id, set()).add(websocket)
        logger.info("WS connected: user=%s", user_id)

    def disconnect(self, user_id: UUID, websocket: WebSocket) -> None:
        conns = self._connections.get(user_id)
        if not conns:
            return
        conns.discard(websocket)
        if not conns:                  
            self._connections.pop(user_id, None)

    # Kiểm tra user có đang mở web không
    def is_online(self, user_id: UUID) -> bool:
        return bool(self._connections.get(user_id))


    async def send_to_user(self, user_id: UUID, message: dict) -> None:
        conns = self._connections.get(user_id)
        logger.info("send_to_user: user=%s conns=%d", user_id, len(conns) if conns else 0)
        if not conns:
            return
        for ws in list(conns):              
            try:
                await ws.send_json(message)
            except Exception:
                conns.discard(ws)         


manager = ConnectionManager()