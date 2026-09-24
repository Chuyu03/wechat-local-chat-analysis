from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from support import REPOSITORY_ROOT  # noqa: F401 - installs src on sys.path
from wechat_analyse.capture import (
    ForegroundWindowIdentity,
    capture_batch,
    validate_foreground_window,
)
from wechat_analyse.paths import init_batch


class _FakeImage:
    def __init__(self) -> None:
        self.saved = False

    def save(self, path: Path) -> None:
        self.saved = True
        Path(path).write_bytes(b"synthetic captured pixels")


class CaptureWindowBindingTests(unittest.TestCase):
    def test_rejects_unapproved_foreground_process(self) -> None:
        identity = ForegroundWindowIdentity(100, 200, "unrelated.exe")
        with self.assertRaises(RuntimeError):
            validate_foreground_window(identity, ("WeChat.exe", "Weixin.exe"))

    def test_successful_capture_records_bound_window(self) -> None:
        identity = ForegroundWindowIdentity(100, 200, "WeChat.exe")
        fake_image = _FakeImage()
        fake_pyautogui = types.SimpleNamespace(
            FAILSAFE=False,
            screenshot=lambda region: fake_image,
            moveTo=lambda x, y: None,
            scroll=lambda clicks: None,
        )
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = init_batch(
                workspace,
                "Synthetic Contact",
                "2040-01-01",
                "2040-01-02",
                batch_id="synthetic-capture-window",
            )
            with patch.dict(sys.modules, {"pyautogui": fake_pyautogui}):
                capture_batch(
                    workspace=workspace,
                    batch_root=paths.root,
                    region=(10, 10, 100, 100),
                    count=1,
                    pre_capture_delay_seconds=0,
                    window_probe=lambda: identity,
                )
            manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))

        self.assertTrue(fake_image.saved)
        self.assertEqual("complete", manifest["capture"]["status"])
        self.assertEqual("WeChat.exe", manifest["capture"]["bound_window"]["process_name"])
        self.assertEqual(1, len(manifest["capture"]["screenshots"]))

    def test_window_change_interrupts_before_screenshot_is_saved(self) -> None:
        bound = ForegroundWindowIdentity(100, 200, "WeChat.exe")
        changed = ForegroundWindowIdentity(101, 201, "unrelated.exe")
        sequence = iter((bound, bound, changed))
        fake_image = _FakeImage()
        fake_pyautogui = types.SimpleNamespace(
            FAILSAFE=False,
            screenshot=lambda region: fake_image,
            moveTo=lambda x, y: None,
            scroll=lambda clicks: None,
        )
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = init_batch(
                workspace,
                "Synthetic Contact",
                "2040-01-01",
                "2040-01-02",
                batch_id="synthetic-capture-interrupted",
            )
            with patch.dict(sys.modules, {"pyautogui": fake_pyautogui}):
                with self.assertRaises(RuntimeError):
                    capture_batch(
                        workspace=workspace,
                        batch_root=paths.root,
                        region=(10, 10, 100, 100),
                        count=1,
                        pre_capture_delay_seconds=0,
                        window_probe=lambda: next(sequence),
                    )
            manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))

        self.assertFalse(fake_image.saved)
        self.assertEqual("interrupted", manifest["capture"]["status"])
        self.assertEqual([], manifest["capture"]["screenshots"])


if __name__ == "__main__":
    unittest.main()
