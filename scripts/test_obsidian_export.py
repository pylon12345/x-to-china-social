#!/usr/bin/env python3
"""Regression tests for Obsidian article, asset, and image-prompt export."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("export_to_obsidian.py")


class ObsidianExportTests(unittest.TestCase):
    def test_exports_each_image_prompt_as_a_separate_note(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job, vault = root / "job", root / "vault"
            job.mkdir()
            vault.mkdir()
            (job / "media" / "prompts").mkdir(parents=True)
            (job / "source.json").write_text(json.dumps({
                "source_url": "https://x.com/example/status/123",
                "status_id": "123",
                "author": {"name": "Example", "handle": "@example"},
            }), encoding="utf-8")
            (job / "wechat.md").write_text(
                "---\ntitle: 测试文章\n---\n\n# 测试文章\n\n正文\n",
                encoding="utf-8",
            )
            for number in (1, 2):
                (job / "media" / "prompts" / f"0{number}-image.md").write_text(
                    f"---\ntype: illustration\n---\n\n# Prompt {number}\n",
                    encoding="utf-8",
                )
            (job / "illustration-report.json").write_text(json.dumps({
                "status": "passed",
                "items": [
                    {
                        "source_media_id": f"media-0{number}",
                        "mode": "recreate",
                        "prompt_path": f"media/prompts/0{number}-image.md",
                        "output_path": f"media/0{number}-image.jpg",
                    }
                    for number in (1, 2)
                ],
            }), encoding="utf-8")

            subprocess.run([
                sys.executable, str(SCRIPT), str(job),
                "--vault", str(vault), "--platform", "wechat",
            ], check=True, capture_output=True, text=True)

            receipt = json.loads((job / "obsidian-receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(len(receipt["prompt_notes"]), 2)
            for prompt in receipt["prompt_notes"]:
                destination = Path(prompt["destination"])
                self.assertTrue(destination.is_file())
                self.assertIn("## 完整提示词", destination.read_text(encoding="utf-8"))
            article = Path(receipt["items"][0]["destination"]).read_text(encoding="utf-8")
            self.assertIn("## 配图提示词", article)
            self.assertEqual(article.count("X内容库/_prompts/"), 2)


if __name__ == "__main__":
    unittest.main()
