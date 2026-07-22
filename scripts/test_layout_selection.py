#!/usr/bin/env python3
"""Regression tests for choosing among WeChat layout candidates."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("select_wechat_layout.py")


class LayoutSelectionTests(unittest.TestCase):
    def test_selects_candidate_and_writes_decision(self):
        with tempfile.TemporaryDirectory() as raw:
            job = Path(raw)
            for profile in ("clean", "editorial", "visual"):
                (job / f"wechat-layout-{profile}.html").write_text(
                    f"<p style='color:red'>{profile}</p>", encoding="utf-8"
                )
            subprocess.run([
                sys.executable, str(SCRIPT), str(job),
                "--profile", "editorial", "--reason", "观点文章需要更强层级",
            ], check=True)
            selection = json.loads((job / "layout-selection.json").read_text(encoding="utf-8"))
            self.assertEqual(selection["selected_profile"], "editorial")
            self.assertEqual(
                (job / "wechat-formatted.html").read_bytes(),
                (job / "wechat-layout-editorial.html").read_bytes(),
            )
            self.assertIn("editorial", (job / "layout-decision.md").read_text(encoding="utf-8"))

    def test_requires_all_candidates(self):
        with tempfile.TemporaryDirectory() as raw:
            result = subprocess.run([
                sys.executable, str(SCRIPT), raw,
                "--profile", "clean", "--reason", "test",
            ], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing layout candidate", result.stderr)


if __name__ == "__main__":
    unittest.main()
