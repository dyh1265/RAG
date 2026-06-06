/**
 * Export README static screenshots (upload.png, chat.png, citations.png).
 * Reuses the demo capture flow; run with stack up at http://localhost.
 */
import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
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
const OUT_DIR = resolve(ROOT, "docs/images");
const VIEWPORT = { width: 1280, height: 800 };
const QUERY = "What does Figure 3 show about revenue trends?";

async function main() {
  await mkdir(OUT_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: VIEWPORT });
  page.setDefaultTimeout(180_000);

  try {
    await page.goto(BASE_URL, { waitUntil: "networkidle", timeout: 60_000 });
    await page.waitForTimeout(600);
    await page.screenshot({ path: join(OUT_DIR, "upload.png") });
    console.log("wrote upload.png");

    await page.locator('input[type="file"][accept*="pdf"]').setInputFiles(PDF_PATH);
    await page.waitForSelector(".drop-area-busy", { state: "detached", timeout: 300_000 }).catch(() => {});
    await page.waitForSelector(".chat-input", { timeout: 300_000 });
    await page.selectOption("#provider", "openai");

    await page.locator(".chat-input").fill(QUERY);
    await page.locator('form.chat-input-row button[type="submit"]').click();
    await page.waitForSelector(".message-assistant .citations", { timeout: 180_000 });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: join(OUT_DIR, "chat.png") });
    console.log("wrote chat.png");

    await page.locator(".citations summary").click();
    await page.locator(".citation-page-link").first().click();
    await page.waitForSelector(".doc-preview-frame", { timeout: 30_000 });
    await page.waitForTimeout(2500);
    await page.screenshot({ path: join(OUT_DIR, "citations.png") });
    console.log("wrote citations.png");
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
