---
name: wechat-local-chat-analysis
description: Capture, OCR, normalize, review, and summarize authorized conversations from the official WeChat client for Windows using a privacy-first local workflow. Use when the user wants evidence-backed analysis of chat screenshots; do not use for database decryption, process injection, unofficial clients, or unapproved cloud uploads.
---

# WeChat Local Chat Analysis

Analyze only conversations the user is authorized to access. Keep the workflow local by default and preserve screenshots as reviewable evidence rather than treating OCR output as unquestionable fact.

## Non-negotiable boundaries

- Support Windows 10/11 and the official WeChat desktop client. Do not read or decrypt WeChat databases, hook or inject into processes, automate unofficial clients, use unofficial plugins, or imitate private protocols.
- Establish the authorized contacts, date range, and batch before collection. Stop if the visible conversation or requested scope does not match that authorization.
- Capture the complete approved range first; run OCR and analysis only after coverage is checked. Do not interrupt live collection with per-screenshot OCR.
- Keep screenshots, OCR output, normalized messages, review files, manifests, and reports local unless the user separately approves an external transfer.
- The CLI file pipeline is local; model-side semantic analysis is a separate data boundary. Before placing chat text into a model context that is not verified as device-local, preview the exact batch and obtain explicit approval. Without that approval, stop at the local evidence report.
- Before any cloud upload, external model call, or paid service, show the exact files or fields, destination, visibility, redactions, privacy risks, likely fees or quota use, and a local alternative. Continue only after explicit approval for that transfer.
- Treat OCR as fallible. Never state high-impact facts from low-confidence text without checking the corresponding screenshot or obtaining user confirmation.

## Route the request

1. For scoping and authorized collection, read [references/capture-workflow.md](references/capture-workflow.md).
2. For CLI use and the end-to-end local workflow, read [references/local-pipeline.md](references/local-pipeline.md).
3. Before interpreting or exporting data, read [references/data-contract.md](references/data-contract.md).
4. For a semantic summary or analytical report, read [references/analysis-reporting.md](references/analysis-reporting.md) after normalization and evidence review.
5. Read [references/external-review.md](references/external-review.md) only when the user asks to prepare or send material to an online service.

## Default workflow

1. Confirm authorization, contacts, strict ISO start/end dates, intended questions, and exclusions. A real collection range cannot end in the future; future dates are allowed only for an explicitly synthetic, non-capture test.
2. Run `wechat-local-chat-analysis doctor`, then create a bounded batch with `init-batch` and retain the printed batch path.
3. Before `capture --batch <printed-batch-path>`, explain that it will bind to an approved official WeChat process, screenshot the selected rectangle, and send scroll events to that foreground window. Obtain permission for that visible control, verify the official WeChat conversation and crop, keep unrelated content outside the region, and explain that Ctrl+C or moving the pointer to a screen corner stops the PyAutoGUI run. If the official executable name differs from `WeChat.exe` or `Weixin.exe`, verify it first and pass it explicitly with `--expected-process-name`.
4. Run `capture`, verify every registered screenshot, the date boundaries, continuity, and absence of unrelated content, and only then run `ocr --acknowledge-capture-coverage`. The flag confirms that separate human/agent coverage review; it is not inferred from capture completion.
5. Run `normalize`. Use normalized JSONL as the main analysis input; use screenshots and raw OCR as evidence for review.
6. Use the review CSV as a checklist for low-confidence and ambiguous items. Record verified corrections in the analysis notes; the CSV is not imported back into JSONL. Then run `report` to create the raw local evidence index.
7. Before semantic analysis, read [references/analysis-reporting.md](references/analysis-reporting.md). Then read the normalized JSONL locally and produce the requested summary with claim-level provenance, evidence limits, unresolved items, and the authorized scope. Do not represent the CLI evidence report as a complete semantic analysis.

## Analysis rules

- Deduplicate only screenshots with identical SHA-256 hashes. Preserve repeated text from different screenshots, times, or sources.
- Treat possible overlap from scrolling as a review item unless the evidence proves it is the same captured message.
- Review names, dates, amounts, addresses, commitments, links, image cards, and other consequential facts against the screenshot.
- Do not retain chat text, identities, screenshots, or conclusions in durable memory.
- `prepare-online-review` creates a local candidate bundle only. It does not authorize or perform an upload.

## Invocation examples

- English: `Use $wechat-local-chat-analysis to summarize an authorized WeChat conversation from local screenshots and flag uncertain OCR.`
- 中文：`使用 $wechat-local-chat-analysis 分析我已授权的微信聊天截图，先本地 OCR，再标出低置信度内容。`
