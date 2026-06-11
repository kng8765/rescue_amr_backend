from __future__ import annotations

import argparse
import asyncio
import json

import websockets


async def run_client(server: str, client_id: str, role: str, device_id: str) -> None:
    uri = f"{server.rstrip('/')}/ws/{client_id}?role={role}&device_id={device_id}"
    async with websockets.connect(uri) as websocket:
        print(f"connected: {uri}")
        await websocket.send(json.dumps({"type": "register"}))

        async def receive_loop() -> None:
            async for message in websocket:
                print(message)

        async def heartbeat_loop() -> None:
            while True:
                await websocket.send(json.dumps({"type": "heartbeat"}))
                await asyncio.sleep(5)

        await asyncio.gather(receive_loop(), heartbeat_loop())


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal WebSocket signaling test client.")
    parser.add_argument("--server", default="ws://127.0.0.1:8000")
    parser.add_argument("--client-id", default="control-test")
    parser.add_argument("--role", choices=["control", "android", "test"], default="control")
    parser.add_argument("--device-id", default="control-pc")
    args = parser.parse_args()

    asyncio.run(run_client(args.server, args.client_id, args.role, args.device_id))


if __name__ == "__main__":
    main()
