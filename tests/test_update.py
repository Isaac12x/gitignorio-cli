from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gitignore_cli.detect import detect_os_template
from gitignore_cli.file import GitignoreFile
from gitignore_cli.templates import get_store

CUSTOM_RULES = """\
# My custom rules
*.local
# Keep this line
"""


class UpdatePreservesCustomContentTests(unittest.TestCase):
    def test_append_templates_keeps_existing_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".gitignore"
            path.write_text(CUSTOM_RULES, encoding="utf-8")
            store = get_store()
            document = GitignoreFile.load(path, store)
            content = path.read_text(encoding="utf-8")
            os_template = detect_os_template()

            to_add: list[str] = []
            if not document.template_present(store, os_template, content):
                to_add.append(os_template)

            added = document.append_templates(store, to_add)
            updated = path.read_text(encoding="utf-8")

            self.assertEqual(added, [os_template])
            self.assertIn("# My custom rules", updated)
            self.assertIn("*.local", updated)
            self.assertIn("# Keep this line", updated)
            self.assertIn(f"### {store.section_title(os_template)} ###", updated)

    def test_append_templates_is_noop_when_nothing_to_add(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".gitignore"
            path.write_text(CUSTOM_RULES, encoding="utf-8")
            original = path.read_text(encoding="utf-8")
            store = get_store()
            document = GitignoreFile.load(path, store)

            added = document.append_templates(store, [])
            self.assertEqual(added, [])
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
