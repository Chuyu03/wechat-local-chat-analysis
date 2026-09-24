# External review approval gate

Read this reference only when the user asks to prepare, upload, or analyze chat material with an online or third-party service.

## Local preparation

`prepare-online-review --batch PATH` may create a local candidate bundle for exactly one already-authorized batch. It must not upload, email, synchronize, publish, or call an external model. Treat the bundle as sensitive until the user has inspected it.

Prefer the smallest useful excerpt. Remove unrelated messages and fields; replace names, account identifiers, addresses, links, filenames, and other direct identifiers when they are unnecessary for the approved question. Keep a local mapping only when the user needs reversibility.

## Required preview

Before any transfer, show:

- the exact files and fields proposed for transfer;
- the destination service and account context;
- who can access the material and whether it may become public;
- the redactions already applied and residual re-identification risk;
- whether the service may retain or train on the data, if this is known;
- expected API, subscription, storage, or model charges and quota use;
- a local-only alternative.

Ask for explicit approval immediately before the single named transfer. Approval for local preparation, a previous upload, or a different service does not authorize this upload.

If destination, retention, visibility, cost, or account context cannot be established, stop after local preparation. Never include credentials, cookies, tokens, environment files, or unrelated screenshots in a review bundle.
