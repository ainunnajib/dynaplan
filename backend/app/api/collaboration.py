import json
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.collaboration import PresenceResponse, PresenceUpdate
from app.services.auth import decode_access_token, get_user_by_id
from app.services.collaboration import (
    build_presence_response,
    get_active_users,
    get_session_by_id,
    register_presence,
    remove_presence,
    update_cursor,
    update_heartbeat,
)
from app.services.planning_model import get_model_by_id

router = APIRouter(tags=["collaboration"])


# ---------------------------------------------------------------------------
# In-memory connection manager for WebSocket broadcasting
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manages active WebSocket connections per model_id."""

    def __init__(self) -> None:
        # model_id (str) -> list of (websocket, user_id str, session_id str)
        self._connections: Dict[str, List[dict]] = {}

    async def connect(
        self,
        model_id: str,
        websocket: WebSocket,
        user_id: str,
        session_id: str,
    ) -> None:
        await websocket.accept()
        if model_id not in self._connections:
            self._connections[model_id] = []
        self._connections[model_id].append(
            {"ws": websocket, "user_id": user_id, "session_id": session_id}
        )

    def disconnect(self, model_id: str, session_id: str) -> None:
        if model_id not in self._connections:
            return
        self._connections[model_id] = [
            c for c in self._connections[model_id] if c["session_id"] != session_id
        ]

    async def broadcast(
        self,
        model_id: str,
        message: dict,
        exclude_session_id: Optional[str] = None,
    ) -> None:
        """Send a JSON message to all connections on a model, optionally excluding one."""
        if model_id not in self._connections:
            return
        dead: List[dict] = []
        for conn in list(self._connections[model_id]):
            if exclude_session_id and conn["session_id"] == exclude_session_id:
                continue
            try:
                await conn["ws"].send_json(message)
            except Exception:
                dead.append(conn)
        for d in dead:
            self._connections[model_id].remove(d)

    async def send_personal(self, websocket: WebSocket, message: dict) -> None:
        try:
            await websocket.send_json(message)
        except Exception:
            pass


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/models/{model_id}/presence",
    response_model=List[PresenceResponse],
)
async def list_presence(
    model_id: uuid.UUID,
    module_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[PresenceResponse]:
    """List active users in a model (active within the last 60 seconds)."""
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )
    sessions = await get_active_users(db, model_id, module_id=module_id)
    return [build_presence_response(s) for s in sessions]


@router.post(
    "/models/{model_id}/presence",
    response_model=PresenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_presence(
    model_id: uuid.UUID,
    data: PresenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PresenceResponse:
    """Register or refresh presence for the current user in a model."""
    model = await get_model_by_id(db, model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )
    session = await register_presence(
        db,
        user_id=current_user.id,
        model_id=model_id,
        module_id=data.module_id,
    )
    return build_presence_response(session)


@router.delete(
    "/presence/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_presence(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove a presence session."""
    session = await get_session_by_id(db, session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presence session not found",
        )
    # Only the owning user can delete their own session
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot remove another user's presence session",
        )
    await remove_presence(db, session_id)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/models/{model_id}")
async def websocket_endpoint(
    model_id: str,
    websocket: WebSocket,
    token: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    WebSocket endpoint for real-time collaboration on a model.

    Connect with: ws://host/ws/models/{model_id}?token=<jwt>

    Message types:
      - cell_change: broadcast a cell value change to all users in the model
      - cursor_move: update and broadcast cursor position
      - heartbeat: keep the session alive
      - presence_join / presence_leave: emitted by the server on connect/disconnect
    """
    # --- Authenticate via query-param token ---
    if not token:
        await websocket.close(code=1008)  # Policy Violation
        return

    subject = decode_access_token(token)
    if subject is None:
        await websocket.close(code=1008)
        return

    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        await websocket.close(code=1008)
        return

    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        await websocket.close(code=1008)
        return

    # Validate model_id
    try:
        model_uuid = uuid.UUID(model_id)
    except ValueError:
        await websocket.close(code=1008)
        return

    model = await get_model_by_id(db, model_uuid)
    if model is None:
        await websocket.close(code=1008)
        return

    # Register presence
    session = await register_presence(db, user_id=user_id, model_id=model_uuid)
    session_id = str(session.id)

    await manager.connect(model_id, websocket, str(user_id), session_id)

    # Notify other users of join
    join_msg = {
        "type": "presence_join",
        "session_id": session_id,
        "user_id": str(user_id),
        "user_full_name": user.full_name,
    }
    await manager.broadcast(model_id, join_msg, exclude_session_id=session_id)

    # Send the joiner their own session_id
    await manager.send_personal(websocket, {
        "type": "connected",
        "session_id": session_id,
        "user_id": str(user_id),
    })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                await manager.send_personal(websocket, {"type": "error", "detail": "Invalid JSON"})
                continue

            msg_type = data.get("type")
            payload = data.get("payload", {})

            if msg_type == "heartbeat":
                await update_heartbeat(db, session.id)
                await manager.send_personal(websocket, {"type": "heartbeat_ack"})

            elif msg_type == "cell_change":
                # Broadcast to everyone else in the model
                broadcast_msg = {
                    "type": "cell_change",
                    "session_id": session_id,
                    "user_id": str(user_id),
                    "user_full_name": user.full_name,
                    "payload": payload,
                }
                await manager.broadcast(model_id, broadcast_msg, exclude_session_id=session_id)

            elif msg_type == "cursor_move":
                cell_ref = payload.get("cell_ref") if payload else None
                await update_cursor(db, session.id, cell_ref)
                broadcast_msg = {
                    "type": "cursor_move",
                    "session_id": session_id,
                    "user_id": str(user_id),
                    "user_full_name": user.full_name,
                    "payload": {"cell_ref": cell_ref},
                }
                await manager.broadcast(model_id, broadcast_msg, exclude_session_id=session_id)

            else:
                await manager.send_personal(
                    websocket,
                    {"type": "error", "detail": f"Unknown message type: {msg_type}"},
                )

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(model_id, session_id)
        await remove_presence(db, session.id)
        leave_msg = {
            "type": "presence_leave",
            "session_id": session_id,
            "user_id": str(user_id),
            "user_full_name": user.full_name,
        }
        await manager.broadcast(model_id, leave_msg)
