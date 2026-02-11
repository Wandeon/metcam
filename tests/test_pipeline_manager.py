import importlib.util
import json
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path


def load_pipeline_manager_module():
    module_name = f"pipeline_manager_test_{time.time_ns()}"
    module_path = Path(__file__).resolve().parents[1] / "src/video-pipeline/pipeline_manager.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if not spec or not spec.loader:
        raise RuntimeError("Could not load pipeline_manager module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def create_fresh_manager(module, lock_dir: Path):
    cls = module.PipelineManager
    cls._instance = None
    cls.LOCK_DIR = lock_dir
    cls.LOCK_FILE = lock_dir / "camera.lock"
    cls.STATE_FILE = lock_dir / "pipeline_state.json"
    return cls()


class TestPipelineManager(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_pipeline_manager_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.lock_dir = Path(self.tmp.name) / "locks"
        self.manager = create_fresh_manager(self.module, self.lock_dir)

    def tearDown(self) -> None:
        try:
            self.manager._force_release()
        except Exception:
            pass
        self.module.PipelineManager._instance = None
        self.tmp.cleanup()

    def test_acquire_and_release_lock(self) -> None:
        ok = self.manager.acquire_lock(self.module.PipelineMode.PREVIEW, "preview-holder")
        self.assertTrue(ok)
        state = self.manager.get_state()
        self.assertEqual(state["mode"], "preview")
        self.assertEqual(state["holder"], "preview-holder")

        released = self.manager.release_lock("preview-holder")
        self.assertTrue(released)
        state = self.manager.get_state()
        self.assertEqual(state["mode"], "idle")
        self.assertIsNone(state["holder"])

    def test_idempotent_reacquire_same_holder_same_mode(self) -> None:
        self.assertTrue(self.manager.acquire_lock(self.module.PipelineMode.RECORDING, "rec-1"))
        self.assertTrue(self.manager.acquire_lock(self.module.PipelineMode.RECORDING, "rec-1"))
        state = self.manager.get_state()
        self.assertEqual(state["mode"], "recording")
        self.assertEqual(state["holder"], "rec-1")

    def test_conflicting_holder_rejected_without_force(self) -> None:
        self.assertTrue(self.manager.acquire_lock(self.module.PipelineMode.PREVIEW, "preview-1"))
        self.assertFalse(self.manager.acquire_lock(self.module.PipelineMode.RECORDING, "recording-2", force=False))
        state = self.manager.get_state()
        self.assertEqual(state["mode"], "preview")
        self.assertEqual(state["holder"], "preview-1")

    def test_force_acquire_replaces_existing_holder(self) -> None:
        self.assertTrue(self.manager.acquire_lock(self.module.PipelineMode.PREVIEW, "preview-1"))
        self.assertTrue(self.manager.acquire_lock(self.module.PipelineMode.RECORDING, "recording-2", force=True))
        state = self.manager.get_state()
        self.assertEqual(state["mode"], "recording")
        self.assertEqual(state["holder"], "recording-2")

    def test_wait_for_idle_unblocks_after_release(self) -> None:
        self.assertTrue(self.manager.acquire_lock(self.module.PipelineMode.PREVIEW, "preview-1"))

        def delayed_release():
            time.sleep(0.2)
            self.manager.release_lock("preview-1")

        threading.Thread(target=delayed_release, daemon=True).start()
        self.assertTrue(self.manager.wait_for_idle(timeout=1.0))

    def test_stale_lock_state_is_cleaned_up_on_init(self) -> None:
        stale_dir = Path(self.tmp.name) / "stale"
        stale_dir.mkdir(parents=True, exist_ok=True)
        stale_state_file = stale_dir / "pipeline_state.json"
        stale_state_file.write_text(
            json.dumps(
                {
                    "mode": "preview",
                    "holder": "stale-holder",
                    "lock_time": (datetime.now() - timedelta(minutes=10)).isoformat(),
                    "pid": 99999,
                }
            ),
            encoding="utf-8",
        )

        stale_manager = create_fresh_manager(self.module, stale_dir)
        state = stale_manager.get_state()
        self.assertEqual(state["mode"], "idle")
        self.assertIsNone(state["holder"])


if __name__ == "__main__":
    unittest.main()

