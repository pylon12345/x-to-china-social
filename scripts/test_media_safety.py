#!/usr/bin/env python3
"""Regression tests for save_media URL safety checks."""

import unittest
from unittest import mock

import save_media
from save_media import safe_url


class SafeUrlTests(unittest.TestCase):
    def test_rejects_literal_private_and_loopback_ips(self):
        for url in ("http://127.0.0.1/a.jpg", "http://10.0.0.5/a.jpg",
                    "http://169.254.1.1/a.jpg", "http://[::1]/a.jpg"):
            with self.assertRaises(RuntimeError):
                safe_url(url)

    def test_rejects_hostname_resolving_to_loopback(self):
        with mock.patch.object(save_media, "getproxies", return_value={}):
            with self.assertRaises(RuntimeError):
                safe_url("http://localhost/a.jpg")

    def test_proxy_skips_local_hostname_resolution(self):
        proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
        with mock.patch.object(save_media, "getproxies", return_value=proxies):
            with mock.patch.object(save_media.socket, "getaddrinfo",
                                   side_effect=AssertionError("must not resolve")):
                self.assertEqual(safe_url("https://example.com/a.jpg"),
                                 "https://example.com/a.jpg")
        # Literal private IPs stay rejected even behind a proxy.
        with mock.patch.object(save_media, "getproxies", return_value=proxies):
            with self.assertRaises(RuntimeError):
                safe_url("http://127.0.0.1/a.jpg")

    def test_rejects_non_http_schemes(self):
        for url in ("file:///etc/passwd", "ftp://example.com/a.jpg", "not-a-url"):
            with self.assertRaises(RuntimeError):
                safe_url(url)

    def test_accepts_public_literal_ip(self):
        self.assertEqual(safe_url("https://93.184.216.34/a.jpg"), "https://93.184.216.34/a.jpg")


if __name__ == "__main__":
    unittest.main()
