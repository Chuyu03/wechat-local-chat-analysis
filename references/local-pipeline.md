# Local CLI pipeline

Read this reference when operating the repository's CLI. Run commands from an installed environment on Windows with Python 3.11 or 3.12.

## Workspace

The default workspace is `%LOCALAPPDATA%\WechatLocalChatAnalysis`. Override it with the global `--workspace` option when the user chooses another local directory. Runtime data must stay outside the installed Skill source tree.

Use `--help` on the root command and each subcommand for the installed version's exact arguments:

```powershell
wechat-local-chat-analysis --help
wechat-local-chat-analysis init-batch --help
```

`python -m wechat_analyse` exposes the same command surface.

## Commands

| Command | Purpose |
| --- | --- |
| `doctor` | Report the platform, Python version, optional packages, GPU detection, and Paddle CUDA capability without claiming completed OCR device use. |
| `init-batch --contact TEXT --start-date YYYY-MM-DD --end-date YYYY-MM-DD [--batch-id ID]` | Create a schema-v1 manifest for one authorized contact and inclusive ISO date range. |
| `capture --batch PATH --region x,y,width,height --acknowledge-visible-scope` | Bind to an approved official WeChat foreground process, capture the selected region into an existing batch, scroll between frames, compute SHA-256 hashes, and interrupt if the window identity changes. Use `--help` for process-name, count, scroll, and delay controls. |
| `ocr --batch PATH --acknowledge-capture-coverage [--device auto\|cpu\|gpu:0]` | After separate coverage review, process exactly the completed capture manifest's registered screenshots and record requested/actual device evidence. Optional language and limit controls are shown in `--help`. |
| `normalize --batch PATH [--min-confidence 0..1]` | Preserve raw OCR text, produce normalized message JSONL, and apply the review-confidence threshold. |
| `report --batch PATH` | Generate a local evidence-aware report for exactly one normalized batch. |
| `prepare-online-review --batch PATH [--max-items N]` | Create a local, inspectable candidate for exactly one batch; never upload it. |

Artifact-producing commands print the target path after success; `doctor` prints diagnostics instead. Console paths may be absolute for usability; paths persisted in the schema-v1 manifest remain workspace-relative.

The report command creates a local evidence index and uncertainty summary. The agent must still read the normalized JSONL locally to produce the user's requested semantic summary; it must not describe the CLI report alone as complete analysis.

## Device behavior

- CPU is the compatibility baseline.
- `auto` may try GPU and then fall back to CPU, but the manifest must record both the requested device and the actual device plus the reason for fallback.
- An explicit `gpu:0` request must stop on GPU initialization failure. It must not silently run on CPU.
- Do not equate a configured value with successful hardware use. Verify the active Paddle framework and runtime result.

PaddleOCR is optional. Install the appropriate PaddlePaddle CPU or GPU framework using the official selector, then install the repository's OCR optional dependency. Model downloads are controlled by PaddleOCR and can require network access; disclose this before the first OCR run.

Official references:

- [PaddleOCR installation](https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/installation.html)
- [PaddleOCR general OCR pipeline](https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/pipeline_usage/OCR.html)

## Failure handling

- On a validation, containment, link, or manifest error, stop without processing the affected file.
- On OCR failure, keep registered screenshots intact and report the requested/actual device evidence.
- Reject incomplete capture, missing or changed registered screenshots, changed OCR JSON/text, or changed normalized JSONL. Ignore and record extra screenshot files that were never registered by capture.
- Do not claim complete coverage when collection boundaries are missing.
- Do not delete source screenshots after normalization or reporting.
