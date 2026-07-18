import { KnownDevices } from "puppeteer";

// Approximates Lighthouse's mobile "Slow 4G" throttling profile so Mobile
// Test results reflect real-world mobile conditions, not the render
// machine's actual (likely fast, wired) network.
const SLOW_4G = {
  offline: false,
  downloadThroughput: (1.6 * 1024 * 1024) / 8,
  uploadThroughput: (750 * 1024) / 8,
  latency: 150,
};

const TAP_TARGET_SELECTOR = 'a, button, input, select, textarea, [role="button"], [onclick], summary, label';

export async function renderPage(
  browser,
  { url, device, throttle = false, captureScreenshot = false, fullPageScreenshot = false, timeoutMs = 20000 }
) {
  const page = await browser.newPage();
  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(String(err)));

  try {
    if (device && KnownDevices[device]) {
      await page.emulate(KnownDevices[device]);
    }
    if (throttle) {
      const client = await page.createCDPSession();
      await client.send("Network.enable");
      await client.send("Network.emulateNetworkConditions", SLOW_4G);
    }

    const start = Date.now();
    const response = await page.goto(url, { waitUntil: "networkidle2", timeout: timeoutMs });
    const timingMs = Date.now() - start;

    const viewport = page.viewport();

    const extracted = await page.evaluate((selector) => {
      const tapTargets = Array.from(document.querySelectorAll(selector))
        .map((el) => {
          const rect = el.getBoundingClientRect();
          const text = (el.innerText || el.getAttribute("value") || el.getAttribute("aria-label") || "").trim();
          return {
            tag: el.tagName.toLowerCase(),
            text: text.slice(0, 60),
            x: Math.round(rect.x),
            y: Math.round(rect.y),
            width: Math.round(rect.width),
            height: Math.round(rect.height),
          };
        })
        .filter((t) => t.width > 0 && t.height > 0);

      const fontSizes = [];
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
        acceptNode: (node) => (node.textContent.trim().length > 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT),
      });
      let node = walker.nextNode();
      while (node) {
        const el = node.parentElement;
        if (el) {
          const size = parseFloat(getComputedStyle(el).fontSize);
          if (!Number.isNaN(size)) fontSizes.push(size);
        }
        node = walker.nextNode();
      }

      const links = Array.from(document.querySelectorAll("a[href]")).map((a) => ({
        href: a.href,
        text: a.innerText.trim().slice(0, 100),
      }));

      const viewportMeta = document.querySelector('meta[name="viewport"]');

      return {
        tapTargets,
        fontSizes,
        links,
        viewportMetaContent: viewportMeta ? viewportMeta.getAttribute("content") : null,
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth,
        renderedHtml: document.documentElement.outerHTML,
        title: document.title,
      };
    }, TAP_TARGET_SELECTOR);

    let screenshotBase64 = null;
    if (captureScreenshot) {
      screenshotBase64 = await page.screenshot({
        encoding: "base64",
        type: "jpeg",
        quality: 60,
        fullPage: fullPageScreenshot,
      });
    }

    return {
      requested_url: url,
      final_url: response ? response.url() : url,
      status_code: response ? response.status() : null,
      timing_ms: timingMs,
      viewport: viewport
        ? { width: viewport.width, height: viewport.height, device_scale_factor: viewport.deviceScaleFactor }
        : null,
      viewport_meta_content: extracted.viewportMetaContent,
      tap_targets: extracted.tapTargets,
      font_sizes: extracted.fontSizes,
      scroll_width: extracted.scrollWidth,
      inner_width: extracted.innerWidth,
      links: extracted.links,
      rendered_html: extracted.renderedHtml,
      title: extracted.title,
      console_errors: consoleErrors,
      screenshot_base64: screenshotBase64,
    };
  } finally {
    await page.close();
  }
}
