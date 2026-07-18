#!/usr/bin/env python3
"""Regression tests for the pure helpers inside publish_wechat_draft."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from publish_wechat_draft import local_path, remote_verification, reusable_uploads


class LocalPathTests(unittest.TestCase):
    def test_relative_src_resolves_next_to_html(self):
        html = Path("C:/job/wechat-formatted.html")
        self.assertEqual(local_path("media/a.png", html), Path("C:/job/media/a.png").resolve())

    def test_percent_encoded_src_is_decoded(self):
        html = Path("C:/job/wechat-formatted.html")
        self.assertEqual(
            local_path("media/my%20image.png", html),
            Path("C:/job/media/my image.png").resolve(),
        )

    def test_remote_src_is_ignored(self):
        self.assertIsNone(local_path("https://example.com/a.png", Path("C:/job/x.html")))


class RemoteVerificationTests(unittest.TestCase):
    def test_matching_draft_passes(self):
        html = (
            '<h1 style="font-size:24px">标题</h1>'
            '<p style="line-height:1.8">' + "基于原文改写的正文。" * 10 + "</p>"
            '<p style="line-height:1.8">来源说明段落，' + "补充内容。" * 10 + "</p>"
            '<p style="color:#555">https://x.com/user/status/1</p>'
        )
        item = {"title": "标题", "content": html, "content_source_url": "https://x.com/user/status/1"}
        with tempfile.TemporaryDirectory() as temp:
            checks, _remote, _local = remote_verification(
                Path(temp), html, item, "标题", "https://x.com/user/status/1"
            )
        self.assertEqual([name for name, ok in checks.items() if not ok], [])

    def test_lost_layout_fails(self):
        local = '<p style="a">x</p>' * 6
        item = {"title": "t", "content": "<p>" + "字" * 100 + "</p>", "content_source_url": ""}
        with tempfile.TemporaryDirectory() as temp:
            checks, _remote, _local = remote_verification(Path(temp), local, item, "t", "")
        self.assertFalse(checks["layout_preserved"])


class ReusableUploadsTests(unittest.TestCase):
    def test_unchanged_image_is_reused_and_changed_image_is_not(self):
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            (job / "media").mkdir()
            same, changed = job / "media" / "same.png", job / "media" / "changed.png"
            same.write_bytes(b"same-bytes")
            changed.write_bytes(b"new-bytes")
            prior = {"uploaded_images": [
                {"local_path": "media/same.png", "remote_url": "https://mmbiz/1",
                 "sha256": hashlib.sha256(b"same-bytes").hexdigest()},
                {"local_path": "media/changed.png", "remote_url": "https://mmbiz/2",
                 "sha256": hashlib.sha256(b"old-bytes").hexdigest()},
            ]}
            images = [("media/same.png", same), ("media/changed.png", changed)]
            reusable = reusable_uploads(prior, images, job)
        self.assertEqual(list(reusable), ["media/same.png"])
        self.assertEqual(reusable["media/same.png"]["remote_url"], "https://mmbiz/1")

    def test_prior_without_hashes_is_never_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            image = job / "a.png"
            image.write_bytes(b"bytes")
            prior = {"uploaded_images": [{"local_path": "a.png", "remote_url": "https://mmbiz/1"}]}
            self.assertEqual(reusable_uploads(prior, [("a.png", image)], job), {})


if __name__ == "__main__":
    unittest.main()
