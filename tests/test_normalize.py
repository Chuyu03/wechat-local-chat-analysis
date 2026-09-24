from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from support import add_synthetic_ocr, read_jsonl, write_json
from wechat_analyse.normalize import normalize_batch, sanitize_csv_cell, write_review_csv
from wechat_analyse.paths import init_batch


class CsvSafetyTests(unittest.TestCase):
    def test_formula_triggering_prefixes_are_neutralized(self) -> None:
        dangerous = [
            "=1+1",
            "+SUM(1,1)",
            "-2+3",
            "@synthetic",
            "\t=1+1",
            "\r=1+1",
        ]
        for value in dangerous:
            with self.subTest(value=repr(value)):
                sanitized = sanitize_csv_cell(value)
                self.assertTrue(sanitized.startswith("'"), repr(sanitized))
                self.assertEqual(value, sanitized[1:])
        self.assertEqual("ordinary synthetic text", sanitize_csv_cell("ordinary synthetic text"))

    def test_csv_writer_applies_neutralization_to_untrusted_text(self) -> None:
        record = {
            "message_id": "synthetic-001",
            "review_status": "needs_review",
            "ocr_confidence": 0.5,
            "speaker": "unknown",
            "content_text": "=HYPERLINK(\"https://invalid.example\",\"synthetic\")",
            "source_image": "data/synthetic/000001.png",
            "bbox": [[1, 1], [2, 2]],
        }
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "review.csv"
            write_review_csv(target, [record])
            with target.open("r", encoding="utf-8-sig", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertTrue(row["content_text"].startswith("'="))


class NormalizeTests(unittest.TestCase):
    def _new_batch(self, workspace: Path):
        return init_batch(
            workspace,
            "Synthetic Contact",
            "2040-01-01",
            "2040-01-02",
            batch_id="synthetic-batch",
        )

    def test_same_text_from_distinct_screenshots_is_preserved_and_reviewed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = self._new_batch(workspace)
            add_synthetic_ocr(
                workspace=workspace,
                batch_paths=paths,
                stem="000001",
                text="Synthetic repeated message",
                confidence=0.99,
                source_sha256="1" * 64,
            )
            add_synthetic_ocr(
                workspace=workspace,
                batch_paths=paths,
                stem="000002",
                text="Synthetic repeated message",
                confidence=0.99,
                source_sha256="2" * 64,
            )

            records = read_jsonl(normalize_batch(paths.root, workspace, min_confidence=0.85))

            self.assertEqual(2, len(records))
            self.assertEqual(
                ["Synthetic repeated message", "Synthetic repeated message"],
                [record["content_text"] for record in records],
            )
            self.assertTrue(all(record["review_status"] == "needs_review" for record in records))
            self.assertTrue(
                all(
                    any("overlap" in reason for reason in record.get("review_reasons", []))
                    for record in records
                )
            )

    def test_identical_screenshot_hash_is_definitively_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = self._new_batch(workspace)
            for stem in ("000001", "000002"):
                add_synthetic_ocr(
                    workspace=workspace,
                    batch_paths=paths,
                    stem=stem,
                    text="Synthetic duplicate screenshot content",
                    confidence=0.99,
                    source_sha256="a" * 64,
                )

            records = read_jsonl(normalize_batch(paths.root, workspace, min_confidence=0.85))
            self.assertEqual(1, len(records))

    def test_low_confidence_item_enters_review_without_losing_raw_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = self._new_batch(workspace)
            raw_text = "Synthetic OCR raw text = still preserved in JSONL"
            add_synthetic_ocr(
                workspace=workspace,
                batch_paths=paths,
                stem="000001",
                text=raw_text,
                confidence=0.42,
                source_sha256="b" * 64,
            )

            records = read_jsonl(normalize_batch(paths.root, workspace, min_confidence=0.85))
            self.assertEqual(1, len(records))
            self.assertEqual(raw_text, records[0]["content_text"])
            self.assertEqual("needs_review", records[0]["review_status"])
            self.assertTrue(any("confidence" in reason for reason in records[0]["review_reasons"]))

    def test_unregistered_stale_ocr_file_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = self._new_batch(workspace)
            add_synthetic_ocr(
                workspace=workspace,
                batch_paths=paths,
                stem="000001",
                text="Synthetic current OCR",
                confidence=0.99,
                source_sha256="d" * 64,
            )
            write_json(
                paths.ocr / "stale.json",
                {
                    "schema_version": 1,
                    "source_image": "data/stale.png",
                    "source_sha256": "e" * 64,
                    "image_size": [100, 100],
                    "items": [{"index": 1, "text": "Synthetic stale OCR", "confidence": 0.99}],
                },
            )

            records = read_jsonl(normalize_batch(paths.root, workspace))

            self.assertEqual(["Synthetic current OCR"], [record["content_text"] for record in records])

    def test_rejects_screenshot_replaced_after_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = self._new_batch(workspace)
            add_synthetic_ocr(
                workspace=workspace,
                batch_paths=paths,
                stem="000001",
                text="Synthetic evidence",
                confidence=0.99,
                source_sha256="f" * 64,
            )
            (paths.screenshots / "000001.png").write_bytes(b"synthetic replacement")

            with self.assertRaises(ValueError):
                normalize_batch(paths.root, workspace)

    def test_rejects_ocr_json_changed_after_registration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = self._new_batch(workspace)
            ocr_path = add_synthetic_ocr(
                workspace=workspace,
                batch_paths=paths,
                stem="000001",
                text="Synthetic registered OCR",
                confidence=0.99,
                source_sha256="0" * 64,
            )
            payload = json.loads(ocr_path.read_text(encoding="utf-8"))
            payload["items"][0]["text"] = "Synthetic tampered OCR"
            write_json(ocr_path, payload)

            with self.assertRaises(ValueError):
                normalize_batch(paths.root, workspace)


if __name__ == "__main__":
    unittest.main()
