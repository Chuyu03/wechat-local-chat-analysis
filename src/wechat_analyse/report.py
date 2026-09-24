from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from .paths import (
    load_manifest,
    now_iso,
    resolve_batch_root,
    resolve_within,
    resolve_workspace,
    sha256_file,
    validate_contact_slug,
    write_json,
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected JSON object at {path.name}:{line_number}")
            records.append(value)
    return records


MARKDOWN_SPECIAL_RE = re.compile(r"([\\`*_{}\[\]()<>#+\-.!|])")


def _escape_markdown_text(value: Any) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    return MARKDOWN_SPECIAL_RE.sub(r"\\\1", text)


def load_batch_records(
    batch_root: str | Path,
    workspace: str | Path | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root = resolve_workspace(workspace)
    batch = resolve_batch_root(batch_root, root)
    manifest = load_manifest(batch, root)
    normalize_state = manifest.get("normalize")
    if not isinstance(normalize_state, dict) or normalize_state.get("status") != "complete":
        raise RuntimeError("Normalization must complete successfully before reporting")
    messages_value = normalize_state.get("messages_jsonl")
    if not isinstance(messages_value, str) or not messages_value or Path(messages_value).is_absolute():
        raise ValueError("Normalized messages path must be workspace-relative")
    messages_path = resolve_within(root, messages_value, must_exist=True)
    normalized_dir = resolve_within(root, batch / "normalized", must_exist=True)
    try:
        messages_path.relative_to(normalized_dir)
    except ValueError as exc:
        raise ValueError("Normalized messages path escapes the selected batch") from exc
    expected_messages_digest = str(
        normalize_state.get("messages_jsonl_sha256", "")
    ).lower()
    if len(expected_messages_digest) != 64 or sha256_file(messages_path) != expected_messages_digest:
        raise ValueError("Normalized messages bytes do not match the manifest")
    records = _read_jsonl(messages_path)
    if not records:
        raise FileNotFoundError("No normalized messages found for the selected batch")
    return manifest, records


def render_report(contact_slug: str, records: Iterable[dict[str, Any]]) -> str:
    slug = validate_contact_slug(contact_slug)
    material = list(records)
    review_items = [
        record for record in material if record.get("review_status") == "needs_review"
    ]
    scopes = sorted(
        {
            f"{record.get('start_date', '?')} to {record.get('end_date', '?')}"
            for record in material
        }
    )
    lines = [
        f"# Local chat evidence report: {slug}",
        "",
        "> This report is local evidence derived from OCR. Verify consequential facts against screenshots.",
        "",
        "## Scope",
        "",
        f"- Contact slug: `{slug}`",
        f"- Candidate records: {len(material)}",
        f"- Records needing review: {len(review_items)}",
    ]
    for scope in scopes:
        lines.append(f"- Inclusive batch range: {scope}")
    lines.extend(["", "## Evidence index", ""])
    for record in material:
        message_id = str(record.get("message_id", "unknown"))
        speaker = str(record.get("speaker", "unknown"))
        status = str(record.get("review_status", "unknown"))
        text = _escape_markdown_text(record.get("content_text", ""))
        lines.append(f"- `{message_id}` [{speaker}; {status}] {text}")
    if review_items:
        lines.extend(["", "## Review required", ""])
        for record in review_items:
            reasons = ", ".join(str(reason) for reason in record.get("review_reasons", []))
            lines.append(f"- `{record.get('message_id', 'unknown')}`: {reasons or 'unspecified uncertainty'}")
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- The CLI does not prove that the captured screen covered every message in the authorized range.",
            "- OCR, speaker inference, scrolling overlap, media cards, and voice content may require manual review.",
            "- Repeated text from distinct sources is preserved; only identical screenshot hashes are deterministic duplicates.",
            "",
        ]
    )
    return "\n".join(lines)


def build_batch_report(
    batch_root: str | Path,
    workspace: str | Path | None = None,
) -> Path:
    root = resolve_workspace(workspace)
    batch = resolve_batch_root(batch_root, root)
    manifest, records = load_batch_records(batch, root)
    slug = validate_contact_slug(str(manifest.get("contact_slug", "")))
    normalized_dir = resolve_within(root, batch / "normalized", must_exist=True)
    target = resolve_within(root, normalized_dir / "report.md")
    try:
        target.relative_to(normalized_dir)
    except ValueError as exc:
        raise ValueError("Report output escapes the selected batch") from exc
    target.write_text(render_report(slug, records), encoding="utf-8", newline="\n")
    return target


def prepare_online_review_request(
    batch_root: str | Path,
    workspace: str | Path | None = None,
    *,
    max_items: int = 50,
) -> Path:
    if max_items <= 0 or max_items > 500:
        raise ValueError("max-items must be between 1 and 500")
    root = resolve_workspace(workspace)
    batch = resolve_batch_root(batch_root, root)
    manifest, records = load_batch_records(batch, root)
    slug = validate_contact_slug(str(manifest.get("contact_slug", "")))
    candidates = [
        {
            "message_id": record.get("message_id"),
            "content_text": record.get("content_text"),
            "source_image": record.get("source_image"),
            "source_sha256": record.get("source_sha256"),
            "ocr_confidence": record.get("ocr_confidence"),
            "review_reasons": record.get("review_reasons", []),
        }
        for record in records
        if record.get("review_status") == "needs_review"
    ][:max_items]
    request_id = now_iso().replace(":", "").replace("+", "-")
    normalized_dir = resolve_within(root, batch / "normalized", must_exist=True)
    target = resolve_within(root, normalized_dir / f"online-review-{request_id}.json")
    try:
        target.relative_to(normalized_dir)
    except ValueError as exc:
        raise ValueError("Online review output escapes the selected batch") from exc
    write_json(
        target,
        {
            "schema_version": 1,
            "status": "local_only_not_uploaded",
            "redacted": False,
            "selection_scope": "selected_batch_needs_review_up_to_max_items",
            "created_at": now_iso(),
            "contact_slug": slug,
            "batch_id": manifest["batch_id"],
            "start_date": manifest["start_date"],
            "end_date": manifest["end_date"],
            "candidate_count": len(candidates),
            "warning": (
                "Sensitive local candidate. Redact and obtain separate approval before any transfer."
            ),
            "candidates": candidates,
        },
    )
    return target
