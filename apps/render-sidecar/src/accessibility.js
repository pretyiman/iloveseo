import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { KnownDevices } from "puppeteer";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const axeSource = fs.readFileSync(path.join(__dirname, "..", "node_modules", "axe-core", "axe.min.js"), "utf-8");

export async function runAccessibilityScan(browser, { url, device, timeoutMs = 20000 }) {
  const page = await browser.newPage();
  try {
    if (device && KnownDevices[device]) {
      await page.emulate(KnownDevices[device]);
    }
    await page.goto(url, { waitUntil: "networkidle2", timeout: timeoutMs });
    await page.evaluate(axeSource);
    const results = await page.evaluate(() => axe.run());

    return {
      url,
      violations: results.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        description: v.description,
        help: v.help,
        help_url: v.helpUrl,
        tags: v.tags,
        node_count: v.nodes.length,
        sample_targets: v.nodes.slice(0, 5).map((n) => n.target.join(" ")),
      })),
      passes_count: results.passes.length,
      incomplete_count: results.incomplete.length,
    };
  } finally {
    await page.close();
  }
}
