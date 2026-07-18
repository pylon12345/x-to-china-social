#!/usr/bin/env python3
"""Regression tests for V8.2 report and remote-layout gates."""

import json
import tempfile
import unittest
from pathlib import Path

from manage_workflow import delivery_errors, report_errors
from publish_wechat_draft import layout_proof, unsupported_images


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class WorkflowGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.job = Path(self.temp.name)
        self.data = {"targets": ["wechat"], "delivery": {"mode": "full"}}

    def tearDown(self):
        self.temp.cleanup()

    def test_humanizer_gate(self):
        write(self.job / "humanization-report.json", {
            "status": "passed", "skill": "humanizer-zh",
            "targets": [{"target": "wechat", "status": "passed"}],
            "fidelity_checks": {
                "facts_preserved": True, "quotes_preserved": True,
                "source_links_preserved": True,
            },
        })
        self.assertEqual(report_errors(self.job, self.data, {"id": "rewrite"}), [])

    def test_guizang_illustration_skill_is_accepted(self):
        write(self.job / "illustration-report.json", {
            "status": "passed",
            "skills_used": ["guizang-material-illustration"],
            "items": [],
            "qa": {
                "facts_preserved": True, "originality": True,
                "mobile_readability": True,
            },
        })
        self.assertEqual(report_errors(self.job, self.data, {"id": "illustrate"}), [])

    def test_illustration_requires_skills_used(self):
        write(self.job / "illustration-report.json", {
            "status": "passed", "items": [],
            "qa": {
                "facts_preserved": True, "originality": True,
                "mobile_readability": True,
            },
        })
        errors = report_errors(self.job, self.data, {"id": "illustrate"})
        self.assertTrue(any("skills_used" in error for error in errors))

    def test_layout_gate_is_skipped_for_xiaohongshu_only(self):
        data = {"targets": ["xiaohongshu"], "delivery": {"mode": "fast"}}
        self.assertEqual(report_errors(self.job, data, {"id": "layout"}), [])

    def test_illustrate_accepts_renderer_and_optimizer_skills(self):
        write(self.job / "illustration-report.json", {
            "status": "passed",
            "skills_used": ["guizang-material-illustration", "imagegen", "baoyu-compress-image"],
            "items": [],
            "qa": {
                "facts_preserved": True, "originality": True,
                "mobile_readability": True,
            },
        })
        self.assertEqual(report_errors(self.job, self.data, {"id": "illustrate"}), [])

    def test_fast_mode_does_not_require_wechat_receipt(self):
        write(self.job / "obsidian-receipt.json", {
            "status": "saved", "items": [{"platform": "wechat"}],
        })
        data = {"targets": ["wechat"], "delivery": {"mode": "fast"}}
        self.assertEqual(delivery_errors(self.job, data, {"id": "sync"}), [])

    def test_full_mode_requires_remote_layout_proof(self):
        write(self.job / "obsidian-receipt.json", {
            "status": "saved", "items": [{"platform": "wechat"}],
        })
        write(self.job / "wechat-draft-receipt.json", {
            "status": "draft_saved", "mode": "official_api", "draft_id": "d1",
            "verified": True, "unresolved_images": [], "intended_images": [],
            "uploaded_images": [],
            "verification": {
                "title": True, "body_nonempty": True,
                "source_url": True, "adaptation_disclosure": True,
                "layout_preserved": False,
            },
            "remote_layout": {
                "inline_style_count": 0, "styled_heading_count": 0,
                "styled_paragraph_count": 0,
            },
        })
        self.assertTrue(delivery_errors(self.job, self.data, {"id": "sync"}))

    def test_sync_requires_each_image_prompt_in_obsidian(self):
        write(self.job / "illustration-report.json", {
            "status": "passed",
            "items": [{"prompt_path": "media/prompts/01-cover.md"}],
        })
        write(self.job / "obsidian-receipt.json", {
            "status": "saved", "items": [{"platform": "wechat"}],
            "prompt_notes": [],
        })
        data = {"targets": ["wechat"], "delivery": {"mode": "fast"}}
        errors = delivery_errors(self.job, data, {"id": "sync"})
        self.assertTrue(any("missing image prompts" in error for error in errors))

    def test_layout_proof_counts_inline_components(self):
        html = (
            '<h1 style="font-size:24px">标题</h1>'
            '<p style="line-height:1.8">第一段</p>'
            '<p style="line-height:1.8">第二段</p>'
            '<section style="color:#333">结尾</section>'
        )
        proof = layout_proof(html)
        self.assertEqual(proof["inline_style_count"], 4)
        self.assertEqual(proof["styled_heading_count"], 1)
        self.assertEqual(proof["styled_paragraph_count"], 2)

    def test_wechat_preflight_rejects_webp(self):
        unsupported = unsupported_images(
            [("media/image.webp", self.job / "image.webp")],
            self.job / "cover.jpg",
        )
        self.assertEqual(unsupported, [str(self.job / "image.webp")])


if __name__ == "__main__":
    unittest.main()
