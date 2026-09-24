from __future__ import annotations

import importlib.metadata
import json
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .config import SUPPORTED_IMAGE_SUFFIXES
from .paths import (
    load_manifest,
    now_iso,
    relative_path,
    resolve_batch_root,
    resolve_within,
    resolve_workspace,
    save_manifest,
    sha256_file,
    write_json,
)


VALID_DEVICE_REQUESTS = {"auto", "cpu", "gpu:0"}


class EvidenceChangedError(RuntimeError):
    """Raised when screenshot bytes change during the OCR evidence step."""


def validate_device_request(requested: str) -> str:
    normalized = str(requested).strip().lower()
    if normalized not in VALID_DEVICE_REQUESTS:
        raise ValueError("device must be one of: auto, cpu, gpu:0")
    return normalized


def paddle_cuda_available(paddle_module: Any) -> bool:
    try:
        return bool(paddle_module.device.is_compiled_with_cuda())
    except Exception:
        return False


def resolve_requested_device(requested: str, paddle_module: Any | None = None) -> str:
    """Resolve auto to the exact PaddleOCR 3.x device string."""

    normalized = validate_device_request(requested)
    if normalized != "auto":
        return normalized
    if paddle_module is None:
        try:
            import paddle as paddle_module  # type: ignore[import-not-found,no-redef]
        except Exception:
            return "cpu"
    return "gpu:0" if paddle_cuda_available(paddle_module) else "cpu"


# Compatibility name retained for callers of the private prototype.
resolve_paddle_device = resolve_requested_device


def make_paddle_ocr(paddle_ocr_cls: Any, device: str, lang: str = "ch") -> Any:
    """Construct PaddleOCR 3.x without masking an unsupported device."""

    return paddle_ocr_cls(
        lang=lang,
        device=device,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


def _distribution_version(*names: str) -> str | None:
    for name in names:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return None


def _runtime_evidence(paddle_module: Any) -> dict[str, Any]:
    return {
        "framework": {
            "name": "PaddlePaddle",
            "version": str(getattr(paddle_module, "__version__", "unknown")),
            "cuda_compiled": paddle_cuda_available(paddle_module),
        },
        "package_versions": {
            "paddleocr": _distribution_version("paddleocr"),
            "paddlepaddle": _distribution_version("paddlepaddle", "paddlepaddle-gpu"),
            "python": sys.version.split()[0],
        },
    }


def _safe_failure_reason(prefix: str, exc: BaseException) -> str:
    return f"{prefix} ({type(exc).__name__})"


def _load_optional_runtime() -> tuple[Any, Any, Any]:
    os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")
    try:
        from PIL import Image  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("OCR image metadata requires the local 'ocr' extra.") from exc
    try:
        import paddle  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "PaddlePaddle is not installed. Select and install a CPU or GPU build from "
            "the official PaddlePaddle installation guide."
        ) from exc
    try:
        from paddleocr import PaddleOCR  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("PaddleOCR 3.x is not installed. Install the local 'ocr' extra.") from exc
    return Image, paddle, PaddleOCR


def _collect_registered_images(
    capture_state: Any,
    screenshots_dir: Path,
    workspace: Path,
    limit: int | None,
) -> tuple[list[tuple[Path, str]], list[dict[str, str]], list[str]]:
    if not isinstance(capture_state, dict) or capture_state.get("status") != "complete":
        raise RuntimeError("Capture must complete successfully before OCR")
    registered = capture_state.get("screenshots")
    if not isinstance(registered, list):
        raise ValueError("Capture manifest screenshots must be a list")
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")

    registered_paths: set[str] = set()
    seen_hashes: dict[str, str] = {}
    unique: list[tuple[Path, str]] = []
    duplicates: list[dict[str, str]] = []
    for entry in registered:
        if not isinstance(entry, dict):
            raise ValueError("Capture screenshot entry must be an object")
        file_value = entry.get("file")
        expected_digest = str(entry.get("sha256", "")).lower()
        if not isinstance(file_value, str) or not file_value or Path(file_value).is_absolute():
            raise ValueError("Capture screenshot file must be workspace-relative")
        if len(expected_digest) != 64 or any(
            character not in "0123456789abcdef" for character in expected_digest
        ):
            raise ValueError("Capture screenshot sha256 is invalid")
        safe_path = resolve_within(workspace, file_value, must_exist=True)
        try:
            safe_path.relative_to(screenshots_dir)
        except ValueError as exc:
            raise ValueError("Screenshot path escapes the selected batch") from exc
        if not safe_path.is_file() or safe_path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
            raise ValueError("Registered screenshot is not a supported image file")
        relative = relative_path(workspace, safe_path)
        if relative in registered_paths:
            raise ValueError("Capture manifest registers the same screenshot path more than once")
        registered_paths.add(relative)
        current_digest = sha256_file(safe_path)
        if current_digest != expected_digest:
            raise EvidenceChangedError("Registered screenshot changed after capture")
        if expected_digest in seen_hashes:
            duplicates.append(
                {
                    "file": relative,
                    "sha256": expected_digest,
                    "duplicate_of": seen_hashes[expected_digest],
                }
            )
            continue
        seen_hashes[expected_digest] = relative
        unique.append((safe_path, expected_digest))

    unregistered = sorted(
        relative_path(workspace, child)
        for child in screenshots_dir.iterdir()
        if child.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
        and relative_path(workspace, child) not in registered_paths
    )
    selected = unique[:limit] if limit is not None else unique
    return selected, duplicates, unregistered


def ocr_batch(
    batch_root: str | Path,
    workspace: str | Path | None = None,
    *,
    device: str = "auto",
    lang: str = "ch",
    limit: int | None = None,
    capture_coverage_acknowledged: bool = False,
    paddle_ocr_cls: Any | None = None,
    paddle_module: Any | None = None,
    image_module: Any | None = None,
) -> Path:
    if not capture_coverage_acknowledged:
        raise ValueError(
            "OCR requires explicit acknowledgement that capture coverage was reviewed"
        )
    requested = validate_device_request(device)
    resolved_workspace = resolve_workspace(workspace)
    batch = resolve_batch_root(batch_root, resolved_workspace)
    screenshots_dir = resolve_within(
        resolved_workspace, batch / "screenshots", must_exist=True
    )
    ocr_dir = resolve_within(resolved_workspace, batch / "ocr")
    text_dir = resolve_within(resolved_workspace, batch / "ocr_text")
    for label, scoped_path in (("screenshots", screenshots_dir), ("ocr", ocr_dir), ("ocr_text", text_dir)):
        try:
            scoped_path.relative_to(batch)
        except ValueError as exc:
            raise ValueError(f"Batch {label} directory escapes the selected batch") from exc
    ocr_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(batch, resolved_workspace)
    capture_state = manifest.get("capture")
    images, duplicates, unregistered = _collect_registered_images(
        capture_state, screenshots_dir, resolved_workspace, limit
    )
    if not images:
        manifest["ocr"] = {
            "status": "failed",
            "requested_device": requested,
            "actual_device": None,
            "actual_devices": [],
            "failure": "No unique screenshots are available for OCR",
            "finished_at": now_iso(),
        }
        save_manifest(batch, resolved_workspace, manifest)
        raise RuntimeError("No unique screenshots are available for OCR")

    if paddle_ocr_cls is None or paddle_module is None or image_module is None:
        loaded_image, loaded_paddle, loaded_cls = _load_optional_runtime()
        image_module = image_module or loaded_image
        paddle_module = paddle_module or loaded_paddle
        paddle_ocr_cls = paddle_ocr_cls or loaded_cls

    attempted_device = resolve_requested_device(requested, paddle_module)
    evidence = _runtime_evidence(paddle_module)
    ocr_manifest: dict[str, Any] = {
        "status": "running",
        "engine": "PaddleOCR 3.x",
        "language": lang,
        "requested_device": requested,
        "attempted_device": attempted_device,
        "actual_device": None,
        "actual_devices": [],
        "initialized_devices": [],
        "fallback_reason": None,
        "device_evidence": None,
        "started_at": now_iso(),
        "images_requested": len(images) + len(duplicates),
        "images_unique_by_sha256": len(images),
        "duplicates_skipped": duplicates,
        "unregistered_files_ignored": unregistered,
        "images": [],
        **evidence,
    }
    manifest["ocr"] = ocr_manifest
    save_manifest(batch, resolved_workspace, manifest)

    if requested == "gpu:0" and not paddle_cuda_available(paddle_module):
        ocr_manifest["status"] = "failed"
        ocr_manifest["failure"] = "gpu:0 requested but PaddlePaddle has no CUDA support"
        ocr_manifest["finished_at"] = now_iso()
        save_manifest(batch, resolved_workspace, manifest)
        raise RuntimeError("gpu:0 was requested, but PaddlePaddle reports no CUDA support")

    active_device = attempted_device
    initialized_devices: list[str] = []
    try:
        engine = make_paddle_ocr(paddle_ocr_cls, active_device, lang)
        initialized_devices.append(active_device)
    except Exception as exc:
        if requested == "auto" and active_device == "gpu:0":
            ocr_manifest["fallback_reason"] = _safe_failure_reason(
                "GPU initialization failed; retried on CPU", exc
            )
            active_device = "cpu"
            try:
                engine = make_paddle_ocr(paddle_ocr_cls, active_device, lang)
                initialized_devices.append(active_device)
            except Exception as cpu_exc:
                ocr_manifest["status"] = "failed"
                ocr_manifest["failure"] = _safe_failure_reason(
                    "CPU initialization failed", cpu_exc
                )
                ocr_manifest["finished_at"] = now_iso()
                save_manifest(batch, resolved_workspace, manifest)
                raise RuntimeError("PaddleOCR could not initialize on GPU or CPU") from cpu_exc
        else:
            ocr_manifest["status"] = "failed"
            ocr_manifest["failure"] = _safe_failure_reason(
                f"PaddleOCR initialization failed on {active_device}", exc
            )
            ocr_manifest["finished_at"] = now_iso()
            save_manifest(batch, resolved_workspace, manifest)
            raise RuntimeError(f"PaddleOCR could not initialize on {active_device}") from exc

    actual_devices: list[str] = []
    ocr_manifest["initialized_devices"] = initialized_devices.copy()
    ocr_manifest["device_evidence"] = (
        f"PaddleOCR initialized successfully with device={active_device}; inference pending"
    )
    save_manifest(batch, resolved_workspace, manifest)

    try:
        for sequence, (image_path, source_digest) in enumerate(images, start=1):
            try:
                items = run_verified_image(engine, image_path, source_digest)
            except Exception as exc:
                if isinstance(exc, EvidenceChangedError):
                    raise
                if requested == "auto" and active_device == "gpu:0":
                    ocr_manifest["fallback_reason"] = _safe_failure_reason(
                        "GPU inference failed; remaining work retried on CPU", exc
                    )
                    active_device = "cpu"
                    try:
                        engine = make_paddle_ocr(paddle_ocr_cls, active_device, lang)
                        if active_device not in initialized_devices:
                            initialized_devices.append(active_device)
                        ocr_manifest["initialized_devices"] = initialized_devices.copy()
                        items = run_verified_image(engine, image_path, source_digest)
                    except Exception as cpu_exc:
                        ocr_manifest["status"] = "failed"
                        ocr_manifest["failure"] = _safe_failure_reason(
                            "CPU fallback inference failed", cpu_exc
                        )
                        ocr_manifest["finished_at"] = now_iso()
                        save_manifest(batch, resolved_workspace, manifest)
                        raise RuntimeError("PaddleOCR CPU fallback inference failed") from cpu_exc
                else:
                    ocr_manifest["status"] = "failed"
                    ocr_manifest["failure"] = _safe_failure_reason(
                        f"Inference failed on {active_device}", exc
                    )
                    ocr_manifest["finished_at"] = now_iso()
                    save_manifest(batch, resolved_workspace, manifest)
                    raise RuntimeError(f"PaddleOCR inference failed on {active_device}") from exc

            if active_device not in actual_devices:
                actual_devices.append(active_device)
            ocr_manifest["actual_devices"] = actual_devices.copy()
            ocr_manifest["actual_device"] = (
                "mixed" if len(actual_devices) > 1 else actual_devices[0]
            )
            ocr_manifest["device_evidence"] = (
                "Successful OCR inference completed with device="
                + ocr_manifest["actual_device"]
            )
            with image_module.open(image_path) as image:
                image_size = [int(image.size[0]), int(image.size[1])]
            source_relative = relative_path(resolved_workspace, image_path)
            base_name = f"{sequence:06d}-{source_digest[:12]}"
            json_target = resolve_within(resolved_workspace, ocr_dir / f"{base_name}.json")
            text_target = resolve_within(resolved_workspace, text_dir / f"{base_name}.txt")
            try:
                json_target.relative_to(ocr_dir)
                text_target.relative_to(text_dir)
            except ValueError as exc:
                raise ValueError("OCR output path escapes the selected batch") from exc
            payload = {
                "schema_version": 1,
                "source_image": source_relative,
                "source_sha256": source_digest,
                "image_size": image_size,
                "engine": "PaddleOCR 3.x",
                "actual_device": active_device,
                "items": items,
                "created_at": now_iso(),
            }
            write_json(json_target, payload)
            text_target.write_text(
                "\n".join(str(item.get("text", "")) for item in items),
                encoding="utf-8",
                newline="\n",
            )
            ocr_json_sha256 = sha256_file(json_target)
            ocr_text_sha256 = sha256_file(text_target)
            ocr_manifest["images"].append(
                {
                    "source_image": source_relative,
                    "source_sha256": source_digest,
                    "ocr_json": relative_path(resolved_workspace, json_target),
                    "ocr_json_sha256": ocr_json_sha256,
                    "ocr_text": relative_path(resolved_workspace, text_target),
                    "ocr_text_sha256": ocr_text_sha256,
                    "actual_device": active_device,
                    "item_count": len(items),
                }
            )
            save_manifest(batch, resolved_workspace, manifest)
    except BaseException as exc:
        if ocr_manifest.get("status") != "failed":
            ocr_manifest["status"] = "failed"
            ocr_manifest["failure"] = _safe_failure_reason("OCR processing failed", exc)
            ocr_manifest["device_evidence"] = (
                "Batch failed; any recorded actual_device applies only to inference steps "
                "completed before the failure"
            )
            ocr_manifest["finished_at"] = now_iso()
            save_manifest(batch, resolved_workspace, manifest)
        raise

    ocr_manifest["status"] = "complete"
    ocr_manifest["finished_at"] = now_iso()
    save_manifest(batch, resolved_workspace, manifest)
    return batch


def run_single_image(engine: Any, image_path: Path) -> Any:
    if hasattr(engine, "predict"):
        return engine.predict(str(image_path))
    if hasattr(engine, "ocr"):
        return engine.ocr(str(image_path), cls=False)
    raise RuntimeError("Unsupported PaddleOCR object: no predict() or ocr() method")


def run_verified_image(
    engine: Any,
    image_path: Path,
    expected_sha256: str,
) -> list[dict[str, Any]]:
    if sha256_file(image_path) != expected_sha256:
        raise EvidenceChangedError("Screenshot changed before OCR inference")
    items = normalize_paddle_result(run_single_image(engine, image_path))
    if sha256_file(image_path) != expected_sha256:
        raise EvidenceChangedError("Screenshot changed during OCR inference")
    return items


def normalize_paddle_result(result: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    _append_items(result, items)
    for index, item in enumerate(items, start=1):
        item["index"] = index
        item.setdefault("text", "")
        item.setdefault("confidence", None)
        item.setdefault("bbox", None)
    return items


def _append_items(value: Any, items: list[dict[str, Any]]) -> None:
    if value is None or isinstance(value, (str, bytes, int, float, bool)):
        return
    if isinstance(value, dict):
        _append_items_from_dict(value, items)
        return
    if isinstance(value, (list, tuple)):
        if _append_legacy_line(value, items):
            return
        for child in value:
            _append_items(child, items)
        return
    if isinstance(value, Iterable):
        for child in value:
            _append_items(child, items)
        return
    for attribute in ("json", "to_dict"):
        if not hasattr(value, attribute):
            continue
        try:
            converted = getattr(value, attribute)
            converted = converted() if callable(converted) else converted
            if isinstance(converted, str):
                converted = json.loads(converted)
            _append_items(converted, items)
            return
        except Exception:
            continue
    if hasattr(value, "__dict__"):
        _append_items(vars(value), items)


def _as_list(value: Any) -> list[Any] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if hasattr(value, "tolist"):
        converted = value.tolist()
        return converted if isinstance(converted, list) else [converted]
    return None


def _first_list(data: dict[str, Any], keys: tuple[str, ...]) -> list[Any] | None:
    for key in keys:
        converted = _as_list(data.get(key))
        if converted is not None:
            return converted
    return None


def _append_items_from_dict(value: dict[str, Any], items: list[dict[str, Any]]) -> None:
    data = value.get("res", value)
    if not isinstance(data, dict):
        _append_items(data, items)
        return
    texts = _first_list(data, ("rec_texts", "texts"))
    scores = _first_list(data, ("rec_scores", "scores", "confidence"))
    boxes = _first_list(data, ("rec_polys", "dt_polys", "text_polys", "boxes", "bbox"))
    if texts is not None:
        for index, text in enumerate(texts):
            items.append(
                {
                    "index": len(items) + 1,
                    "text": str(text),
                    "confidence": _safe_float(_get_index(scores, index)),
                    "bbox": _to_jsonable(_get_index(boxes, index)),
                }
            )
        return
    if isinstance(data.get("text"), str):
        items.append(
            {
                "index": len(items) + 1,
                "text": data["text"],
                "confidence": _safe_float(data.get("confidence")),
                "bbox": _to_jsonable(data.get("bbox")),
            }
        )
        return
    for child in data.values():
        if child is not data:
            _append_items(child, items)


def _append_legacy_line(value: list[Any] | tuple[Any, ...], items: list[dict[str, Any]]) -> bool:
    if len(value) != 2:
        return False
    bbox, text_score = value
    if not isinstance(text_score, (list, tuple)) or not text_score:
        return False
    if not isinstance(text_score[0], str):
        return False
    items.append(
        {
            "index": len(items) + 1,
            "text": text_score[0],
            "confidence": _safe_float(text_score[1] if len(text_score) > 1 else None),
            "bbox": _to_jsonable(bbox),
        }
    )
    return True


def _get_index(values: list[Any] | None, index: int) -> Any:
    if values is None or index >= len(values):
        return None
    return values[index]


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _to_jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(child) for child in value]
    if hasattr(value, "tolist"):
        return _to_jsonable(value.tolist())
    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)


# Public aliases make low-level adapters easy to unit-test without PaddleOCR installed.
append_items_from_any = _append_items
safe_float = _safe_float
to_jsonable = _to_jsonable
