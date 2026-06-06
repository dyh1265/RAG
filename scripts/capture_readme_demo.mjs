/**
 * Capture README demo frames from the live DocuMind UI.
 *
 * Usage (from repo root, Playwright from Cursor browse plugin):
 *   node scripts/capture_readme_demo.mjs
 *
 * Writes PNG frames to docs/images/demo_frames/
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
const PDF_PATH = resolve(ROOT, "data/raw/sample_report.pdf");
const OUT_DIR = resolve(ROOT, "docs/images/demo_frames");
const VIEWPORT = { width: 1280, height: 800 };
const QUERY = "What does Figure 3 show about revenue trends?";

let frame = 0;

async function shot(page, name) {
  const path = join(OUT_DIR, `${String(frame).padStart(2, "0")}_${name}.png`);
  await page.screenshot({ path, fullPage: false });
  console.log("captured", path);
  frame += 1;
  return path;
}

async function waitForChatReady(page, timeoutMs = 300_000) {
  await page.waitForSelector(".drop-area-busy", { state: "detached", timeout: timeoutMs }).catch(() => {});
  const input = page.locator(".chat-input");
  await input.waitFor({ state: "visible", timeout: timeoutMs });
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.setDefaultTimeout(180_000);

  try {
    await page.goto(BASE_URL, { waitUntil: "networkidle", timeout: 60_000 });
    await page.waitForTimeout(800);
    await shot(page, "landing");

    const fileInput = page.locator('input[type="file"][accept*="pdf"]');
    await fileInput.setInputFiles(PDF_PATH);

    // Ingest progress then chat becomes available.
    await waitForChatReady(page);
    await page.waitForTimeout(1500);
    await shot(page, "indexed");

    // Faster, reliable answer for the demo capture.
    await page.selectOption("#provider", "openai");

    const chatInput = page.locator(".chat-input");
    await chatInput.fill(QUERY);
    await shot(page, "question_typed");

    await page.locator('form.chat-input-row button[type="submit"]').click();

    // Wait for assistant reply with citations (loading dots gone).
    await page.waitForSelector(".message-assistant .citations", { timeout: 180_000 });
    await page.waitForTimeout(1200);
    await shot(page, "answer");

    await writeFile(
      join(OUT_DIR, "manifest.json"),
      JSON.stringify({ query: QUERY, frames: frame, viewport: VIEWPORT }, null, 2),
    );
    console.log(`Done — ${frame} frames in ${OUT_DIR}`);
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
