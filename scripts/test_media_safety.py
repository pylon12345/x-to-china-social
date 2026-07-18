#!/usr/bin/env python3
"""Regression tests for save_media URL safety checks."""

import unittest

from save_media import safe_url


class SafeUrlTests(unittest.TestCase):
    def test_rejects_literal_private_and_loopback_ips(self):
        for url in ("http://127.0.0.1/a.jpg", "http://10.0.0.5/a.jpg",
                    "http://169.254.1.1/a.jpg", "http://[::1]/a.jpg"):
            with self.assertRaises(RuntimeError):
                safe_url(url)

    def test_rejects_hostname_resolving_to_loopback(self):
        with self.assertRaises(RuntimeError):
            safe_url("http://localhost/a.jpg")

    def test_rejects_non_http_schemes(self):
        for url in ("file:///etc/passwd", "ftp://example.com/a.jpg", "not-a-url"):
            with self.assertRaises(RuntimeError):
                safe_url(url)

    def test_accepts_public_literal_ip(self):
        self.assertEqual(safe_url("https://93.184.216.34/a.jpg"), "https://93.184.216.34/a.jpg")


if __name__ == "__main__":
    unittest.main()
