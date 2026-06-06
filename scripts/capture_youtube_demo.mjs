/**
 * Capture YouTube-lecture RAG demo frames from the live DocuMind UI.
 *
 * Records two flows:
 *   1. Ingest: paste URL -> progress stages (transcribe, slides) -> indexed
 *   2. Slide-scoped Q&A: "what did the author say about slide N" -> cited answer
 *
 * Usage (stack up at http://localhost, TRANSCRIBER_PROVIDER=openai):
 *   node scripts/capture_youtube_demo.mjs
 *
 * Frames -> docs/images/yt_frames/ingest/*.png and .../qa/*.png
 */
import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PLUGIN_ROOT =
  process.env.BROWSE_PLUGIN_ROOT ??
  "C:/Users/dyh/.cursor/plugins/cache/cursor-public/browse/release_v0.2.4";
const require = createRequire(join(PLUGIN_ROOT, "package.json"));
const { chromium } = require("playwright");

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const BASE_URL = process.env.DEMO_URL ?? "http://localhost";
const VIDEO_URL = process.env.DEMO_YT_URL ?? "https://www.youtube.com/watch?v=mk7pRpLTYWc";
const SLIDE_QUERY = process.env.DEMO_YT_QUERY ?? "What did the author say about slide 7?";
const OUT_DIR = resolve(ROOT, "docs/images/yt_frames");
const VIEWPORT = { width: 1280, height: 800 };

async function shot(page, dir, idx, name) {
  const path = join(dir, `${String(idx).padStart(2, "0")}_${name}.png`);
  await page.screenshot({ path });
  console.log("captured", path);
}

async function main() {
  const ingestDir = join(OUT_DIR, "ingest");
  const qaDir = join(OUT_DIR, "qa");
  await mkdir(ingestDir, { recursive: true });
  await mkdir(qaDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: VIEWPORT });
  page.setDefaultTimeout(180_000);

  try {
    await page.goto(BASE_URL, { waitUntil: "networkidle", timeout: 60_000 });
    await page.waitForTimeout(600);

    // --- Flow 1: ingest ---
    await page.getByRole("tab", { name: "Add YouTube Lecture" }).click();
    await page.waitForTimeout(400);
    let ig = 0;
    await shot(page, ingestDir, ig++, "form");

    await page.locator(".youtube-url-input").fill(VIDEO_URL);
    await shot(page, ingestDir, ig++, "url_typed");

    await page.locator('form.youtube-form button[type="submit"]').click();

    // Poll progress: capture distinct stage labels until chat appears.
    const seenStages = new Set();
    const deadline = Date.now() + 15 * 60_000;
    let chatReady = false;
    while (Date.now() < deadline) {
      if (await page.locator(".chat-input").count()) {
        chatReady = true;
        break;
      }
      const label = await page
        .locator(".youtube-ingest .drop-title")
        .first()
        .textContent()
        .catch(() => null);
      const key = (label ?? "").trim();
      if (key && !seenStages.has(key)) {
        seenStages.add(key);
        await shot(page, ingestDir, ig++, `stage_${seenStages.size}`);
      }
      await page.waitForTimeout(2000);
    }
    if (!chatReady) throw new Error("Ingest did not complete within 15 min");
    await page.waitForTimeout(1500);
    await shot(page, ingestDir, ig++, "indexed");

    // --- Flow 2: slide-scoped Q&A ---
    await page.selectOption("#provider", "openai").catch(() => {});
    let q = 0;
    await shot(page, qaDir, q++, "workspace");

    await page.locator(".chat-input").fill(SLIDE_QUERY);
    await shot(page, qaDir, q++, "question_typed");

    await page.locator('form.chat-input-row button[type="submit"]').click();
    await page.waitForSelector(".message-assistant .citations", { timeout: 180_000 });
    await page.waitForTimeout(1200);
    await shot(page, qaDir, q++, "answer");

    // Expand citations + jump preview to the cited slide page.
    await page.locator(".citations summary").click().catch(() => {});
    await page.waitForTimeout(500);
    const pageLink = page.locator(".citation-page-link").first();
    if (await pageLink.count()) {
      await pageLink.click();
      await page.waitForTimeout(2500);
      await shot(page, qaDir, q++, "slide_preview");
    }

    await writeFile(
      join(OUT_DIR, "manifest.json"),
      JSON.stringify({ video: VIDEO_URL, query: SLIDE_QUERY, viewport: VIEWPORT }, null, 2),
    );
    console.log("Done");
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
