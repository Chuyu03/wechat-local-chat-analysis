from __future__ import annotations

import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support import SOURCE_ROOT, add_synthetic_ocr, read_jsonl
from wechat_analyse.cli import main
from wechat_analyse.normalize import normalize_batch
from wechat_analyse.paths import init_batch
from wechat_analyse.report import render_report
from wechat_analyse.report import build_batch_report, prepare_online_review_request


class CliTests(unittest.TestCase):
    def _run_module(self, workspace: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SOURCE_ROOT)
        return subprocess.run(
            [sys.executable, "-m", "wechat_analyse", "--workspace", str(workspace), *arguments],
            cwd=workspace,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def test_module_help_lists_every_public_command(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = self._run_module(Path(temporary), "--help")
        self.assertEqual(0, result.returncode, result.stderr)
        for command in (
            "doctor",
            "init-batch",
            "capture",
            "ocr",
            "normalize",
            "report",
            "prepare-online-review",
        ):
            self.assertIn(command, result.stdout)

    @unittest.skipUnless(sys.platform == "win32", "The v0.1.0 doctor supports Windows only")
    def test_doctor_is_diagnostic_when_optional_dependencies_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            result = self._run_module(workspace, "doctor")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(str(workspace.resolve()), result.stdout)
        self.assertIn("Python", result.stdout)


class OfflineReportTests(unittest.TestCase):
    def test_render_report_keeps_same_text_from_different_sources(self) -> None:
        records = [
            {
                "message_id": "synthetic-001",
                "speaker": "other",
                "content_text": "Synthetic repeated report message",
                "content_type": "text",
                "ocr_confidence": 0.4,
                "review_status": "needs_review",
            },
            {
                "message_id": "synthetic-002",
                "speaker": "other",
                "content_text": "Synthetic repeated report message",
                "content_type": "text",
                "ocr_confidence": 0.5,
                "review_status": "needs_review",
            },
        ]
        report = render_report("synthetic-contact", records)
        self.assertIn("2", report)
        self.assertIn("synthetic-001", report)
        self.assertIn("synthetic-002", report)

    def test_cli_builds_report_from_local_synthetic_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = init_batch(
                workspace,
                "Synthetic Contact",
                "2040-01-01",
                "2040-01-02",
                batch_id="synthetic-report",
            )
            add_synthetic_ocr(
                workspace=workspace,
                batch_paths=paths,
                stem="000001",
                text="Synthetic local report content",
                confidence=0.42,
                source_sha256="c" * 64,
            )
            messages = normalize_batch(paths.root, workspace, min_confidence=0.85)
            self.assertEqual(1, len(read_jsonl(messages)))

            exit_code = main(
                ["--workspace", str(workspace), "report", "--batch", str(paths.root)]
            )
            self.assertEqual(0, exit_code)
            reports = list(workspace.rglob("report.md"))
            self.assertEqual(1, len(reports))
            self.assertIn("Synthetic local report content", reports[0].read_text(encoding="utf-8"))

    def test_report_and_review_candidate_stay_inside_one_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            first = init_batch(
                workspace,
                "Synthetic Contact",
                "2040-01-01",
                "2040-01-01",
                batch_id="synthetic-first-scope",
            )
            second = init_batch(
                workspace,
                "Synthetic Contact",
                "2040-01-02",
                "2040-01-02",
                batch_id="synthetic-second-scope",
            )
            add_synthetic_ocr(
                workspace=workspace,
                batch_paths=first,
                stem="000001",
                text="Synthetic first batch only",
                confidence=0.4,
            )
            add_synthetic_ocr(
                workspace=workspace,
                batch_paths=second,
                stem="000001",
                text="Synthetic second batch only",
                confidence=0.4,
            )
            normalize_batch(first.root, workspace)
            normalize_batch(second.root, workspace)

            report_path = build_batch_report(first.root, workspace)
            candidate_path = prepare_online_review_request(first.root, workspace)
            report_text = report_path.read_text(encoding="utf-8")
            candidate = json.loads(candidate_path.read_text(encoding="utf-8"))

            self.assertIn("Synthetic first batch only", report_text)
            self.assertNotIn("Synthetic second batch only", report_text)
            candidate_text = json.dumps(candidate, ensure_ascii=False)
            self.assertIn("Synthetic first batch only", candidate_text)
            self.assertNotIn("Synthetic second batch only", candidate_text)
            self.assertEqual("synthetic-first-scope", candidate["batch_id"])
            self.assertFalse(candidate["redacted"])

    def test_report_rejects_normalized_jsonl_changed_after_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = init_batch(
                workspace,
                "Synthetic Contact",
                "2040-01-01",
                "2040-01-02",
                batch_id="synthetic-tampered-report",
            )
            add_synthetic_ocr(
                workspace=workspace,
                batch_paths=paths,
                stem="000001",
                text="Synthetic original evidence",
                confidence=0.99,
            )
            messages = normalize_batch(paths.root, workspace)
            messages.write_text(
                messages.read_text(encoding="utf-8").replace(
                    "Synthetic original evidence", "Synthetic tampered evidence"
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                build_batch_report(paths.root, workspace)


if __name__ == "__main__":
    unittest.main()
