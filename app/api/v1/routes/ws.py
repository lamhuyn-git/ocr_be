from __future__ import annotations
import logging
from uuid import UUID
import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.database import AsyncSessionLocal
from app.models.user import User
from app.core.security import decode_token
from app.realtime.connection_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()


async def _authenticate(token: str | None) -> User | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    async with AsyncSessionLocal() as db:        
        user = await db.get(User, UUID(user_id))
    if not user or not user.is_active:
        return None
    return user


@router.websocket("/ws/notifications")
async def notifications_ws(websocket: WebSocket) -> None:
    await websocket.accept()                              
    try:
        first = await websocket.receive_json()          
    except Exception:
        await websocket.close(code=4401)                 
        return

    token = first.get("token") if isinstance(first, dict) else None
    user = await _authenticate(token)                    
    if user is None:
        await websocket.close(code=4401)                 
        return

    manager.register(user.id, websocket)                 
    await websocket.send_json({"event": "connected"})    
    try:
        while True:
            await websocket.receive_text()               
    except WebSocketDisconnect:
        manager.disconnect(user.id, websocket)
    except Exception:
        manager.disconnect(user.id, websocket)