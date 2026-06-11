from __future__ import annotations

import os

import uvicorn


def main() -> None:
    ssl_certfile = os.getenv("VOICE_SSL_CERTFILE")
    ssl_keyfile = os.getenv("VOICE_SSL_KEYFILE")

    uvicorn.run(
        "voice_server.app:app",
        host=os.getenv("VOICE_HOST", "0.0.0.0"),
        port=int(os.getenv("VOICE_PORT", "8000")),
        reload=False,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
    )


if __name__ == "__main__":
    main()
