# Security Policy

## Supported versions

Security fixes are provided for the latest `0.1.x` release until a newer supported release line is announced.

## Reporting a vulnerability

Use the repository's private vulnerability reporting feature under **Security > Advisories > Report a vulnerability**, when enabled. Do not open a public issue containing an exploit, private chat data, credentials, local paths, screenshots, or other sensitive evidence.

If private reporting is unavailable, contact the maintainer through a private channel listed on the repository owner's GitHub profile. Send the minimum detail needed to establish impact. Wait for a secure reply before sharing a proof of concept or sensitive attachment.

Include:

- the affected version and command;
- the security boundary that failed;
- minimal reproduction steps using synthetic data;
- expected and observed behavior;
- whether any real data, credential, network destination, or external service was exposed.

Never send real WeChat screenshots or conversation content as a vulnerability reproducer.

## Security model

This tool processes highly sensitive local content. Its intended guarantees are:

- explicit authorization and bounded contact/date scope;
- no database decryption, process injection, unofficial client, or private-protocol access;
- local processing by default and no implicit upload;
- runtime data outside the installed source tree;
- validated identifiers, strict ISO date ranges, workspace containment, and rejection of escaping symbolic links;
- screenshot SHA-256 provenance and requested/actual OCR device evidence;
- export-only spreadsheet formula mitigation without altering raw OCR;
- a preview and separate explicit approval before any external transfer or paid service.

An issue that bypasses these controls, crosses the workspace boundary, leaks data, executes content from an export, misrepresents the actual device in a security-relevant way, or performs an unapproved network transfer is in scope for a security report.

OCR accuracy problems without a boundary bypass are normally quality issues. Unauthorized use of a user's account, weaknesses in WeChat, and vulnerabilities in separately installed third-party software should be reported to the appropriate vendor.

## Safe handling

- Use synthetic fixtures when reproducing a bug.
- Do not attach `.env` files, tokens, cookies, account identifiers, chat databases, screenshots, manifests from real runs, OCR output, or reports.
- Review dependency and model downloads before first use. PaddleOCR models can require network access and disk space.
- Keep generated workspaces on an access-controlled local drive and remove exported review bundles according to the user's retention policy.
- Do not place a workspace on a shared, permissively writable, synchronized, or elevated-process path. The supported model is a non-elevated private workspace; same-authority malicious writers are outside the tamper-resistance guarantee.
- SHA-256 fields detect accidental or uncoordinated changes. They are not signatures and do not authenticate evidence against an actor who can rewrite both artifacts and the manifest.
- Treat `prepare-online-review` output as sensitive. The command prepares a local candidate; it does not make external transfer safe or authorized.
