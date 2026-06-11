from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from .models import CallState, ClientInfo, ClientRole, SessionInfo, SignalMessage, SignalType

SendJson = Callable[[dict], Awaitable[None]]


@dataclass
class ConnectedClient:
    info: ClientInfo
    send_json: SendJson
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SessionManager:
    def __init__(self) -> None:
        self._clients: dict[str, ConnectedClient] = {}
        self._sessions: dict[str, SessionInfo] = {}

    @property
    def clients(self) -> dict[str, ClientInfo]:
        return {client_id: client.info for client_id, client in self._clients.items()}

    @property
    def sessions(self) -> dict[str, SessionInfo]:
        return dict(self._sessions)

    async def connect(
        self,
        *,
        client_id: str,
        role: ClientRole,
        device_id: str,
        send_json: SendJson,
    ) -> ClientInfo:
        info = ClientInfo(client_id=client_id, role=role, device_id=device_id)
        self._clients[client_id] = ConnectedClient(info=info, send_json=send_json)
        await self._broadcast_status()
        return info

    async def disconnect(self, client_id: str) -> None:
        client = self._clients.pop(client_id, None)
        if client is None:
            return

        for session in self._sessions.values():
            if client_id in {session.control_client_id, session.android_client_id}:
                session.state = CallState.ENDED

        await self._broadcast_status()

    async def handle_message(self, client_id: str, raw_message: dict) -> None:
        message = SignalMessage.model_validate(raw_message)
        client = self._require_client(client_id)
        client.last_seen = datetime.now(timezone.utc)

        if message.type == SignalType.HEARTBEAT:
            await client.send_json(self._status_message())
            return

        if message.type in {SignalType.REGISTER, SignalType.RECONNECT}:
            await self._broadcast_status()
            return

        if message.type == SignalType.SESSION_CREATE:
            session = self._create_session(client.info)
            await client.send_json(
                SignalMessage(
                    type=SignalType.STATUS,
                    session_id=session.session_id,
                    payload=self._status_payload(),
                ).model_dump(mode="json")
            )
            await self._broadcast_status()
            return

        if message.type == SignalType.CALL_START:
            session = self._require_session(message.session_id)
            session.state = CallState.CALLING
            await self._relay(client_id, message)
            await self._broadcast_status()
            return

        if message.type == SignalType.CALL_END:
            session = self._require_session(message.session_id)
            session.state = CallState.ENDED
            await self._relay(client_id, message)
            await self._broadcast_status()
            return

        if message.type in {SignalType.OFFER, SignalType.ANSWER, SignalType.ICE_CANDIDATE}:
            if message.type == SignalType.OFFER:
                session = self._require_session(message.session_id)
                session.state = CallState.CALLING
            elif message.type == SignalType.ANSWER:
                session = self._require_session(message.session_id)
                session.state = CallState.CONNECTED
            await self._relay(client_id, message)
            await self._broadcast_status()
            return

        raise ValueError(f"Unsupported signal type: {message.type}")

    def _create_session(self, requester: ClientInfo) -> SessionInfo:
        control = self._first_client(ClientRole.CONTROL)
        android = self._first_client(ClientRole.ANDROID)

        control_client_id = control.client_id if control else None
        android_client_id = android.client_id if android else None

        if requester.role == ClientRole.CONTROL:
            control_client_id = requester.client_id
        elif requester.role == ClientRole.ANDROID:
            android_client_id = requester.client_id

        for existing in self._sessions.values():
            if existing.control_client_id == control_client_id or existing.android_client_id == android_client_id:
                existing.state = CallState.ENDED

        session = SessionInfo(
            session_id=uuid4().hex,
            control_client_id=control_client_id,
            android_client_id=android_client_id,
            state=CallState.READY if control_client_id and android_client_id else CallState.IDLE,
        )

        self._sessions[session.session_id] = session
        return session

    async def _relay(self, source_client_id: str, message: SignalMessage) -> None:
        target_id = message.target or self._infer_target(source_client_id, message.session_id)
        if target_id is None:
            await self._clients[source_client_id].send_json(
                SignalMessage(
                    type=SignalType.ERROR,
                    session_id=message.session_id,
                    payload={"detail": "No relay target is available."},
                ).model_dump(mode="json")
            )
            return

        target = self._clients.get(target_id)
        if target is None:
            await self._clients[source_client_id].send_json(
                SignalMessage(
                    type=SignalType.ERROR,
                    session_id=message.session_id,
                    payload={"detail": f"Target client is not connected: {target_id}"},
                ).model_dump(mode="json")
            )
            return

        relay_message = message.model_copy(update={"source": source_client_id, "target": target_id})
        await target.send_json(relay_message.model_dump(mode="json"))

    def _infer_target(self, source_client_id: str, session_id: str | None) -> str | None:
        session = self._sessions.get(session_id or "")
        if session is None:
            return None
        if source_client_id == session.control_client_id:
            return session.android_client_id
        if source_client_id == session.android_client_id:
            return session.control_client_id
        return None

    def _first_client(self, role: ClientRole) -> ClientInfo | None:
        for client in self._clients.values():
            if client.info.role == role:
                return client.info
        return None

    def _require_client(self, client_id: str) -> ConnectedClient:
        client = self._clients.get(client_id)
        if client is None:
            raise KeyError(f"Unknown client: {client_id}")
        return client

    def _require_session(self, session_id: str | None) -> SessionInfo:
        if not session_id:
            raise ValueError("session_id is required")
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Unknown session: {session_id}")
        return session

    def _status_message(self) -> dict:
        return SignalMessage(
            type=SignalType.STATUS,
            payload=self._status_payload(),
        ).model_dump(mode="json")

    def _status_payload(self) -> dict:
        return {
            "clients": {key: value.model_dump(mode="json") for key, value in self.clients.items()},
            "sessions": {key: value.model_dump(mode="json") for key, value in self.sessions.items()},
        }

    async def _broadcast_status(self) -> None:
        status = self._status_message()
        for client in list(self._clients.values()):
            await client.send_json(status)
