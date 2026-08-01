from __future__ import annotations

import asyncio
import logging
import os
import signal
import threading
import time
from fastapi import WebSocket


class EndpointFilter(logging.Filter):
    """
    Log filter to hide successful high-frequency polling requests
    to reduce console noise.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return (
            "GET /api/v1/query/runtime/status" not in message
            and "GET /api/v1/query/roleplay/session" not in message
        )


class ConnectionManager:
    BROADCAST_SEND_TIMEOUT_SECONDS = 2.0

    def __init__(self, *, runtime=None, is_idle_shutdown_enabled=None):
        self.runtime = runtime
        self.is_idle_shutdown_enabled = is_idle_shutdown_enabled or (lambda: False)
        self.active_connections: list[WebSocket] = []
        self._shutdown_timer: threading.Timer | None = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

        if self._shutdown_timer:
            self._shutdown_timer.cancel()
            self._shutdown_timer = None

        if len(self.active_connections) == 1:
            print("[Auto-Control] Client connection detected, game paused, waiting for user input.")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        if len(self.active_connections) == 0:
            self._set_pause_state(True, "所有客户端已断开，自动暂停游戏以节省资源。")

            if self.is_idle_shutdown_enabled():
                print("[Auto-Control] All clients disconnected. Server will shutdown in 5 seconds...")

                def _do_shutdown():
                    print("[Auto-Control] Auto shutdown triggered due to no active connections.")
                    os._exit(0)

                self._shutdown_timer = threading.Timer(5.0, _do_shutdown)
                self._shutdown_timer.start()

    def _set_pause_state(self, should_pause: bool, log_msg: str):
        runtime = self.runtime
        if runtime is None:
            return

        if runtime.get("is_paused") != should_pause:
            runtime.set_paused(should_pause)
            print(f"[Auto-Control] {log_msg}")

    async def broadcast(self, message: dict):
        import json

        txt = json.dumps(message, default=str)
        connections = list(self.active_connections)

        async def send(connection: WebSocket) -> WebSocket | None:
            try:
                await asyncio.wait_for(
                    connection.send_text(txt),
                    timeout=self.BROADCAST_SEND_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                print(f"Broadcast error: {exc}")
                return connection
            return None

        disconnected = [
            connection
            for connection in await asyncio.gather(*(send(connection) for connection in connections))
            if connection is not None
        ]

        for connection in disconnected:
            self.disconnect(connection)


def trigger_process_shutdown(*, is_dev_mode: bool) -> dict[str, str]:
    def _shutdown():
        time.sleep(1)
        if is_dev_mode:
            try:
                os.kill(os.getpid(), signal.SIGINT)
                time.sleep(1)
            except Exception:
                pass
        os._exit(0)

    threading.Thread(target=_shutdown).start()
    return {"status": "shutting_down", "message": "Server is shutting down..."}


def patch_sys_streams() -> None:
    """修复无控制台模式下 sys.stdout/stderr 为 None 导致 uvicorn 报错的问题"""
    from src.server.encoding_runtime import configure_process_encoding

    configure_process_encoding()
