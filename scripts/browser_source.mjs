/**
 * Extract structured X/Twitter source evidence from a Codex in-app-browser tab.
 * Import this module from the persistent browser JavaScript runtime.
 */

import { mkdir, writeFile } from "node:fs/promises";
import { dirname } from "node:path";

function parseStatusUrl(raw) {
  const parsed = new URL(String(raw || "").trim());
  const match = parsed.pathname.replace(/\/$/, "").match(/^\/([^/]+)\/status\/(\d+)(?:\/.*)?$/);
  if (!match || !["x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"].includes(parsed.hostname.toLowerCase())) {
    throw new Error("expected an X/Twitter status permalink");
  }
  return {
    handle: match[1],
    statusId: match[2],
    sourceUrl: `https://x.com/${match[1]}/status/${match[2]}`,
    path: `/${match[1]}/status/${match[2]}`,
  };
}

function cleanText(value) {
  return String(value || "").replace(/\r\n?/g, "\n").replace(/[ \t]+\n/g, "\n").trim();
}

export function normalizeBrowserProjection(projection, sourceUrl, currentUrl) {
  const expected = parseStatusUrl(sourceUrl);
  const current = parseStatusUrl(currentUrl);
  if (current.statusId !== expected.statusId) {
    throw new Error(`browser tab status ${current.statusId} does not match ${expected.statusId}`);
  }
  if (!projection || !Array.isArray(projection.posts) || projection.posts.length === 0) {
    throw new Error("browser projection contains no posts");
  }
  const projectedHandle = String(projection.author?.handle || expected.handle).trim().replace(/^@/, "");
  if (projectedHandle.toLowerCase() !== expected.handle.toLowerCase()) {
    throw new Error(`page author @${projectedHandle} does not match URL @${expected.handle}`);
  }
  const posts = projection.posts.map((post, index) => {
    const text = cleanText(post?.text);
    const media = Array.isArray(post?.media) ? post.media.filter(Boolean) : [];
    if (!text && media.length === 0) {
      throw new Error(`browser post ${index + 1} has no text or media`);
    }
    return {
      text,
      media,
      timestamp: post?.timestamp || null,
    };
  });
  return {
    source_url: expected.sourceUrl,
    status_id: expected.statusId,
    author: {
      name: cleanText(projection.author?.name) || null,
      handle: `@${expected.handle}`,
    },
    posts,
    quoted_posts: [],
    acquisition: "browser",
    fetched_at: new Date().toISOString(),
    browser: {
      current_url: current.sourceUrl,
      strategy: "semantic-article-dom-v1",
      screenshot_used: false,
    },
  };
}

async function projectPage(tab, expected, includeThread) {
  return tab.playwright.evaluate((input) => {
    const clean = (value) => String(value || "")
      .replace(/\u00a0/g, " ")
      .replace(/[ \t]+/g, " ")
      .replace(/\s*\n\s*/g, "\n")
      .trim();
    const topLevelArticles = Array.from(document.querySelectorAll("main article"))
      .filter((article) => !article.parentElement?.closest("article"));
    const linkMatchesStatus = (article) => Array.from(article.querySelectorAll("a[href]"))
      .some((link) => {
        const href = link.getAttribute("href") || "";
        return href === input.path || href.startsWith(`${input.path}?`);
      });
    const primaryIndex = topLevelArticles.findIndex(linkMatchesStatus);
    const fallbackIndex = topLevelArticles.findIndex((article) => article.querySelector("h1, [data-testid='tweetText']"));
    const startIndex = primaryIndex >= 0 ? primaryIndex : fallbackIndex;
    if (startIndex < 0) {
      return { error: "primary article not found", posts: [] };
    }

    const authorFor = (article) => {
      const expectedHref = `/${input.handle}`.toLowerCase();
      const links = Array.from(article.querySelectorAll("a[href]"));
      const handleLink = links.find((link) => clean(link.textContent).toLowerCase() === `@${input.handle}`.toLowerCase());
      const nameLink = links.find((link) => {
        const href = (link.getAttribute("href") || "")
          .replace(/^https?:\/\/(?:www\.)?(?:x|twitter)\.com/i, "")
          .replace(/\/$/, "")
          .toLowerCase();
        const text = clean(link.textContent);
        return href === expectedHref && text && !text.startsWith("@") && text.toLowerCase() !== "user avatar";
      });
      return {
        name: clean(nameLink?.textContent) || null,
        handle: clean(handleLink?.textContent) || `@${input.handle}`,
      };
    };

    const mediaFor = (article) => {
      const items = [];
      const seen = new Set();
      const add = (url, altText, type) => {
        const target = String(url || "").trim();
        if (!target || seen.has(target)) return;
        seen.add(target);
        items.push({ url: target, alt_text: clean(altText) || null, type });
      };
      for (const img of article.querySelectorAll("img")) {
        if (img.closest("article") !== article) continue;
        const src = img.currentSrc || img.getAttribute("src") || "";
        const alt = img.getAttribute("alt") || "";
        const isContent = alt === "Article cover image" || src.includes("pbs.twimg.com/media") ||
          src.includes("pbs.twimg.com/ext_tw_video_thumb") || Boolean(img.closest("[data-testid='tweetPhoto']"));
        if (isContent && !/user avatar/i.test(alt)) add(src, alt, "image");
      }
      for (const video of article.querySelectorAll("video")) {
        if (video.closest("article") !== article) continue;
        add(video.getAttribute("poster") || video.getAttribute("src"), "Video", "video");
      }
      return items;
    };

    const textFor = (article) => {
      const title = article.querySelector("h1");
      if (!title) {
        const tweetText = article.querySelector("[data-testid='tweetText']");
        return clean(tweetText?.innerText || tweetText?.textContent);
      }
      const nodes = Array.from(article.querySelectorAll("h1,h2,h3,h4,h5,h6,p,li"))
        .filter((node) => node.closest("article") === article)
        .filter((node) => !(node.tagName !== "LI" && node.closest("li")));
      const firstTitle = nodes.indexOf(title);
      const selected = firstTitle >= 0 ? nodes.slice(firstTitle) : nodes;
      const lines = [];
      for (const node of selected) {
        const text = clean(node.innerText || node.textContent);
        if (!text) continue;
        const tag = node.tagName.toLowerCase();
        const prefix = /^h[1-6]$/.test(tag) ? `${"#".repeat(Number(tag[1]))} ` : tag === "li" ? "- " : "";
        const line = `${prefix}${text}`;
        if (lines[lines.length - 1] !== line) lines.push(line);
      }
      return lines.join("\n\n");
    };

    const primary = topLevelArticles[startIndex];
    const primaryAuthor = authorFor(primary);
    const selectedArticles = [];
    for (let index = startIndex; index < topLevelArticles.length; index += 1) {
      const article = topLevelArticles[index];
      const author = authorFor(article);
      if (index > startIndex && (!input.includeThread || author.handle.toLowerCase() !== primaryAuthor.handle.toLowerCase())) break;
      selectedArticles.push(article);
    }
    const posts = selectedArticles.map((article) => ({
      text: textFor(article),
      media: mediaFor(article),
      timestamp: article.querySelector("time[datetime]")?.getAttribute("datetime") || null,
    })).filter((post) => post.text || post.media.length);
    return { author: primaryAuthor, posts };
  }, {
    path: expected.path,
    handle: expected.handle,
    includeThread: Boolean(includeThread),
  }, { timeoutMs: 30000 });
}

export async function extractXSource(tab, options) {
  const sourceUrl = options?.sourceUrl;
  const outputPath = options?.outputPath;
  if (!tab || !sourceUrl || !outputPath) {
    throw new Error("extractXSource requires tab, sourceUrl, and outputPath");
  }
  const expected = parseStatusUrl(sourceUrl);
  const currentUrl = await tab.url();
  const projection = await projectPage(tab, expected, options?.includeThread !== false);
  if (projection?.error) throw new Error(projection.error);
  const data = normalizeBrowserProjection(projection, sourceUrl, currentUrl);
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, `${JSON.stringify(data, null, 2)}\n`, "utf8");
  return {
    outputPath,
    sourceUrl: data.source_url,
    author: data.author,
    postCount: data.posts.length,
    mediaCount: data.posts.reduce((total, post) => total + post.media.length, 0),
    contentChars: data.posts.reduce((total, post) => total + post.text.length, 0),
    acquisition: data.acquisition,
  };
}

export async function saveViewportScreenshot(tab, outputPath) {
  if (!tab || !outputPath) throw new Error("saveViewportScreenshot requires tab and outputPath");
  const bytes = await tab.screenshot({ fullPage: false });
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, bytes);
  return outputPath;
}
