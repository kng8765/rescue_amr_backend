from __future__ import annotations

import asyncio

from voice_server.models import ClientRole, SignalType
from voice_server.session_manager import SessionManager


class Sink:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, message: dict) -> None:
        self.messages.append(message)


def run(coro):
    return asyncio.run(coro)


def test_session_create_becomes_ready_when_control_and_android_are_connected() -> None:
    async def scenario() -> dict:
        manager = SessionManager()
        control = Sink()
        android = Sink()
        await manager.connect(
            client_id="control-1",
            role=ClientRole.CONTROL,
            device_id="control-pc",
            send_json=control.send_json,
        )
        await manager.connect(
            client_id="android-1",
            role=ClientRole.ANDROID,
            device_id="robot-top-phone",
            send_json=android.send_json,
        )
        await manager.handle_message("control-1", {"type": SignalType.SESSION_CREATE.value})
        return next(iter(manager.sessions.values())).model_dump(mode="json")

    session = run(scenario())

    assert session["state"] == "ready"
    assert session["control_client_id"] == "control-1"
    assert session["android_client_id"] == "android-1"


def test_offer_is_relayed_to_the_other_session_peer() -> None:
    async def scenario() -> list[dict]:
        manager = SessionManager()
        control = Sink()
        android = Sink()
        await manager.connect(
            client_id="control-1",
            role=ClientRole.CONTROL,
            device_id="control-pc",
            send_json=control.send_json,
        )
        await manager.connect(
            client_id="android-1",
            role=ClientRole.ANDROID,
            device_id="robot-top-phone",
            send_json=android.send_json,
        )
        await manager.handle_message("control-1", {"type": SignalType.SESSION_CREATE.value})
        session_id = next(iter(manager.sessions))
        await manager.handle_message(
            "control-1",
            {
                "type": SignalType.OFFER.value,
                "session_id": session_id,
                "payload": {"sdp": "fake-offer", "type": "offer"},
            },
        )
        return android.messages

    messages = run(scenario())

    assert any(message["type"] == "offer" and message["payload"]["sdp"] == "fake-offer" for message in messages)
