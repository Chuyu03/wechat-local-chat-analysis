from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from .paths import resolve_workspace


def module_exists(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def detect_nvidia_gpu() -> str:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return "not detected"
    try:
        result = subprocess.run(
            [executable, "--query-gpu=name", "--format=csv,noheader"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"detected but unavailable ({type(exc).__name__})"
    return result.stdout.strip() or "detected"


def detect_paddle_cuda_support() -> str:
    if not module_exists("paddle"):
        return "paddle not installed"
    try:
        import paddle  # type: ignore[import-not-found]

        return str(bool(paddle.device.is_compiled_with_cuda()))
    except Exception as exc:  # third-party import/runtime failures vary
        return f"unknown ({type(exc).__name__})"


def run_doctor(workspace: str | Path | None = None) -> int:
    resolved_workspace = resolve_workspace(workspace)
    python_supported = sys.version_info[:2] in {(3, 11), (3, 12)}
    windows_supported = platform.system() == "Windows"
    print(f"Workspace: {resolved_workspace}")
    print(f"Platform: {platform.platform()}")
    print(f"Python: {platform.python_version()}")
    print(f"Supported platform: {windows_supported}")
    print(f"Supported Python: {python_supported}")
    print(f"NVIDIA GPU: {detect_nvidia_gpu()}")
    print(f"Paddle CUDA support: {detect_paddle_cuda_support()}")
    print("")
    checks = (
        ("Pillow", "PIL", "image metadata and capture output"),
        ("PyAutoGUI", "pyautogui", "optional screen capture"),
        ("PaddleOCR", "paddleocr", "optional local OCR"),
        ("PaddlePaddle", "paddle", "install separately using the official selector"),
    )
    for label, module, purpose in checks:
        marker = "OK" if module_exists(module) else "OPTIONAL-MISSING"
        print(f"[{marker}] {label}: {purpose}")
    if not windows_supported or not python_supported:
        print("")
        print("This v0.1.0 release supports Windows 10/11 and Python 3.11/3.12 only.")
        return 1
    return 0
