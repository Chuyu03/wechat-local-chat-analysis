from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .config import (
    DEFAULT_LEFT_SPEAKER_THRESHOLD,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_RIGHT_SPEAKER_THRESHOLD,
)
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


CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value: Any) -> str:
    """Return a spreadsheet-inert text representation without changing JSONL data."""

    if value is None:
        text = ""
    elif isinstance(value, (dict, list, tuple)):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        text = str(value)
    candidate = text.lstrip(" ")
    if candidate.startswith(CSV_FORMULA_PREFIXES):
        return "'" + text
    return text


def infer_speaker(
    bbox: Any,
    image_width: float | int | None,
    *,
    left_threshold: float = DEFAULT_LEFT_SPEAKER_THRESHOLD,
    right_threshold: float = DEFAULT_RIGHT_SPEAKER_THRESHOLD,
) -> str:
    if not image_width or image_width <= 0 or not isinstance(bbox, (list, tuple)):
        return "unknown"
    x_values: list[float] = []
    for point in bbox:
        if isinstance(point, (list, tuple)) and point:
            try:
                x_values.append(float(point[0]))
            except (TypeError, ValueError):
                continue
    if not x_values:
        return "unknown"
    center_ratio = ((min(x_values) + max(x_values)) / 2.0) / float(image_width)
    if center_ratio <= left_threshold:
        return "other"
    if center_ratio >= right_threshold:
        return "self"
    return "unknown"


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def write_review_csv(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "message_id",
        "review_status",
        "review_reasons",
        "ocr_confidence",
        "speaker",
        "content_text",
        "source_image",
        "source_sha256",
        "bbox",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = {field: sanitize_csv_cell(record.get(field)) for field in fields}
            writer.writerow(row)


def _safe_confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    return confidence if 0.0 <= confidence <= 1.0 else None


def _validate_relative_source(workspace: Path, source_image: Any) -> str:
    if not isinstance(source_image, str) or not source_image:
        raise ValueError("OCR source_image must be a non-empty workspace-relative path")
    source = Path(source_image)
    if source.is_absolute():
        raise ValueError("OCR source_image must be workspace-relative")
    resolved = resolve_within(workspace, source)
    return relative_path(workspace, resolved)


def normalize_batch(
    batch_root: str | Path,
    workspace: str | Path | None = None,
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> Path:
    if not 0.0 <= float(min_confidence) <= 1.0:
        raise ValueError("min-confidence must be between 0 and 1")

    resolved_workspace = resolve_workspace(workspace)
    batch = resolve_batch_root(batch_root, resolved_workspace)
    manifest = load_manifest(batch, resolved_workspace)
    ocr_dir = resolve_within(resolved_workspace, batch / "ocr", must_exist=True)
    screenshots_dir = resolve_within(
        resolved_workspace, batch / "screenshots", must_exist=True
    )
    normalized_dir = resolve_within(resolved_workspace, batch / "normalized")
    messages_path = resolve_within(resolved_workspace, normalized_dir / "messages.jsonl")
    review_path = resolve_within(resolved_workspace, batch / "review.csv")

    records: list[dict[str, Any]] = []
    seen_screenshot_hashes: set[str] = set()
    duplicate_screenshots: list[dict[str, str]] = []

    for label, scoped_path in (
        ("OCR", ocr_dir),
        ("screenshots", screenshots_dir),
        ("normalized", normalized_dir),
        ("review CSV", review_path),
    ):
        try:
            scoped_path.relative_to(batch)
        except ValueError as exc:
            raise ValueError(f"Batch {label} path escapes the selected batch") from exc
    normalized_dir.mkdir(parents=True, exist_ok=True)

    ocr_manifest = manifest.get("ocr")
    if not isinstance(ocr_manifest, dict) or ocr_manifest.get("status") != "complete":
        raise RuntimeError("OCR must complete successfully before normalization")
    registered_images = ocr_manifest.get("images")
    if not isinstance(registered_images, list):
        raise ValueError("OCR manifest images must be a list")
    registered_ocr_entries: dict[Path, dict[str, Any]] = {}
    for entry in registered_images:
        if not isinstance(entry, dict):
            raise ValueError("OCR manifest image entry must be an object")
        ocr_json = entry.get("ocr_json")
        if not isinstance(ocr_json, str) or not ocr_json or Path(ocr_json).is_absolute():
            raise ValueError("OCR manifest ocr_json must be workspace-relative")
        safe_ocr_path = resolve_within(resolved_workspace, ocr_json, must_exist=True)
        try:
            safe_ocr_path.relative_to(ocr_dir)
        except ValueError as exc:
            raise ValueError(
                "Registered OCR JSON must stay inside the batch OCR directory"
            ) from exc
        previous = registered_ocr_entries.get(safe_ocr_path)
        if previous is not None and previous != entry:
            raise ValueError("Conflicting OCR manifest entries reference the same file")
        registered_ocr_entries[safe_ocr_path] = entry

    for safe_ocr_path, registered_entry in sorted(registered_ocr_entries.items()):
        expected_ocr_digest = str(registered_entry.get("ocr_json_sha256", "")).lower()
        if len(expected_ocr_digest) != 64 or sha256_file(safe_ocr_path) != expected_ocr_digest:
            raise ValueError(f"OCR JSON bytes do not match the manifest in {safe_ocr_path.name}")
        ocr_text_value = registered_entry.get("ocr_text")
        expected_text_digest = str(registered_entry.get("ocr_text_sha256", "")).lower()
        if not isinstance(ocr_text_value, str) or not ocr_text_value or Path(ocr_text_value).is_absolute():
            raise ValueError("OCR manifest ocr_text must be workspace-relative")
        safe_text_path = resolve_within(
            resolved_workspace, ocr_text_value, must_exist=True
        )
        ocr_text_dir = resolve_within(
            resolved_workspace, batch / "ocr_text", must_exist=True
        )
        try:
            safe_text_path.relative_to(ocr_text_dir)
        except ValueError as exc:
            raise ValueError("Registered OCR text must stay inside the batch OCR text directory") from exc
        if len(expected_text_digest) != 64 or sha256_file(safe_text_path) != expected_text_digest:
            raise ValueError(f"OCR text bytes do not match the manifest in {safe_ocr_path.name}")
        with safe_ocr_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("schema_version") != 1:
            raise ValueError(f"Unsupported OCR schema in {safe_ocr_path.name}")
        source_image = _validate_relative_source(
            resolved_workspace, payload.get("source_image")
        )
        source_path = resolve_within(
            resolved_workspace, source_image, must_exist=True
        )
        try:
            source_path.relative_to(screenshots_dir)
        except ValueError as exc:
            raise ValueError("OCR source image escapes the selected batch") from exc
        source_sha256 = str(payload.get("source_sha256", "")).lower()
        if len(source_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in source_sha256
        ):
            raise ValueError(f"Invalid source_sha256 in {safe_ocr_path.name}")
        if registered_entry.get("source_image") != source_image:
            raise ValueError(f"OCR source_image does not match the manifest in {safe_ocr_path.name}")
        if str(registered_entry.get("source_sha256", "")).lower() != source_sha256:
            raise ValueError(f"OCR source_sha256 does not match the manifest in {safe_ocr_path.name}")
        if sha256_file(source_path) != source_sha256:
            raise ValueError(f"Current screenshot bytes do not match OCR evidence in {safe_ocr_path.name}")
        if source_sha256 in seen_screenshot_hashes:
            duplicate_screenshots.append(
                {
                    "ocr_json": relative_path(resolved_workspace, safe_ocr_path),
                    "source_sha256": source_sha256,
                }
            )
            continue
        seen_screenshot_hashes.add(source_sha256)

        image_size = payload.get("image_size")
        image_width = image_size[0] if isinstance(image_size, list) and image_size else None
        items = payload.get("items")
        if not isinstance(items, list):
            raise ValueError(f"OCR items must be a list in {safe_ocr_path.name}")
        if registered_entry.get("item_count") != len(items):
            raise ValueError(f"OCR item_count does not match the manifest in {safe_ocr_path.name}")
        if registered_entry.get("actual_device") != payload.get("actual_device"):
            raise ValueError(f"OCR actual_device does not match the manifest in {safe_ocr_path.name}")

        for fallback_index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"OCR item must be an object in {safe_ocr_path.name}")
            try:
                item_index = int(item.get("index", fallback_index))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid OCR item index in {safe_ocr_path.name}") from exc
            raw_text = item.get("text", "")
            content_text = raw_text if isinstance(raw_text, str) else str(raw_text)
            confidence = _safe_confidence(item.get("confidence"))
            bbox = item.get("bbox")
            speaker = infer_speaker(bbox, image_width)
            reasons: list[str] = []
            if confidence is None or confidence < float(min_confidence):
                reasons.append("low_or_missing_ocr_confidence")
            if speaker == "unknown":
                reasons.append("uncertain_speaker")
            if not content_text.strip():
                reasons.append("empty_or_non_text_item")
            record = {
                "message_id": (
                    f"{manifest['batch_id']}-{source_sha256[:12]}-{item_index:04d}"
                ),
                "contact_slug": manifest["contact_slug"],
                "batch_id": manifest["batch_id"],
                "start_date": manifest["start_date"],
                "end_date": manifest["end_date"],
                "speaker": speaker,
                "timestamp_text": "",
                "content_text": content_text,
                "content_type": "text" if content_text.strip() else "unknown",
                "source_image": source_image,
                "source_sha256": source_sha256,
                "bbox": bbox,
                "ocr_confidence": confidence,
                "review_status": "needs_review" if reasons else "unreviewed",
                "review_reasons": reasons,
                "created_at": now_iso(),
            }
            records.append(record)

    text_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        text = record["content_text"].strip()
        if text:
            text_groups[text].append(record)
    for group in text_groups.values():
        source_hashes = {record["source_sha256"] for record in group}
        if len(group) > 1 and len(source_hashes) > 1:
            for record in group:
                if "possible_scroll_overlap" not in record["review_reasons"]:
                    record["review_reasons"].append("possible_scroll_overlap")
                record["review_status"] = "needs_review"

    write_jsonl(messages_path, records)
    write_review_csv(
        review_path,
        (record for record in records if record["review_status"] == "needs_review"),
    )
    messages_sha256 = sha256_file(messages_path)
    review_csv_sha256 = sha256_file(review_path)
    manifest["normalize"] = {
        "status": "complete",
        "min_confidence": float(min_confidence),
        "record_count": len(records),
        "review_count": sum(
            record["review_status"] == "needs_review" for record in records
        ),
        "duplicate_screenshots_skipped": duplicate_screenshots,
        "messages_jsonl": relative_path(resolved_workspace, messages_path),
        "messages_jsonl_sha256": messages_sha256,
        "review_csv": relative_path(resolved_workspace, review_path),
        "review_csv_sha256": review_csv_sha256,
        "finished_at": now_iso(),
    }
    save_manifest(batch, resolved_workspace, manifest)
    return messages_path
