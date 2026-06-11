from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .models import ClientRole, SignalMessage, SignalType
from .session_manager import SessionManager

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"

app = FastAPI(title="Rescue Voice Signaling Server", version="0.1.0")
manager = SessionManager()

if FRONTEND_ROOT.exists():
    app.mount("/frontend", StaticFiles(directory=FRONTEND_ROOT), name="frontend")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/status")
async def status() -> dict:
    return {
        "clients": {key: value.model_dump(mode="json") for key, value in manager.clients.items()},
        "sessions": {key: value.model_dump(mode="json") for key, value in manager.sessions.items()},
    }


@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/frontend/control_dashboard/index.html")


@app.get("/android")
async def android() -> RedirectResponse:
    return RedirectResponse(url="/frontend/android_device/index.html")


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    role: ClientRole = ClientRole.TEST,
    device_id: str | None = None,
) -> None:
    await websocket.accept()
    await manager.connect(
        client_id=client_id,
        role=role,
        device_id=device_id or client_id,
        send_json=websocket.send_json,
    )
    await websocket.send_json(
        SignalMessage(
            type=SignalType.REGISTER,
            source="server",
            payload={"client_id": client_id, "role": role.value, "device_id": device_id or client_id},
        ).model_dump(mode="json")
    )

    try:
        while True:
            message = await websocket.receive_json()
            try:
                await manager.handle_message(client_id, message)
            except Exception as exc:  # noqa: BLE001 - return protocol errors to the connected client.
                logger.exception("Failed to handle signaling message")
                await websocket.send_json(
                    SignalMessage(
                        type=SignalType.ERROR,
                        source="server",
                        payload={"detail": str(exc)},
                    ).model_dump(mode="json")
                )
    except WebSocketDisconnect:
        await manager.disconnect(client_id)
