from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field

import websockets


@dataclass
class TestClient:
    client_id: str
    role: str
    device_id: str
    server: str
    websocket: object | None = None
    messages: list[dict] = field(default_factory=list)

    @property
    def uri(self) -> str:
        return f"{self.server.rstrip('/')}/ws/{self.client_id}?role={self.role}&device_id={self.device_id}"

    async def connect(self) -> None:
        self.websocket = await websockets.connect(self.uri)

    async def close(self) -> None:
        if self.websocket is not None:
            await self.websocket.close()

    async def send(self, message: dict) -> None:
        if self.websocket is None:
            raise RuntimeError("client is not connected")
        await self.websocket.send(json.dumps(message))

    async def receive_until(self, message_type: str, timeout: float = 5.0, predicate=None) -> dict:
        if self.websocket is None:
            raise RuntimeError("client is not connected")

        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError(f"{self.client_id} did not receive {message_type}")
            raw = await asyncio.wait_for(self.websocket.recv(), timeout=remaining)
            message = json.loads(raw)
            self.messages.append(message)
            if message.get("type") == message_type and (predicate is None or predicate(message)):
                return message


async def run(server: str) -> None:
    control = TestClient("control-test", "control", "control-pc", server)
    android = TestClient("android-test", "android", "robot-top-phone", server)

    try:
        await control.connect()
        await android.connect()
        await control.receive_until("register")
        await android.receive_until("register")

        await control.send({"type": "session_create"})
        session_status = await control.receive_until(
            "status",
            predicate=lambda message: bool(message.get("payload", {}).get("sessions")),
        )
        sessions = session_status["payload"]["sessions"]
        session_id = next(iter(sessions))

        fake_offer = {"type": "offer", "sdp": "fake-offer"}
        await control.send({"type": "offer", "session_id": session_id, "payload": fake_offer})
        offer = await android.receive_until("offer")
        assert offer["payload"] == fake_offer

        fake_answer = {"type": "answer", "sdp": "fake-answer"}
        await android.send({"type": "answer", "session_id": session_id, "payload": fake_answer})
        answer = await control.receive_until("answer")
        assert answer["payload"] == fake_answer

        await control.send(
            {
                "type": "ice_candidate",
                "session_id": session_id,
                "payload": {"candidate": {"candidate": "candidate:fake"}},
            }
        )
        await android.receive_until("ice_candidate")

        print("signaling flow test passed")
    finally:
        await control.close()
        await android.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-end WebSocket signaling flow test.")
    parser.add_argument("--server", default="ws://127.0.0.1:8000")
    args = parser.parse_args()
    asyncio.run(run(args.server))


if __name__ == "__main__":
    main()
