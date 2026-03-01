import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class PresenceUpdate(BaseModel):
    model_id: uuid.UUID
    module_id: Optional[uuid.UUID] = None
    cursor_cell: Optional[str] = None


class PresenceResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    model_id: uuid.UUID
    module_id: Optional[uuid.UUID]
    connected_at: datetime
    last_heartbeat: datetime
    cursor_cell: Optional[str]
    user_email: Optional[str] = None
    user_full_name: Optional[str] = None

    model_config = {"from_attributes": True}


class CellChangeEvent(BaseModel):
    line_item_id: str
    dimension_members: List[Dict[str, str]]
    value: Any
    module_id: Optional[str] = None


class WebSocketMessage(BaseModel):
    type: str  # cell_change | cursor_move | presence_join | presence_leave | heartbeat
    payload: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    user_full_name: Optional[str] = None
