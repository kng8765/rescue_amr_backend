from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ClientRole(str, Enum):
    CONTROL = "control"
    ANDROID = "android"
    TEST = "test"


class CallState(str, Enum):
    IDLE = "idle"
    READY = "ready"
    CALLING = "calling"
    CONNECTED = "connected"
    ENDED = "ended"
    ERROR = "error"


class SignalType(str, Enum):
    REGISTER = "register"
    SESSION_CREATE = "session_create"
    OFFER = "offer"
    ANSWER = "answer"
    ICE_CANDIDATE = "ice_candidate"
    CALL_START = "call_start"
    CALL_END = "call_end"
    HEARTBEAT = "heartbeat"
    RECONNECT = "reconnect"
    STATUS = "status"
    ERROR = "error"


class SignalMessage(BaseModel):
    type: SignalType
    session_id: str | None = None
    source: str | None = None
    target: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ClientInfo(BaseModel):
    client_id: str
    role: ClientRole
    device_id: str
    connected: bool = True


class SessionInfo(BaseModel):
    session_id: str
    control_client_id: str | None = None
    android_client_id: str | None = None
    state: CallState = CallState.IDLE
