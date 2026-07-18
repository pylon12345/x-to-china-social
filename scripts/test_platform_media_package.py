#!/usr/bin/env python3
"""Regression tests for platform-specific media/prompt packages."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("build_platform_media_package.py")


class PlatformMediaPackageTests(unittest.TestCase):
    def test_builds_separate_packages_without_putting_prompts_in_article(self):
        with tempfile.TemporaryDirectory() as raw:
            job = Path(raw)
            (job / "media").mkdir()
            (job / "media" / "card.jpg").write_bytes(b"image")
            (job / "media" / "card.prompt.md").write_text("draw a clean card", encoding="utf-8")
            (job / "wechat.md").write_text("# Article\n\nReader-facing copy only.\n", encoding="utf-8")
            (job / "workflow-state.json").write_text(json.dumps({
                "targets": ["wechat"],
            }), encoding="utf-8")
            (job / "illustration-report.json").write_text(json.dumps({
                "status": "passed",
                "items": [{
                    "source_media_id": "media-01",
                    "mode": "recreate",
                    "output_path": "media/card.jpg",
                    "prompt_path": "media/card.prompt.md",
                }],
            }), encoding="utf-8")

            subprocess.run([sys.executable, str(SCRIPT), str(job)], check=True)
            package = json.loads((job / "platform-media-package.json").read_text(encoding="utf-8"))
            item = package["platforms"]["wechat"]["items"][0]
            self.assertEqual(item["image_path"], "media/card.jpg")
            self.assertEqual(item["prompt_path"], "media/card.prompt.md")
            self.assertFalse(package["platforms"]["wechat"]["article_contains_prompts"])

    def test_rejects_full_prompt_embedded_in_article(self):
        with tempfile.TemporaryDirectory() as raw:
            job = Path(raw)
            (job / "image.jpg").write_bytes(b"image")
            (job / "prompt.md").write_text("private generation prompt", encoding="utf-8")
            (job / "wechat.md").write_text("private generation prompt", encoding="utf-8")
            (job / "workflow-state.json").write_text(json.dumps({"targets": ["wechat"]}), encoding="utf-8")
            (job / "illustration-report.json").write_text(json.dumps({
                "status": "passed", "items": [{
                    "output_path": "image.jpg", "prompt_path": "prompt.md"
                }]
            }), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(job)], capture_output=True, text=True
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("contains the full prompt", result.stderr)


if __name__ == "__main__":
    unittest.main()
