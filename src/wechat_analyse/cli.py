from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .capture import capture_batch, parse_region
from .config import (
    DEFAULT_CAPTURE_COUNT,
    DEFAULT_DELAY_SECONDS,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_PRE_CAPTURE_DELAY_SECONDS,
    DEFAULT_SCROLL_CLICKS,
)
from .doctor import run_doctor
from .normalize import normalize_batch
from .ocr import ocr_batch
from .paths import PathSafetyError, init_batch
from .report import build_batch_report, prepare_online_review_request


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wechat-local-chat-analysis",
        description="Privacy-first local workflow for authorized PC WeChat screenshots.",
    )
    parser.add_argument(
        "--workspace",
        help="Private runtime workspace. Defaults to %%LOCALAPPDATA%%\\WechatLocalChatAnalysis.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="Check the local platform and optional dependencies.")

    init_parser = subparsers.add_parser("init-batch", help="Create one bounded local batch.")
    _add_scope_arguments(init_parser)

    capture_parser = subparsers.add_parser(
        "capture", help="Capture a visible authorized screen region before OCR."
    )
    capture_parser.add_argument(
        "--batch", required=True, help="Existing batch path inside the workspace."
    )
    capture_parser.add_argument("--region", required=True, help="x,y,width,height")
    capture_parser.add_argument("--count", type=int, default=DEFAULT_CAPTURE_COUNT)
    capture_parser.add_argument(
        "--scroll-clicks", type=int, default=DEFAULT_SCROLL_CLICKS
    )
    capture_parser.add_argument(
        "--delay-seconds", type=float, default=DEFAULT_DELAY_SECONDS
    )
    capture_parser.add_argument(
        "--pre-capture-delay-seconds",
        type=float,
        default=DEFAULT_PRE_CAPTURE_DELAY_SECONDS,
    )
    capture_parser.add_argument(
        "--acknowledge-visible-scope",
        action="store_true",
        help="Confirm the foreground chat and selected rectangle match the authorized scope.",
    )
    capture_parser.add_argument(
        "--expected-process-name",
        action="append",
        dest="expected_process_names",
        help="Approved official WeChat executable name. Repeat to allow multiple names; defaults to WeChat.exe and Weixin.exe.",
    )

    ocr_parser = subparsers.add_parser("ocr", help="Run optional local PaddleOCR 3.x.")
    ocr_parser.add_argument("--batch", required=True, help="Batch path inside the workspace.")
    ocr_parser.add_argument("--device", choices=("auto", "cpu", "gpu:0"), default="auto")
    ocr_parser.add_argument("--lang", default="ch")
    ocr_parser.add_argument("--limit", type=int)
    ocr_parser.add_argument(
        "--acknowledge-capture-coverage",
        action="store_true",
        help="Confirm the registered capture is complete, in scope, and ready for OCR.",
    )

    normalize_parser = subparsers.add_parser(
        "normalize", help="Build normalized JSONL and a spreadsheet-safe review CSV."
    )
    normalize_parser.add_argument("--batch", required=True)
    normalize_parser.add_argument(
        "--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE
    )

    report_parser = subparsers.add_parser("report", help="Build a local evidence report.")
    report_parser.add_argument("--batch", required=True)

    review_parser = subparsers.add_parser(
        "prepare-online-review",
        help="Create a local review candidate manifest; never upload it.",
    )
    review_parser.add_argument("--batch", required=True)
    review_parser.add_argument("--max-items", type=int, default=50)
    return parser


def _add_scope_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--contact", required=True)
    parser.add_argument("--start-date", required=True, help="Inclusive YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="Inclusive YYYY-MM-DD")
    parser.add_argument("--batch-id")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    workspace = args.workspace
    try:
        if args.command == "doctor":
            return run_doctor(workspace)
        if args.command == "init-batch":
            path = init_batch(
                workspace,
                args.contact,
                args.start_date,
                args.end_date,
                args.batch_id,
            )
            print(path.root)
            return 0
        if args.command == "capture":
            if not args.acknowledge_visible_scope:
                raise ValueError(
                    "capture requires --acknowledge-visible-scope after verifying the authorized foreground chat"
                )
            path = capture_batch(
                workspace=workspace,
                batch_root=args.batch,
                region=parse_region(args.region),
                count=args.count,
                scroll_clicks=args.scroll_clicks,
                delay_seconds=args.delay_seconds,
                pre_capture_delay_seconds=args.pre_capture_delay_seconds,
                expected_process_names=(
                    tuple(args.expected_process_names)
                    if args.expected_process_names
                    else ("WeChat.exe", "Weixin.exe")
                ),
            )
            print(path)
            return 0
        if args.command == "ocr":
            path = ocr_batch(
                args.batch,
                workspace,
                device=args.device,
                lang=args.lang,
                limit=args.limit,
                capture_coverage_acknowledged=args.acknowledge_capture_coverage,
            )
            print(path)
            return 0
        if args.command == "normalize":
            path = normalize_batch(
                args.batch, workspace, min_confidence=args.min_confidence
            )
            print(path)
            return 0
        if args.command == "report":
            path = build_batch_report(args.batch, workspace)
            print(path)
            return 0
        if args.command == "prepare-online-review":
            path = prepare_online_review_request(
                args.batch, workspace, max_items=args.max_items
            )
            print(path)
            return 0
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        NotADirectoryError,
        OSError,
        PathSafetyError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    parser.error(f"Unknown command: {args.command}")
    return 2
