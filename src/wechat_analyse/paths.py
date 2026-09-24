from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .config import APP_NAME, SCHEMA_VERSION


IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class PathSafetyError(ValueError):
    """Raised when a user-controlled path would leave the selected workspace."""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def default_workspace() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_NAME
    return Path.home() / "AppData" / "Local" / APP_NAME


def installed_source_roots() -> tuple[Path, ...]:
    """Return local code roots that must never receive private runtime data."""

    package_root = Path(__file__).resolve().parent
    roots = [package_root]
    for parent in package_root.parents:
        if (parent / "SKILL.md").is_file() and (parent / "pyproject.toml").is_file():
            roots.append(parent.resolve())
            break
    return tuple(dict.fromkeys(roots))


def resolve_workspace(path: str | Path | None = None) -> Path:
    selected = Path(path).expanduser() if path is not None else default_workspace()
    resolved = selected.resolve(strict=False)
    for source_root in installed_source_roots():
        if resolved == source_root or resolved.is_relative_to(source_root):
            raise PathSafetyError(
                "Private runtime workspace must stay outside the installed Skill/source tree"
            )
    return resolved


def resolve_within(
    workspace: str | Path,
    user_path: str | Path,
    *,
    must_exist: bool = False,
) -> Path:
    """Resolve a path and reject traversal or a symlink escape from workspace."""

    root = resolve_workspace(workspace)
    raw = Path(user_path).expanduser()
    candidate = raw if raw.is_absolute() else root / raw
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PathSafetyError(f"Path must stay inside the workspace: {user_path}") from exc
    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"Path does not exist inside the workspace: {user_path}")
    return resolved


def validate_identifier(value: str, *, field: str) -> str:
    if not IDENTIFIER_RE.fullmatch(value):
        raise ValueError(
            f"{field} must be 1-64 ASCII letters, digits, dots, underscores, or hyphens, "
            "and must start with a letter or digit"
        )
    if value in {".", ".."} or value.rstrip(" .") != value:
        raise ValueError(f"Invalid {field}: {value!r}")
    if value.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        raise ValueError(f"{field} is a reserved Windows name: {value!r}")
    return value


def validate_contact_display(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 200 or CONTROL_RE.search(cleaned):
        raise ValueError("contact must be 1-200 characters and contain no control characters")
    return cleaned


def slugify_contact(value: str) -> str:
    display = validate_contact_display(value)
    ascii_base = (
        unicodedata.normalize("NFKD", display).encode("ascii", "ignore").decode("ascii")
    )
    ascii_base = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_base).strip(" .-_")
    if not ascii_base:
        ascii_base = "contact"
    ascii_base = ascii_base[:48].rstrip(" .-_") or "contact"
    digest = hashlib.sha256(display.encode("utf-8")).hexdigest()[:10]
    slug = f"{ascii_base}-{digest}"
    return validate_identifier(slug, field="contact slug")


def validate_contact_slug(value: str) -> str:
    return validate_identifier(value, field="contact slug")


def parse_iso_date(value: str, *, field: str) -> date:
    if not ISO_DATE_RE.fullmatch(value):
        raise ValueError(f"{field} must use strict ISO format YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid calendar date: {value}") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field} must use strict ISO format YYYY-MM-DD")
    return parsed


def validate_date_range(start_date: str, end_date: str) -> tuple[str, str]:
    start = parse_iso_date(start_date, field="start-date")
    end = parse_iso_date(end_date, field="end-date")
    if start > end:
        raise ValueError("start-date must be on or before end-date")
    return start.isoformat(), end.isoformat()


def make_batch_id() -> str:
    return f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


def relative_path(workspace: str | Path, path: str | Path) -> str:
    resolved = resolve_within(workspace, path)
    return resolved.relative_to(resolve_workspace(workspace)).as_posix()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class BatchPaths:
    workspace: Path
    root: Path
    manifest: Path
    screenshots: Path
    ocr: Path
    ocr_text: Path
    normalized: Path
    review_csv: Path


def get_batch_paths(
    workspace: str | Path | None,
    contact_display: str,
    start_date: str,
    end_date: str,
    batch_id: str | None = None,
) -> tuple[BatchPaths, dict[str, Any]]:
    root = resolve_workspace(workspace)
    display = validate_contact_display(contact_display)
    start, end = validate_date_range(start_date, end_date)
    contact_slug = slugify_contact(display)
    selected_batch_id = (
        make_batch_id()
        if batch_id is None
        else validate_identifier(batch_id, field="batch id")
    )
    date_range_slug = f"{start}_to_{end}"
    batch_root = resolve_within(
        root,
        Path("data")
        / "contacts"
        / contact_slug
        / "batches"
        / date_range_slug
        / selected_batch_id,
    )
    paths = BatchPaths(
        workspace=root,
        root=batch_root,
        manifest=batch_root / "manifest.json",
        screenshots=batch_root / "screenshots",
        ocr=batch_root / "ocr",
        ocr_text=batch_root / "ocr_text",
        normalized=batch_root / "normalized",
        review_csv=batch_root / "review.csv",
    )
    metadata = {
        "contact_display": display,
        "contact_slug": contact_slug,
        "start_date": start,
        "end_date": end,
        "date_range": f"{start}/{end}",
        "date_range_slug": date_range_slug,
        "batch_id": selected_batch_id,
    }
    return paths, metadata


def init_batch(
    workspace: str | Path | None,
    contact_display: str,
    start_date: str,
    end_date: str,
    batch_id: str | None = None,
) -> BatchPaths:
    paths, metadata = get_batch_paths(
        workspace, contact_display, start_date, end_date, batch_id
    )
    paths.workspace.mkdir(parents=True, exist_ok=True)
    for directory in (
        paths.root,
        paths.screenshots,
        paths.ocr,
        paths.ocr_text,
        paths.normalized,
    ):
        safe_directory = resolve_within(paths.workspace, directory)
        safe_directory.mkdir(parents=True, exist_ok=True)
        resolve_within(paths.workspace, safe_directory, must_exist=True)

    contact_root = paths.root.parents[2]
    contact_json = resolve_within(paths.workspace, contact_root / "contact.json")
    if contact_json.parent != contact_root or contact_json.name != "contact.json":
        raise PathSafetyError("Contact metadata path escapes the selected contact")
    if not contact_json.exists():
        write_json(
            contact_json,
            {
                "schema_version": SCHEMA_VERSION,
                "contact_display": metadata["contact_display"],
                "contact_slug": metadata["contact_slug"],
                "created_at": now_iso(),
            },
        )

    safe_manifest = resolve_within(paths.workspace, paths.manifest)
    if safe_manifest.parent != paths.root or safe_manifest.name != "manifest.json":
        raise PathSafetyError("Manifest path escapes the selected batch")
    if safe_manifest.exists():
        manifest = load_manifest(paths.root, paths.workspace)
        for key in ("contact_slug", "start_date", "end_date", "batch_id"):
            if manifest.get(key) != metadata[key]:
                raise RuntimeError(f"Existing batch manifest does not match {key}")
        return paths

    manifest_paths = {
        "root": relative_path(paths.workspace, paths.root),
        "screenshots": relative_path(paths.workspace, paths.screenshots),
        "ocr": relative_path(paths.workspace, paths.ocr),
        "ocr_text": relative_path(paths.workspace, paths.ocr_text),
        "normalized": relative_path(paths.workspace, paths.normalized),
        "review_csv": relative_path(paths.workspace, paths.review_csv),
    }
    write_json(
        safe_manifest,
        {
            "schema_version": SCHEMA_VERSION,
            **metadata,
            "created_at": now_iso(),
            "paths": manifest_paths,
            "capture": {"status": "not_started", "screenshots": []},
            "ocr": {"status": "not_started", "images": []},
            "normalize": {"status": "not_started"},
        },
    )
    return paths


def resolve_batch_root(
    batch_root: str | Path,
    workspace: str | Path | None,
    *,
    must_exist: bool = True,
) -> Path:
    resolved_workspace = resolve_workspace(workspace)
    resolved = resolve_within(resolved_workspace, batch_root, must_exist=must_exist)
    if must_exist and not resolved.is_dir():
        raise NotADirectoryError(f"Batch path is not a directory: {batch_root}")
    return resolved


def load_manifest(
    batch_root: str | Path,
    workspace: str | Path | None,
) -> dict[str, Any]:
    root = resolve_batch_root(batch_root, workspace)
    manifest_path = resolve_within(resolve_workspace(workspace), root / "manifest.json", must_exist=True)
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Unsupported manifest schema: {manifest.get('schema_version')!r}")
    validate_contact_display(str(manifest.get("contact_display", "")))
    validate_contact_slug(str(manifest.get("contact_slug", "")))
    validate_identifier(str(manifest.get("batch_id", "")), field="batch id")
    validate_date_range(
        str(manifest.get("start_date", "")), str(manifest.get("end_date", ""))
    )
    manifest_paths = manifest.get("paths")
    if not isinstance(manifest_paths, dict):
        raise ValueError("Manifest paths must be an object")
    expected_paths = {
        "root": root,
        "screenshots": root / "screenshots",
        "ocr": root / "ocr",
        "ocr_text": root / "ocr_text",
        "normalized": root / "normalized",
        "review_csv": root / "review.csv",
    }
    if set(manifest_paths) != set(expected_paths):
        raise ValueError("Manifest paths do not match the schema-v1 path set")
    for name, value in manifest_paths.items():
        if not isinstance(value, str) or not value or Path(value).is_absolute():
            raise ValueError(f"Manifest path {name!r} must be workspace-relative")
        resolved_path = resolve_within(resolve_workspace(workspace), value)
        if resolved_path != expected_paths[name]:
            raise ValueError(f"Manifest path {name!r} does not match the selected batch")
    return manifest


def save_manifest(
    batch_root: str | Path,
    workspace: str | Path | None,
    manifest: dict[str, Any],
) -> None:
    root = resolve_batch_root(batch_root, workspace)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Refusing to save a manifest without schema_version 1")
    write_json(resolve_within(resolve_workspace(workspace), root / "manifest.json"), manifest)


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
