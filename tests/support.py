from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


# A generated-at-test-time 1 x 1 PNG. It contains no captured or personal data.
SYNTHETIC_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl7T9sAAAAASUVORK5CYII="
)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def register_synthetic_capture(*, workspace: Path, batch_paths: Any) -> None:
    manifest = json.loads(batch_paths.manifest.read_text(encoding="utf-8"))
    screenshots = []
    for index, screenshot in enumerate(sorted(batch_paths.screenshots.glob("*")), start=1):
        if not screenshot.is_file():
            continue
        screenshots.append(
            {
                "index": index,
                "file": screenshot.resolve().relative_to(workspace.resolve()).as_posix(),
                "sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(),
                "captured_at": "2040-01-02T00:00:00+00:00",
            }
        )
    manifest["capture"] = {
        "status": "complete",
        "screenshots": screenshots,
        "finished_at": "2040-01-02T00:00:00+00:00",
    }
    write_json(batch_paths.manifest, manifest)


def add_synthetic_ocr(
    *,
    workspace: Path,
    batch_paths: Any,
    stem: str,
    text: str,
    confidence: float | None,
    source_sha256: str | None = None,
    bbox: list[list[int]] | None = None,
) -> Path:
    """Create one synthetic screenshot file and its normalized OCR payload."""

    screenshot = batch_paths.screenshots / f"{stem}.png"
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    seed = (source_sha256 or stem).encode("ascii")
    screenshot_bytes = SYNTHETIC_PNG + seed
    screenshot.write_bytes(screenshot_bytes)
    digest = hashlib.sha256(screenshot_bytes).hexdigest()
    relative_source = screenshot.resolve().relative_to(workspace.resolve()).as_posix()
    payload = {
        "schema_version": 1,
        "synthetic": True,
        "source_image": relative_source,
        "source_sha256": digest,
        "image_size": [1000, 800],
        "engine": "paddle",
        "actual_device": "synthetic",
        "items": [
            {
                "index": 1,
                "text": text,
                "confidence": confidence,
                "bbox": bbox or [[50, 100], [250, 100], [250, 140], [50, 140]],
            }
        ],
    }
    target = batch_paths.ocr / f"{stem}.json"
    write_json(target, payload)
    text_target = batch_paths.ocr_text / f"{stem}.txt"
    text_target.write_text(text + "\n", encoding="utf-8", newline="\n")
    manifest = json.loads(batch_paths.manifest.read_text(encoding="utf-8"))
    manifest.setdefault("ocr", {})["status"] = "complete"
    manifest["ocr"].setdefault("images", []).append(
        {
            "source_image": relative_source,
            "source_sha256": digest,
            "ocr_json": target.resolve().relative_to(workspace.resolve()).as_posix(),
            "ocr_json_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "ocr_text": text_target.resolve().relative_to(workspace.resolve()).as_posix(),
            "ocr_text_sha256": hashlib.sha256(text_target.read_bytes()).hexdigest(),
            "item_count": 1,
            "actual_device": "synthetic",
        }
    )
    write_json(batch_paths.manifest, manifest)
    return target
