#!/usr/bin/env python3
"""Regression tests for platform and delivery routing."""

import json
import tempfile
import unittest
from pathlib import Path

from init_workflow import (
    resolve_delivery, resolve_platform, stage_definitions, upgrade_delivery,
)


class PlatformRoutingTests(unittest.TestCase):
    def test_platform_triggers(self):
        cases = {
            "帮我改写这篇": "wechat",
            "保存到公众号草稿箱": "wechat",
            "只做小红书": "xiaohongshu",
            "公众号和小红书都要": "both",
            "不要小红书，只做公众号": "wechat",
            "不要公众号，只做小红书": "xiaohongshu",
            "不要同时写公众号和小红书": "wechat",
            "WeChat + XHS": "both",
        }
        for request, expected in cases.items():
            with self.subTest(request=request):
                self.assertEqual(resolve_platform("auto", request)[0], expected)

    def test_explicit_platform_wins(self):
        self.assertEqual(resolve_platform("wechat", "只做小红书"), ("wechat", "explicit"))

    def test_delivery_defaults_fast_and_detects_full(self):
        self.assertEqual(resolve_delivery("auto", "帮我改写"), ("fast", "default"))
        self.assertEqual(resolve_delivery("auto", "保存到公众号草稿箱"), ("full", "trigger"))
        self.assertEqual(resolve_delivery("auto", "只做本地，不要同步"), ("fast", "trigger"))

    def test_target_and_delivery_artifacts(self):
        wechat_fast = dict(stage_definitions(["wechat"], "fast"))
        wechat_full = dict(stage_definitions(["wechat"], "full"))
        xhs = dict(stage_definitions(["xiaohongshu"], "fast"))
        self.assertIn("humanization-report.json", wechat_fast["rewrite"])
        self.assertIn("layout-validation.json", wechat_fast["layout"])
        self.assertEqual(wechat_fast["sync"], ["obsidian-receipt.json"])
        self.assertIn("wechat-draft-receipt.json", wechat_full["sync"])
        self.assertEqual(xhs["layout"], [])
        self.assertEqual(xhs["sync"], ["obsidian-receipt.json"])

    def test_completed_fast_ledger_can_upgrade_to_full(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "workflow-state.json"
            state = {
                "targets": ["wechat"],
                "delivery": {"mode": "fast"},
                "overall_status": "preview_ready",
                "current_stage": None,
                "stages": [
                    {"id": "sync", "status": "completed",
                     "required_artifacts": ["obsidian-receipt.json"],
                     "completed_at": "done", "note": None},
                    {"id": "review", "status": "completed",
                     "required_artifacts": [], "completed_at": "done", "note": None},
                ],
            }
            path.write_text(json.dumps(state), encoding="utf-8")
            self.assertTrue(upgrade_delivery(path, state, "full", "trigger", "发到草稿"))
            upgraded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(upgraded["delivery"]["mode"], "full")
            self.assertEqual(upgraded["current_stage"], "sync")
            sync = next(stage for stage in upgraded["stages"] if stage["id"] == "sync")
            self.assertIn("wechat-draft-receipt.json", sync["required_artifacts"])


if __name__ == "__main__":
    unittest.main()
