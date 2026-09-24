from __future__ import annotations

import ctypes
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .config import (
    DEFAULT_CAPTURE_COUNT,
    DEFAULT_DELAY_SECONDS,
    DEFAULT_PRE_CAPTURE_DELAY_SECONDS,
    DEFAULT_SCROLL_CLICKS,
)


DEFAULT_WECHAT_PROCESS_NAMES = ("WeChat.exe", "Weixin.exe")
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


@dataclass(frozen=True)
class ForegroundWindowIdentity:
    hwnd: int
    process_id: int
    process_name: str


def get_foreground_window_identity() -> ForegroundWindowIdentity:
    if os.name != "nt":
        raise RuntimeError("Foreground-window binding is supported on Windows only")
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        raise RuntimeError("No foreground window is available for capture binding")
    process_id = wintypes.DWORD()
    if not user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id)) or not process_id.value:
        raise OSError(ctypes.get_last_error(), "Could not resolve foreground process")
    process_handle = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, process_id.value
    )
    if not process_handle:
        raise OSError(ctypes.get_last_error(), "Could not inspect foreground process")
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(
            process_handle, 0, buffer, ctypes.byref(size)
        ):
            raise OSError(ctypes.get_last_error(), "Could not read foreground process name")
        process_name = Path(buffer.value).name
    finally:
        kernel32.CloseHandle(process_handle)
    if not process_name:
        raise RuntimeError("Foreground process name is empty")
    return ForegroundWindowIdentity(int(hwnd), int(process_id.value), process_name)


def validate_foreground_window(
    identity: ForegroundWindowIdentity,
    expected_process_names: tuple[str, ...],
) -> None:
    expected = {name.casefold() for name in expected_process_names if name.strip()}
    if not expected:
        raise ValueError("At least one expected process name is required")
    if identity.process_name.casefold() not in expected:
        raise RuntimeError(
            "Foreground process does not match an approved official WeChat process name"
        )


def require_same_foreground_window(
    bound: ForegroundWindowIdentity,
    probe: Callable[[], ForegroundWindowIdentity],
) -> None:
    current = probe()
    if current != bound:
        raise RuntimeError("Foreground window changed during capture; batch interrupted")
from .paths import (
    load_manifest,
    now_iso,
    relative_path,
    resolve_batch_root,
    resolve_within,
    resolve_workspace,
    save_manifest,
    sha256_file,
)


def parse_region(value: str) -> tuple[int, int, int, int]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("region must be x,y,width,height")
    try:
        x, y, width, height = (int(part) for part in parts)
    except ValueError as exc:
        raise ValueError("region values must be integers") from exc
    if width <= 0 or height <= 0:
        raise ValueError("region width and height must be positive")
    return x, y, width, height


def capture_batch(
    *,
    workspace: str | Path | None,
    batch_root: str | Path,
    region: tuple[int, int, int, int],
    count: int = DEFAULT_CAPTURE_COUNT,
    scroll_clicks: int = DEFAULT_SCROLL_CLICKS,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    pre_capture_delay_seconds: float = DEFAULT_PRE_CAPTURE_DELAY_SECONDS,
    expected_process_names: tuple[str, ...] = DEFAULT_WECHAT_PROCESS_NAMES,
    window_probe: Callable[[], ForegroundWindowIdentity] | None = None,
) -> Path:
    if count <= 0 or count > 10_000:
        raise ValueError("count must be between 1 and 10000")
    if delay_seconds < 0 or pre_capture_delay_seconds < 0:
        raise ValueError("capture delays must not be negative")
    if len(region) != 4 or region[2] <= 0 or region[3] <= 0:
        raise ValueError("region width and height must be positive")

    try:
        import pyautogui  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "Capture support is optional. Install the 'capture' extra locally before use."
        ) from exc
    pyautogui.FAILSAFE = True

    resolved_workspace = resolve_workspace(workspace)
    batch = resolve_batch_root(batch_root, resolved_workspace)
    screenshots_dir = resolve_within(
        resolved_workspace, batch / "screenshots", must_exist=True
    )
    try:
        screenshots_dir.relative_to(batch)
    except ValueError as exc:
        raise ValueError("Batch screenshots directory escapes the selected batch") from exc
    manifest = load_manifest(batch, resolved_workspace)
    capture: dict[str, Any] = manifest.setdefault("capture", {})
    screenshots = capture.setdefault("screenshots", [])
    capture.update(
        {
            "status": "running",
            "region": list(region),
            "count_requested": count,
            "scroll_clicks": scroll_clicks,
            "delay_seconds": delay_seconds,
            "pre_capture_delay_seconds": pre_capture_delay_seconds,
            "started_at": now_iso(),
        }
    )
    save_manifest(batch, resolved_workspace, manifest)

    if pre_capture_delay_seconds:
        time.sleep(pre_capture_delay_seconds)

    probe = window_probe or get_foreground_window_identity
    bound_window = probe()
    validate_foreground_window(bound_window, expected_process_names)
    capture["bound_window"] = {
        "hwnd": f"0x{bound_window.hwnd:x}",
        "process_id": bound_window.process_id,
        "process_name": bound_window.process_name,
    }
    save_manifest(batch, resolved_workspace, manifest)

    existing_indexes = {
        int(item["index"])
        for item in screenshots
        if isinstance(item, dict) and str(item.get("index", "")).isdigit()
    }
    next_index = max(existing_indexes, default=0) + 1
    known_hashes = {
        str(item.get("sha256")): str(item.get("file"))
        for item in screenshots
        if isinstance(item, dict) and item.get("sha256") and item.get("file")
    }

    try:
        for offset in range(count):
            require_same_foreground_window(bound_window, probe)
            index = next_index + offset
            target = resolve_within(
                resolved_workspace, screenshots_dir / f"{index:06d}.png"
            )
            try:
                target.relative_to(screenshots_dir)
            except ValueError as exc:
                raise ValueError("Screenshot output escapes the selected batch") from exc
            if target.exists() or target.is_symlink():
                raise FileExistsError(f"Refusing to overwrite screenshot: {target.name}")
            image = pyautogui.screenshot(region=region)
            require_same_foreground_window(bound_window, probe)
            image.save(target)
            digest = sha256_file(target)
            item: dict[str, Any] = {
                "index": index,
                "file": relative_path(resolved_workspace, target),
                "sha256": digest,
                "captured_at": now_iso(),
            }
            if digest in known_hashes:
                item["duplicate_of"] = known_hashes[digest]
            else:
                known_hashes[digest] = item["file"]
            screenshots.append(item)
            save_manifest(batch, resolved_workspace, manifest)

            if offset < count - 1 and scroll_clicks:
                require_same_foreground_window(bound_window, probe)
                pyautogui.moveTo(region[0] + region[2] // 2, region[1] + region[3] // 2)
                pyautogui.scroll(scroll_clicks)
                require_same_foreground_window(bound_window, probe)
                if delay_seconds:
                    time.sleep(delay_seconds)
    except BaseException:
        capture["status"] = "interrupted"
        capture["finished_at"] = now_iso()
        save_manifest(batch, resolved_workspace, manifest)
        raise

    capture["status"] = "complete"
    capture["finished_at"] = now_iso()
    capture["screenshots_captured"] = len(screenshots)
    capture["unique_screenshot_hashes"] = len(known_hashes)
    save_manifest(batch, resolved_workspace, manifest)
    return batch


def region_to_text(region: tuple[int, int, int, int]) -> str:
    return ",".join(str(part) for part in region)
