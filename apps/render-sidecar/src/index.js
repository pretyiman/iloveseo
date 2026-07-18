import express from "express";
import puppeteer from "puppeteer";
import { renderPage } from "./render.js";

const PORT = process.env.PORT || 4000;

const app = express();
app.use(express.json());

let browser;

app.get("/health", (_req, res) => {
  res.json({ status: "ok", browser_connected: Boolean(browser?.connected) });
});

app.post("/render", async (req, res) => {
  const { url, device, throttle, capture_screenshot, full_page_screenshot, timeout_ms } = req.body ?? {};
  if (!url) {
    return res.status(400).json({ error: "url is required" });
  }
  try {
    const result = await renderPage(browser, {
      url,
      device,
      throttle: Boolean(throttle),
      captureScreenshot: Boolean(capture_screenshot),
      fullPageScreenshot: Boolean(full_page_screenshot),
      timeoutMs: timeout_ms || 20000,
    });
    res.json(result);
  } catch (err) {
    res.status(502).json({ error: String(err) });
  }
});

async function main() {
  browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });

  app.listen(PORT, () => {
    console.log(`render-sidecar listening on :${PORT}`);
  });
}

process.on("SIGTERM", async () => {
  await browser?.close();
  process.exit(0);
});

main();
