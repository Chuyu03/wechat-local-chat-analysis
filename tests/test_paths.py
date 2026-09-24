from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import REPOSITORY_ROOT  # noqa: F401 - also installs src on sys.path
from wechat_analyse.paths import (
    init_batch,
    load_manifest,
    resolve_within,
    resolve_workspace,
)


class PathSafetyTests(unittest.TestCase):
    def test_rejects_workspace_inside_public_source_tree(self) -> None:
        with self.assertRaises(ValueError):
            resolve_workspace(REPOSITORY_ROOT)
        with self.assertRaises(ValueError):
            resolve_workspace(REPOSITORY_ROOT / "private-workspace")

    def test_rejects_path_traversal_and_absolute_outside_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            workspace.mkdir()
            outside = Path(temporary) / "outside"
            outside.mkdir()

            malicious = [
                "../outside",
                "..\\outside",
                str(outside.resolve()),
            ]
            for candidate in malicious:
                with self.subTest(candidate=candidate):
                    with self.assertRaises((ValueError, OSError)):
                        resolve_within(workspace, candidate)

    def test_rejects_batch_ids_that_are_not_single_safe_segments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            for batch_id in ("", ".", "..", "../escape", "..\\escape", "bad/name", "bad\\name"):
                with self.subTest(batch_id=batch_id):
                    with self.assertRaises(ValueError):
                        init_batch(
                            workspace,
                            "Synthetic Contact",
                            "2040-01-01",
                            "2040-01-02",
                            batch_id=batch_id,
                        )

    def test_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            outside = root / "outside"
            outside.mkdir()
            link = workspace / "escape"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"Directory symlinks are unavailable in this environment: {exc}")

            with self.assertRaises((ValueError, OSError)):
                resolve_within(workspace, "escape/child.json")

    def test_dates_are_strict_iso_and_ordered(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            invalid_ranges = [
                ("2040-1-01", "2040-01-02"),
                ("2040-02-30", "2040-03-01"),
                ("2040-01-03", "2040-01-02"),
            ]
            for start_date, end_date in invalid_ranges:
                with self.subTest(start_date=start_date, end_date=end_date):
                    with self.assertRaises(ValueError):
                        init_batch(
                            workspace,
                            "Synthetic Contact",
                            start_date,
                            end_date,
                            batch_id="synthetic-batch",
                        )

            paths = init_batch(
                workspace,
                "Synthetic Contact",
                "2040-02-29",
                "2040-02-29",
                batch_id="synthetic-leap-day",
            )
            self.assertTrue(paths.manifest.is_file())

    def test_manifest_contains_only_workspace_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = init_batch(
                workspace,
                "Synthetic Contact",
                "2040-01-01",
                "2040-01-02",
                batch_id="synthetic-batch",
            )
            manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))

            self.assertEqual(1, manifest["schema_version"])
            self.assertNotIn(str(workspace.resolve()), paths.manifest.read_text(encoding="utf-8"))
            self.assertTrue(paths.root.resolve().is_relative_to(workspace.resolve()))
            for value in _string_leaves(manifest):
                self.assertFalse(Path(value).is_absolute(), value)

    def test_manifest_cannot_redirect_one_batch_to_another(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            first = init_batch(
                workspace,
                "Synthetic Contact A",
                "2040-01-01",
                "2040-01-02",
                batch_id="synthetic-first",
            )
            second = init_batch(
                workspace,
                "Synthetic Contact B",
                "2040-01-01",
                "2040-01-02",
                batch_id="synthetic-second",
            )
            manifest = json.loads(first.manifest.read_text(encoding="utf-8"))
            manifest["paths"]["ocr"] = second.ocr.relative_to(workspace).as_posix()
            first.manifest.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                load_manifest(first.root, workspace)


def _string_leaves(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for child in value.values():
            result.extend(_string_leaves(child))
        return result
    if isinstance(value, list):
        result = []
        for child in value:
            result.extend(_string_leaves(child))
        return result
    return []


if __name__ == "__main__":
    unittest.main()
