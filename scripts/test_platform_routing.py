#!/usr/bin/env python3
"""Regression tests for platform-trigger routing and target-aware artifacts."""

import unittest

from init_workflow import resolve_platform, stage_definitions


class PlatformRoutingTests(unittest.TestCase):
    def test_trigger_archive(self):
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

    def test_target_specific_artifacts(self):
        wechat = dict(stage_definitions(["wechat"]))
        xhs = dict(stage_definitions(["xiaohongshu"]))
        self.assertEqual(wechat["rewrite"], ["wechat-draft.md", "wechat.md"])
        self.assertEqual(xhs["rewrite"], ["xiaohongshu-draft.md", "xiaohongshu.md"])
        self.assertEqual(xhs["layout"], [])
        self.assertEqual(xhs["sync"], ["obsidian-receipt.json"])


if __name__ == "__main__":
    unittest.main()
