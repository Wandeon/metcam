import asyncio
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path


class FakeWebSocket:
    def __init__(self) -> None:
        self.client = ("127.0.0.1", 12345)
        self.accepted = False
        self.closed = False
        self.close_code = None
        self.close_reason = None
        self.sent: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))

    async def close(self, code: int | None = None, reason: str | None = None) -> None:
        self.closed = True
        self.close_code = code
        self.close_reason = reason


def load_ws_manager_module():
    if "fastapi" not in sys.modules:
        fastapi_stub = types.ModuleType("fastapi")
        fastapi_stub.WebSocket = object
        sys.modules["fastapi"] = fastapi_stub

    module_name = "ws_manager_test_module"
    module_path = Path(__file__).resolve().parents[1] / "src/platform/ws_manager.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if not spec or not spec.loader:
        raise RuntimeError("Could not load ws_manager module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class TestConnectionManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.ws_module = load_ws_manager_module()
        self.original_status_interval = self.ws_module.CHANNEL_INTERVALS["status"]
        self.ws_module.CHANNEL_INTERVALS["status"] = 0.05
        self.manager = self.ws_module.ConnectionManager()
        self.status_counter = 0

        def status_getter():
            self.status_counter += 1
            return {"counter": self.status_counter}

        self.manager.set_data_sources(
            sources={"status": status_getter},
            command_handler=lambda action, params: {"action": action, "params": params},
        )
        self.ws = FakeWebSocket()
        await self.manager.connect(self.ws)

    async def asyncTearDown(self) -> None:
        await self.manager.shutdown()
        self.ws_module.CHANNEL_INTERVALS["status"] = self.original_status_interval

    async def test_connect_sends_hello(self) -> None:
        self.assertTrue(self.ws.accepted)
        self.assertGreaterEqual(len(self.ws.sent), 1)
        hello = self.ws.sent[0]
        self.assertEqual(hello["type"], "hello")
        self.assertEqual(hello["v"], 1)
        self.assertIn("status", hello["channels"])

    async def test_ping_pong(self) -> None:
        await self.manager.handle_message(self.ws, json.dumps({"v": 1, "type": "ping"}))
        self.assertEqual(self.ws.sent[-1]["type"], "pong")

    async def test_command_ack_and_result(self) -> None:
        await self.manager.handle_message(
            self.ws,
            json.dumps({
                "v": 1,
                "type": "command",
                "id": "cmd-1",
                "action": "do_work",
                "params": {"x": 1},
            }),
        )

        command_messages = [m for m in self.ws.sent if m["type"] in {"command_ack", "command_result"}]
        self.assertEqual(command_messages[0]["type"], "command_ack")
        self.assertEqual(command_messages[0]["id"], "cmd-1")
        self.assertEqual(command_messages[1]["type"], "command_result")
        self.assertTrue(command_messages[1]["success"])
        self.assertEqual(command_messages[1]["data"]["action"], "do_work")

    async def test_duplicate_command_replays_cached_success(self) -> None:
        payload = {
            "v": 1,
            "type": "command",
            "id": "cmd-dup-success",
            "action": "echo",
            "params": {"value": 42},
        }

        await self.manager.handle_message(self.ws, json.dumps(payload))
        first_result = [m for m in self.ws.sent if m.get("id") == "cmd-dup-success" and m["type"] == "command_result"][-1]

        await self.manager.handle_message(self.ws, json.dumps(payload))
        second_result = [m for m in self.ws.sent if m.get("id") == "cmd-dup-success" and m["type"] == "command_result"][-1]

        self.assertTrue(first_result["success"])
        self.assertTrue(second_result["success"])
        self.assertEqual(first_result["data"], second_result["data"])
        self.assertTrue(second_result.get("deduplicated"))

    async def test_duplicate_command_replays_cached_failure(self) -> None:
        self.manager.set_data_sources(
            sources={"status": lambda: {"ok": True}},
            command_handler=lambda _action, _params: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        payload = {"v": 1, "type": "command", "id": "cmd-dup-fail", "action": "explode", "params": {}}

        await self.manager.handle_message(self.ws, json.dumps(payload))
        first_result = [m for m in self.ws.sent if m.get("id") == "cmd-dup-fail" and m["type"] == "command_result"][-1]

        await self.manager.handle_message(self.ws, json.dumps(payload))
        second_result = [m for m in self.ws.sent if m.get("id") == "cmd-dup-fail" and m["type"] == "command_result"][-1]

        self.assertFalse(first_result["success"])
        self.assertFalse(second_result["success"])
        self.assertIn("boom", first_result["error"])
        self.assertIn("boom", second_result["error"])
        self.assertTrue(second_result.get("deduplicated"))

    async def test_duplicate_command_while_in_progress_returns_in_progress_ack(self) -> None:
        def slow_handler(_action, _params):
            import time

            time.sleep(0.2)
            return {"ok": True}

        self.manager.set_data_sources(
            sources={"status": lambda: {"ok": True}},
            command_handler=slow_handler,
        )
        payload = {"v": 1, "type": "command", "id": "cmd-in-progress", "action": "slow", "params": {}}

        first_task = asyncio.create_task(self.manager.handle_message(self.ws, json.dumps(payload)))
        await asyncio.sleep(0.03)
        await self.manager.handle_message(self.ws, json.dumps(payload))
        await first_task

        duplicate_ack = [
            m
            for m in self.ws.sent
            if m.get("id") == "cmd-in-progress"
            and m["type"] == "command_ack"
            and m.get("deduplicated")
            and m.get("in_progress")
        ]
        final_results = [
            m for m in self.ws.sent if m.get("id") == "cmd-in-progress" and m["type"] == "command_result"
        ]

        self.assertEqual(len(duplicate_ack), 1)
        self.assertEqual(len(final_results), 1)
        self.assertTrue(final_results[0]["success"])

    async def test_broadcast_status_to_subscriber(self) -> None:
        # Give the broadcast loop enough time for at least one status tick.
        await asyncio.sleep(0.15)
        status_messages = [m for m in self.ws.sent if m["type"] == "status"]
        self.assertGreaterEqual(len(status_messages), 1)
        self.assertIn("counter", status_messages[-1]["data"])

    async def test_invalid_version_returns_error(self) -> None:
        await self.manager.handle_message(self.ws, json.dumps({"v": 999, "type": "ping"}))
        self.assertEqual(self.ws.sent[-1]["type"], "error")
        self.assertEqual(self.ws.sent[-1]["code"], "invalid_version")


if __name__ == "__main__":
    unittest.main()
