"""
WebSocket connection manager for FootballVision Pro.
Manages persistent WS connections, channel subscriptions, broadcast loops,
command dispatch with idempotency, and eager refresh after state changes.
"""

import asyncio
import json
import time
import logging
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Protocol version
PROTOCOL_VERSION = 1

# Broadcast intervals (seconds)
CHANNEL_INTERVALS = {
    "status": 1.0,
    "pipeline_state": 2.0,
    "system_metrics": 3.0,
    "panorama_status": 3.0,
}

# All subscribable channels
ALL_CHANNELS = set(CHANNEL_INTERVALS.keys())

# Default channels on connect
DEFAULT_CHANNELS = {"status"}

# Max inbound message size (bytes)
MAX_MESSAGE_SIZE = 64 * 1024

# Max concurrent WebSocket connections
MAX_CONNECTIONS = 10

# Command idempotency cache
MAX_COMMAND_IDS = 200
COMMAND_ID_TTL = 60.0


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[WebSocket, set[str]] = {}
        self._broadcast_tasks: dict[str, asyncio.Task] = {}
        self._refresh_events: dict[str, asyncio.Event] = {
            ch: asyncio.Event() for ch in ALL_CHANNELS
        }
        self._channel_running: dict[str, bool] = {ch: False for ch in ALL_CHANNELS}
        self._data_sources: dict[str, Callable] = {}
        self._command_handler: Optional[Callable] = None
        self._recent_command_ids: OrderedDict[str, float] = OrderedDict()
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ws_executor")
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_data_sources(
        self,
        sources: dict[str, Callable],
        command_handler: Callable,
    ) -> None:
        """Register sync getter functions and command handler from app layer."""
        self._data_sources = sources
        self._command_handler = command_handler

    async def connect(self, websocket: WebSocket) -> None:
        if len(self._connections) >= MAX_CONNECTIONS:
            await websocket.close(code=1013, reason="Too many connections")
            logger.warning(f"WebSocket rejected: max {MAX_CONNECTIONS} connections reached")
            return
        await websocket.accept()
        self._connections[websocket] = set(DEFAULT_CHANNELS)
        self._loop = asyncio.get_event_loop()
        logger.info(f"WebSocket connected: {websocket.client}. Total: {len(self._connections)}")

        # Send hello
        await self._send(websocket, {
            "v": PROTOCOL_VERSION,
            "type": "hello",
            "channels": list(DEFAULT_CHANNELS),
        })

        # Start broadcast loops for default channels if not running
        self._ensure_broadcast_loops()

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.pop(websocket, None)
        logger.info(f"WebSocket disconnected. Total: {len(self._connections)}")

        # Cancel broadcast loops if no connections
        if not self._connections:
            self._cancel_broadcast_loops()

    async def handle_message(self, websocket: WebSocket, raw: str) -> None:
        if len(raw) > MAX_MESSAGE_SIZE:
            await self._send_error(websocket, "message_too_large", "Message exceeds 64KB limit")
            return

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await self._send_error(websocket, "invalid_json", "Message is not valid JSON")
            return

        if not isinstance(msg, dict):
            await self._send_error(websocket, "invalid_format", "Message must be a JSON object")
            return

        v = msg.get("v")
        if v != PROTOCOL_VERSION:
            await self._send_error(websocket, "invalid_version", f"Expected v={PROTOCOL_VERSION}")
            return

        msg_type = msg.get("type")
        if msg_type == "ping":
            await self._send(websocket, {"v": PROTOCOL_VERSION, "type": "pong"})

        elif msg_type == "subscribe":
            channels = msg.get("channels", [])
            if not isinstance(channels, list):
                await self._send_error(websocket, "invalid_channels", "channels must be a list")
                return
            valid = set(channels) & ALL_CHANNELS
            if websocket in self._connections:
                self._connections[websocket] |= valid
            self._ensure_broadcast_loops()

        elif msg_type == "unsubscribe":
            channels = msg.get("channels", [])
            if not isinstance(channels, list):
                await self._send_error(websocket, "invalid_channels", "channels must be a list")
                return
            if websocket in self._connections:
                self._connections[websocket] -= set(channels)

        elif msg_type == "command":
            await self._handle_command(websocket, msg)

        else:
            await self._send_error(websocket, "unknown_type", f"Unknown message type: {msg_type}")

    async def shutdown(self) -> None:
        self._cancel_broadcast_loops()
        self._executor.shutdown(wait=False)
        # Close all connections
        for ws in list(self._connections):
            try:
                await ws.close()
            except Exception:
                pass
        self._connections.clear()
        logger.info("WebSocket manager shut down")

    # ========================================================================
    # Command handling
    # ========================================================================

    async def _handle_command(self, websocket: WebSocket, msg: dict) -> None:
        cmd_id = msg.get("id")
        action = msg.get("action")
        params = msg.get("params", {})

        if not cmd_id or not action:
            await self._send_error(websocket, "invalid_command", "Command requires 'id' and 'action'")
            return

        # Idempotency check
        self._purge_expired_commands()
        if cmd_id in self._recent_command_ids:
            await self._send(websocket, {
                "v": PROTOCOL_VERSION,
                "type": "command_result",
                "id": cmd_id,
                "success": True,
                "deduplicated": True,
            })
            return

        # Cache the command ID
        self._recent_command_ids[cmd_id] = time.time()
        if len(self._recent_command_ids) > MAX_COMMAND_IDS:
            self._recent_command_ids.popitem(last=False)

        # Send ack immediately
        await self._send(websocket, {
            "v": PROTOCOL_VERSION,
            "type": "command_ack",
            "id": cmd_id,
            "action": action,
        })

        # Execute command in executor
        if not self._command_handler:
            await self._send(websocket, {
                "v": PROTOCOL_VERSION,
                "type": "command_result",
                "id": cmd_id,
                "success": False,
                "error": "Command handler not configured",
            })
            return

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                self._executor,
                self._command_handler,
                action,
                params,
            )
            await self._send(websocket, {
                "v": PROTOCOL_VERSION,
                "type": "command_result",
                "id": cmd_id,
                "success": True,
                "data": result,
            })

            # Trigger eager refresh for state-changing commands
            state_changing = {
                "start_recording", "stop_recording",
                "start_preview", "stop_preview",
            }
            if action in state_changing:
                for ch in ("status", "pipeline_state"):
                    if ch in self._refresh_events:
                        self._refresh_events[ch].set()

        except Exception as e:
            logger.error(f"Command '{action}' failed: {e}")
            await self._send(websocket, {
                "v": PROTOCOL_VERSION,
                "type": "command_result",
                "id": cmd_id,
                "success": False,
                "error": str(e),
            })

    def _purge_expired_commands(self) -> None:
        now = time.time()
        expired = [k for k, t in self._recent_command_ids.items() if now - t > COMMAND_ID_TTL]
        for k in expired:
            del self._recent_command_ids[k]

    # ========================================================================
    # Broadcast loops
    # ========================================================================

    def _ensure_broadcast_loops(self) -> None:
        """Start broadcast loops for channels that have subscribers."""
        needed = set()
        for subs in self._connections.values():
            needed |= subs

        for channel in needed:
            if channel not in self._broadcast_tasks or self._broadcast_tasks[channel].done():
                if channel in self._data_sources:
                    self._broadcast_tasks[channel] = asyncio.ensure_future(
                        self._broadcast_loop(channel)
                    )

    def _cancel_broadcast_loops(self) -> None:
        for task in self._broadcast_tasks.values():
            task.cancel()
        self._broadcast_tasks.clear()
        for ch in self._channel_running:
            self._channel_running[ch] = False

    async def _broadcast_loop(self, channel: str) -> None:
        interval = CHANNEL_INTERVALS.get(channel, 3.0)
        getter = self._data_sources.get(channel)
        if not getter:
            return

        logger.info(f"Broadcast loop started: {channel} (every {interval}s)")
        try:
            while True:
                # Wait for either interval or eager refresh event
                event = self._refresh_events.get(channel)
                try:
                    if event:
                        await asyncio.wait_for(event.wait(), timeout=interval)
                        event.clear()
                    else:
                        await asyncio.sleep(interval)
                except asyncio.TimeoutError:
                    if event:
                        event.clear()

                # Skip if previous getter still running (prevents pileup)
                if self._channel_running.get(channel, False):
                    continue

                # Check if any client subscribes to this channel
                subscribers = [
                    ws for ws, subs in self._connections.items()
                    if channel in subs
                ]
                if not subscribers:
                    continue

                self._channel_running[channel] = True
                try:
                    loop = asyncio.get_event_loop()
                    data = await loop.run_in_executor(self._executor, getter)
                    message = {
                        "v": PROTOCOL_VERSION,
                        "type": channel,
                        "ts": time.time(),
                        "data": data,
                    }
                    await self._broadcast(subscribers, message)
                except Exception as e:
                    logger.warning(f"Broadcast error for {channel}: {e}")
                finally:
                    self._channel_running[channel] = False

        except asyncio.CancelledError:
            logger.info(f"Broadcast loop cancelled: {channel}")

    # ========================================================================
    # Helpers
    # ========================================================================

    async def _broadcast(self, subscribers: list[WebSocket], message: dict) -> None:
        text = json.dumps(message)
        for ws in subscribers:
            try:
                await ws.send_text(text)
            except Exception:
                self.disconnect(ws)

    async def _send(self, websocket: WebSocket, message: dict) -> None:
        try:
            await websocket.send_text(json.dumps(message))
        except Exception:
            self.disconnect(websocket)

    async def _send_error(self, websocket: WebSocket, code: str, message: str) -> None:
        await self._send(websocket, {
            "v": PROTOCOL_VERSION,
            "type": "error",
            "code": code,
            "message": message,
        })


# Singleton instance
ws_manager = ConnectionManager()
