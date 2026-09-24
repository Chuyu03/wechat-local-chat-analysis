# Authorized capture workflow

Read this reference when scoping or collecting conversation screenshots from the official WeChat client for Windows.

## Before collection

- Confirm the user is authorized to view and analyze the requested conversation.
- Record the approved contact slug, inclusive ISO start and end dates, analysis goal, and exclusions.
- For real collection, reject an end date in the future. Future dates are valid only in an explicitly synthetic test that does not operate WeChat.
- Keep one contact and one date range per batch. Create separate batches when the scope changes.
- If the user asks for broader access such as database extraction, decryption, process hooks, unofficial plugins, or protocol simulation, stop and explain that this Skill does not perform those operations.

## Collection

- Verify the expected conversation is open before the first capture and after any interruption.
- Prefer a crop containing only the chat pane. Exclude the contact list, unrelated chats, desktop notifications, account identifiers, and other applications where practical.
- Before running `capture`, explain that it will bind to the current foreground HWND/process, require an approved official WeChat executable name, take screenshots of the selected rectangle, and move or scroll the pointer. Obtain permission for that visible action. Tell the user to press Ctrl+C in the terminal or move the pointer to a screen corner to trigger the PyAutoGUI fail-safe.
- Capture chronologically with enough overlap to avoid gaps. Do not infer missing content from scroll position alone.
- Finish collection before OCR. During capture, focus on the visible scope and coverage rather than interpreting individual messages.
- Avoid activating voice playback, links, mini-programs, payments, downloads, or message actions. A user-authorized manual conversion of a voice message to text is a separate visible action and must not trigger playback.

The CLI `capture` command uses the optional local capture dependency to screenshot only the user-selected region, scroll between captures, and record relative paths and SHA-256 hashes. It is not permission to capture unrelated screen content. Stop immediately if another window appears, the active conversation changes, or the chosen region includes unrelated information.

## Coverage check

Before OCR, verify:

- the start and end boundaries are visible or their absence is disclosed;
- chronological sections do not have an obvious gap;
- every screenshot belongs to the authorized conversation;
- duplicates and likely scrolling overlap are identified without deleting uncertain evidence;
- unrelated or accidentally captured content is removed from the candidate batch before processing.

If any boundary is unclear, describe the gap and ask the user whether to collect more evidence. Do not silently widen the approved date range.

Only after this check may the agent pass `--acknowledge-capture-coverage` to `ocr`. OCR processes exactly the completed capture manifest's registered screenshots, rejects missing or changed registered files, and ignores extra image files that were not registered by capture.
