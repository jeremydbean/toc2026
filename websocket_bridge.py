from __future__ import annotations

import asyncio
import os

from websockets.server import WebSocketServerProtocol, serve


# Configuration
MUD_HOST: str = os.getenv("MUD_HOST", "mud-server")
MUD_PORT: int = int(os.getenv("MUD_PORT", 4000))
WS_PORT: int = int(os.getenv("WS_PORT", 8081))


async def forward_mud_to_ws(
    reader: asyncio.StreamReader, websocket: WebSocketServerProtocol
) -> None:
    """Reads bytes from MUD Telnet and sends text to WebSocket."""
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break

            text = data.decode("latin-1", errors="ignore")
            await websocket.send(text)
    except Exception as error:  # pragma: no cover - defensive logging
        print(f"Error sending to WS: {error}")


async def forward_ws_to_mud(
    writer: asyncio.StreamWriter, websocket: WebSocketServerProtocol
) -> None:
    """Reads text from WebSocket and sends bytes to MUD Telnet."""
    try:
        async for message in websocket:
            if not message.endswith("\n"):
                message += "\n"

            writer.write(message.encode("latin-1"))
            await writer.drain()
    except Exception as error:  # pragma: no cover - defensive logging
        print(f"Error sending to MUD: {error}")


async def mud_handler(websocket: WebSocketServerProtocol, _path: str) -> None:
    print(f"New Web Client Connected: {websocket.remote_address}")

    try:
        reader, writer = await asyncio.open_connection(MUD_HOST, MUD_PORT)

        task1 = asyncio.create_task(forward_mud_to_ws(reader, websocket))
        task2 = asyncio.create_task(forward_ws_to_mud(writer, websocket))

        done, pending = await asyncio.wait(
            [task1, task2],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
        writer.close()
        await writer.wait_closed()

    except ConnectionRefusedError:
        await websocket.send(
            "\n\r\x1b[31m[System]: The Game Server is currently offline.\x1b[0m\n\r"
        )
    except Exception as error:  # pragma: no cover - defensive logging
        print(f"Bridge Error: {error}")
    finally:
        print("Web Client Disconnected")


async def main() -> None:
    print(f"Starting WebSocket Bridge on port {WS_PORT}...")
    print(f"Forwarding to MUD at {MUD_HOST}:{MUD_PORT}")

    async with serve(mud_handler, "0.0.0.0", WS_PORT):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:  # pragma: no cover - user initiated
        print("\nBridge Stopped.")
