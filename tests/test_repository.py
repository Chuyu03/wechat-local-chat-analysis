from __future__ import annotations

import re
import unittest
from pathlib import Path

from support import REPOSITORY_ROOT


ALLOWED_TOP_LEVEL = {
    ".git",
    ".github",
    ".gitignore",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "SKILL.md",
    "THIRD_PARTY_NOTICES.md",
    "agents",
    "examples",
    "pyproject.toml",
    "references",
    "src",
    "tests",
}


class RepositoryBoundaryTests(unittest.TestCase):
    def test_public_tree_uses_the_declared_allowlist(self) -> None:
        unexpected = {
            child.name
            for child in REPOSITORY_ROOT.iterdir()
            if child.name not in ALLOWED_TOP_LEVEL and child.name != "__pycache__"
        }
        self.assertEqual(set(), unexpected)
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


if __name__ == "__main__":
    unittest.main()
