# Evidence-aware semantic analysis

Read this reference only after an authorized batch has been normalized and the user asks for interpretation, synthesis, or an analytical report. Work from the normalized JSONL locally, using the manifest, review CSV, raw OCR, and screenshots only as supporting evidence within the same authorized scope.

The CLI `report` command creates a raw evidence index. It does not determine meaning, resolve OCR uncertainty, establish a complete timeline, or produce the semantic analysis described here.

## Preserve the authorized scope

- Restate the selected contact slug, batch identifier, inclusive date range, requested questions, and exclusions before drawing conclusions.
- Analyze only the batches the user explicitly selected. Do not search adjacent contacts, dates, directories, or unrelated artifacts to fill gaps.
- Treat the capture range as evidence collected within the authorized dates, not proof that every message in that range was captured.
- Keep analysis local unless the separate external-review approval gate has been completed for an exact transfer.

## Assess evidence before interpreting it

Read the manifest and normalized JSONL, then account for:

- whether both requested date boundaries were captured and reviewed;
- manifest integrity checks and the normalized JSONL hash;
- records whose `review_status` is `needs_review` and every `review_reasons` value;
- missing or low `ocr_confidence`, unknown speakers, empty or non-text items, media cards, and voice content;
- possible scrolling overlap, gaps, contradictory records, and repeated text from distinct sources;
- corrections that were verified against screenshots and recorded in the current analysis notes.

`review_status` is a queue state, not proof that a record is correct. `created_at` records pipeline processing time, not when a message was sent. Use `timestamp_text` as message-time evidence only after it has been read from the screen and, when consequential, checked against the source screenshot.

If the evidence cannot answer the user's question, say so. Do not convert missing coverage into a negative finding or fill an unknown speaker, time, intent, or outcome from context alone.

## Classify claims

For every consequential claim, distinguish one of these evidence states:

| State | Meaning | Required treatment |
| --- | --- | --- |
| Verified | The relevant screenshot was checked and supports the claim. | State what was verified and cite the normalized record plus source evidence. |
| OCR-supported | Normalized text supports the claim, but the screenshot was not checked. | Attribute it to OCR and disclose relevant confidence or review flags. |
| Inference | The claim is a reasoned interpretation rather than directly stated evidence. | Label it as an inference, cite all supporting and conflicting records, and explain the reasoning briefly. |
| Unresolved | Evidence is missing, ambiguous, contradictory, or low confidence. | Do not choose a preferred answer; place it in the review section. |

Do not elevate an inference through confident wording. Consequential names, dates, amounts, addresses, commitments, links, and outcomes should remain unresolved until the associated screenshot is checked.

## Build the analysis

### Scope

Identify the authorized batch or batches, inclusive dates, requested question, exclusions, and whether the start and end boundaries were actually observed.

### Data quality

Report record counts, review-queue counts, verified corrections, missing boundaries, OCR limitations, unknown speakers, non-text content, and uncertain overlap. Describe material gaps before presenting findings.

### Timeline

Use only explicit, reviewable time evidence. Preserve observed record order when exact times are unavailable, but label it as capture order rather than a proven conversation chronology. Do not use `created_at` as a message timestamp. Cite each consequential event.

### Facts and commitments

Separate direct statements from interpretations. A commitment should identify the actor, action, deadline or condition, and completion state only where the evidence explicitly supports each element. Mark absent elements as unknown. Do not infer fulfillment merely because no later contradiction was captured.

### Uncertainties and review

List unresolved OCR, speaker, timestamp, overlap, media, contradiction, and coverage questions. Name the exact record or source evidence that a reviewer should inspect and explain what decision depends on it.

### Risks

Describe risks supported by the authorized evidence and separate them from general cautions. State the evidence state and potential impact; do not present legal, medical, financial, safety, or relationship judgments as professional conclusions.

### Next actions

Derive actions from explicit commitments, unresolved evidence, or the user's stated goal. Identify the responsible party and due date only when supported; otherwise label them unassigned or unknown. Do not send messages, contact participants, widen collection, or upload material without separate authorization.

## Cite provenance

Every consequential timeline item, fact, commitment, risk, and inference must point back to normalized evidence. Use a compact evidence label in the analysis and provide an evidence appendix containing:

- `message_id`;
- workspace-relative `source_image` without exposing a machine root;
- `source_sha256` (full value in the appendix; a clearly matching short prefix may be used in prose);
- `bbox` when it helps locate the item;
- `ocr_confidence`, `review_status`, and `review_reasons`;
- whether the screenshot was checked and whether a correction was applied in the analysis notes.

When several records support one claim, cite each record. When records conflict, cite both sides. Preserve identical text from different source hashes as separate evidence, and do not collapse uncertain scrolling overlap.

## Minimum report shape

Use the following sections unless the user's requested format requires an equivalent structure:

1. Authorized scope and question
2. Data quality and coverage
3. Timeline
4. Facts and commitments
5. Uncertainties and required review
6. Evidence-supported risks
7. Next actions
8. Evidence appendix

End with a short limitations statement. Do not retain chat text, identities, screenshots, or conclusions in durable memory.
