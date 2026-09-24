# Local data contract

Read this reference before interpreting manifests, normalized messages, or review exports.

## Manifest schema v1

The manifest is JSON with `schema_version` set to `1`. Paths stored in the manifest are relative to the workspace. A manifest should provide enough evidence to establish:

- the sanitized batch and contact identifiers;
- the inclusive ISO start and end dates;
- registered screenshot relative paths and SHA-256 hashes;
- capture completion state and the foreground process identity bound during capture;
- OCR status and package/framework versions;
- the requested OCR device, actual device, and any fallback reason;
- relative paths plus SHA-256 hashes for OCR JSON/text, normalized JSONL, and review CSV artifacts.

Do not write machine-specific absolute paths, credentials, account identifiers, or unrelated environment details into the manifest.

These hashes detect accidental or uncoordinated changes between stages. They are not digital signatures and do not protect against an actor who can rewrite both the artifacts and the manifest in the same workspace.

## Normalized messages

Normalized messages are JSON Lines: one JSON object per candidate message. Preserve the original OCR text in the raw OCR artifact and retain a traceable screenshot/hash reference in normalized output.

Repeated text is not sufficient evidence of duplication. Preserve messages with the same text when they came from different screenshots, times, or sources. Only identical screenshot hashes are deterministic duplicates. Mark uncertain scrolling overlap for review instead of deleting it.

## Review CSV

The review export is a human checklist; it is not imported back into JSONL. The CLI automatically queues low or missing confidence, unknown speaker, empty text, and repeated text from distinct screenshots that may be scrolling overlap. Independently of automatic queueing, the agent must manually review these consequential categories against screenshots:

- low OCR confidence or unreadable text;
- unclear time, speaker, sequence, or scrolling overlap;
- names, dates, amounts, addresses, commitments, links, and other high-impact facts;
- image cards, room cards, media, or non-text items not represented reliably by OCR.

To mitigate spreadsheet formula injection, prefix any exported cell whose first character is `=`, `+`, `-`, `@`, a tab, or a carriage return. This export-only protection must not change the raw OCR text or normalized JSONL value.

## Reports

Reports are raw evidence indexes generated from JSONL; editing the review CSV does not update them. The agent's analysis notes must distinguish manually checked evidence from unresolved OCR and list important uncertainty. Do not infer an absent message, participant, or date from incomplete screenshots.
