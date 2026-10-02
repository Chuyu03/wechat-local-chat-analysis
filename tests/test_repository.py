from __future__ import annotations

import re
import unittest
from pathlib import Path

from support import REPOSITORY_ROOT


ALLOWED_PUBLIC_FILES = {
    ".github/workflows/ci.yml",
    ".gitignore",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "SKILL.md",
    "THIRD_PARTY_NOTICES.md",
    "agents/openai.yaml",
    "examples/synthetic/README.md",
    "examples/synthetic/manifest.json",
    "examples/synthetic/messages.jsonl",
    "examples/synthetic/ocr/000001.json",
    "examples/synthetic/ocr/000002.json",
    "pyproject.toml",
    "references/analysis-reporting.md",
    "references/capture-workflow.md",
    "references/data-contract.md",
    "references/external-review.md",
    "references/local-pipeline.md",
    "src/wechat_analyse/__init__.py",
    "src/wechat_analyse/__main__.py",
    "src/wechat_analyse/capture.py",
    "src/wechat_analyse/cli.py",
    "src/wechat_analyse/config.py",
    "src/wechat_analyse/doctor.py",
    "src/wechat_analyse/normalize.py",
    "src/wechat_analyse/ocr.py",
    "src/wechat_analyse/ocr_local.py",
    "src/wechat_analyse/paths.py",
    "src/wechat_analyse/report.py",
    "tests/__init__.py",
    "tests/support.py",
    "tests/test_capture.py",
    "tests/test_cli_report.py",
    "tests/test_normalize.py",
    "tests/test_ocr.py",
    "tests/test_paths.py",
    "tests/test_repository.py",
}

REQUIRED_ANALYSIS_PROVENANCE_FIELDS = {
    "message_id",
    "source_image",
    "source_sha256",
    "bbox",
    "ocr_confidence",
    "review_status",
    "review_reasons",
}


class RepositoryBoundaryTests(unittest.TestCase):
    def test_public_tree_uses_the_declared_allowlist(self) -> None:
        self.assertEqual(ALLOWED_PUBLIC_FILES, _public_repository_files())
        for forbidden in ("data", "outputs", "analysis_reports", ".venv", ".codex"):
            self.assertFalse((REPOSITORY_ROOT / forbidden).exists(), forbidden)

    def test_public_text_has_no_private_machine_roots(self) -> None:
        forbidden_patterns = [
            re.compile(
                r"(?<![A-Za-z0-9])[A-Za-z]:\\(?:Users|Data|Documents|Projects)\\",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:NVIDIA|AMD|Intel)\s+GeForce\s+\w+\s+\d{4}\b",
                re.IGNORECASE,
            ),
        ]
        findings: list[str] = []
        for path in _public_text_files():
            text = path.read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                if pattern.search(text):
                    findings.append(f"{path.relative_to(REPOSITORY_ROOT)}: {pattern.pattern}")
        self.assertEqual([], findings)

    def test_relative_markdown_links_resolve_locally(self) -> None:
        missing: list[str] = []
        link_pattern = re.compile(r"\[[^\]]+\]\(([^)\s]+)(?:\s+[^)]*)?\)")
        for path in REPOSITORY_ROOT.rglob("*.md"):
            for target in link_pattern.findall(path.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                clean_target = target.split("#", 1)[0]
                if clean_target and not (path.parent / clean_target).resolve().exists():
                    missing.append(f"{path.relative_to(REPOSITORY_ROOT)} -> {target}")
        self.assertEqual([], missing)

    def test_ci_is_read_only_and_pins_official_actions(self) -> None:
        workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", workflow)
        self.assertIn("actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("upload-artifact", workflow)
        self.assertNotIn("actions/cache", workflow)

    def test_skill_metadata_is_complete_and_has_no_scaffold_markers(self) -> None:
        skill = (REPOSITORY_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---\nname: wechat-local-chat-analysis\n"))
        self.assertIn("\ndescription:", skill.split("---", 2)[1])
        metadata = (REPOSITORY_ROOT / "agents" / "openai.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("$wechat-local-chat-analysis", metadata)
        self.assertIn("allow_implicit_invocation: true", metadata)
        combined = skill + "\n" + metadata
        for marker in (
            "TO" + "DO",
            "YOUR" + "_USERNAME",
            "<" + "owner>",
            "PLACE" + "HOLDER",
        ):
            self.assertNotIn(marker, combined)

    def test_every_reference_is_progressively_disclosed_from_skill(self) -> None:
        skill = (REPOSITORY_ROOT / "SKILL.md").read_text(encoding="utf-8")
        linked_references = {
            target
            for target in re.findall(r"\[[^\]]+\]\((references/[^)#]+\.md)\)", skill)
        }
        available_references = {
            path.relative_to(REPOSITORY_ROOT).as_posix()
            for path in (REPOSITORY_ROOT / "references").glob("*.md")
        }
        self.assertEqual(available_references, linked_references)

    def test_analysis_guide_is_bound_to_normalized_evidence(self) -> None:
        guide = (REPOSITORY_ROOT / "references" / "analysis-reporting.md").read_text(
            encoding="utf-8"
        )
        code_terms = set(re.findall(r"`([a-z][a-z0-9_]*)`", guide))
        self.assertTrue(REQUIRED_ANALYSIS_PROVENANCE_FIELDS <= code_terms)

        workflow = (REPOSITORY_ROOT / "SKILL.md").read_text(encoding="utf-8").split(
            "## Default workflow", 1
        )[1].split("## Analysis rules", 1)[0]
        analysis_step = next(
            line for line in workflow.splitlines() if "analysis-reporting.md" in line
        )
        self.assertIn("normalized JSONL", analysis_step)
        self.assertIn("claim-level provenance", analysis_step)

        self.assertIn("`created_at` records pipeline processing time", guide)
        self.assertIn("`review_status` is a queue state", guide)
        self.assertIn("The CLI `report` command creates a raw evidence index", guide)

    def test_example_files_are_explicitly_synthetic(self) -> None:
        examples = REPOSITORY_ROOT / "examples" / "synthetic"
        self.assertTrue(examples.is_dir())
        for path in examples.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".md", ".json", ".jsonl"}:
                self.assertIn("synthetic", path.read_text(encoding="utf-8").lower(), str(path))


def _public_text_files() -> list[Path]:
    suffixes = {".md", ".py", ".toml", ".yaml", ".yml", ".json", ".jsonl", ".csv"}
    return [
        path
        for path in REPOSITORY_ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in suffixes and ".git" not in path.parts
    ]


def _public_repository_files() -> set[str]:
    return {
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in REPOSITORY_ROOT.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and "__pycache__" not in path.parts
        and path.suffix.lower() != ".pyc"
    }


if __name__ == "__main__":
    unittest.main()
