#!/usr/bin/env python3
"""Regression tests for deterministic, cache-aware source acquisition."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("build_source.py")
URL = "https://x.com/example/status/1234567890"


class SourceAcquisitionTests(unittest.TestCase):
    def extractor_markdown(self, body="A useful post."):
        return "\n".join([
            "---",
            f'url: {json.dumps(URL)}',
            f'requestedUrl: {json.dumps(URL)}',
            'author: "Example Person (@example)"',
            'authorName: "Example Person"',
            'authorUsername: "example"',
            "tweetCount: 1",
            'coverImage: "https://pbs.twimg.com/media/cover.jpg"',
            "---",
            "",
            body,
            "",
            "![Diagram](https://pbs.twimg.com/media/diagram.png)",
            "",
        ])

    def run_builder(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            text=True, capture_output=True, encoding="utf-8",
        )

    def test_imports_extractor_markdown_without_model_reshaping(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "source-raw.md"
            output = root / "job"
            raw.write_text(self.extractor_markdown(), encoding="utf-8")
            result = self.run_builder(raw, "--source-url", URL, "--output-dir", output)
            self.assertEqual(result.returncode, 0, result.stderr)

            source = json.loads((output / "source.json").read_text(encoding="utf-8"))
            index = json.loads((output / "source-index.json").read_text(encoding="utf-8"))
            rendered = (output / "source.md").read_text(encoding="utf-8")
            self.assertEqual(source["author"]["handle"], "@example")
            self.assertEqual(len(source["posts"][0]["media"]), 2)
            self.assertIn("[Image: Diagram]", source["posts"][0]["text"])
            self.assertNotIn("diagram.png)", source["posts"][0]["text"])
            self.assertEqual(index["reading_strategy"], "single_pass")
            self.assertIn("A useful post.", rendered)

    def test_cache_probe_detects_hit_and_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "source-raw.md"
            output = root / "job"
            raw.write_text(self.extractor_markdown(), encoding="utf-8")
            built = self.run_builder(raw, "--source-url", URL, "--output-dir", output)
            self.assertEqual(built.returncode, 0, built.stderr)

            hit = self.run_builder(
                "--check-existing", "--source-url", URL, "--output-dir", output,
            )
            self.assertEqual(hit.returncode, 0, hit.stderr)
            self.assertEqual(json.loads(hit.stdout)["cache"], "hit")

            with (output / "source.md").open("a", encoding="utf-8") as stream:
                stream.write("tampered\n")
            miss = self.run_builder(
                "--check-existing", "--source-url", URL, "--output-dir", output,
            )
            self.assertEqual(miss.returncode, 3)
            self.assertIn("cache miss", miss.stderr)

    def test_long_sources_are_indexed_into_parts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "source-raw.md"
            output = root / "job"
            body = "\n\n".join(f"## Section {i}\n" + ("content " * 500) for i in range(6))
            raw.write_text(self.extractor_markdown(body), encoding="utf-8")
            result = self.run_builder(raw, "--source-url", URL, "--output-dir", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            index = json.loads((output / "source-index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["reading_strategy"], "indexed_parts")
            self.assertGreater(len(index["parts"]), 1)
            self.assertTrue(all((output / item).is_file() for item in index["parts"]))


if __name__ == "__main__":
    unittest.main()
