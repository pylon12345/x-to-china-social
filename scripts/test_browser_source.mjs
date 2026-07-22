import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { extractXSource, normalizeBrowserProjection } from "./browser_source.mjs";

const URL = "https://x.com/example/status/1234567890";
const PROJECTION = {
  author: { name: "Example Person", handle: "@example" },
  posts: [{
    text: "# Example title\n\nA useful article.\n\n- First point",
    timestamp: "2026-07-22T01:00:00.000Z",
    media: [{ url: "https://pbs.twimg.com/media/example.jpg", alt_text: "Cover", type: "image" }],
  }],
};

test("normalizes a semantic browser projection", () => {
  const result = normalizeBrowserProjection(PROJECTION, URL, `${URL}?s=20`);
  assert.equal(result.source_url, URL);
  assert.equal(result.author.handle, "@example");
  assert.equal(result.acquisition, "browser");
  assert.equal(result.posts.length, 1);
  assert.equal(result.posts[0].media.length, 1);
});

test("writes structured evidence without printing full article text", async () => {
  const temporary = await mkdtemp(path.join(os.tmpdir(), "x-browser-source-"));
  try {
    const outputPath = path.join(temporary, "browser-source.json");
    const tab = {
      url: async () => URL,
      playwright: { evaluate: async () => PROJECTION },
    };
    const summary = await extractXSource(tab, { sourceUrl: URL, outputPath });
    const saved = JSON.parse(await readFile(outputPath, "utf8"));
    assert.equal(summary.contentChars > 0, true);
    assert.equal(summary.postCount, 1);
    assert.equal(saved.posts[0].text.includes("A useful article."), true);
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test("rejects a browser tab for another status", () => {
  assert.throws(
    () => normalizeBrowserProjection(PROJECTION, URL, "https://x.com/example/status/999"),
    /does not match/,
  );
});
