export async function renderPdf(browser, { url, timeoutMs = 20000 }) {
  const page = await browser.newPage();
  try {
    await page.goto(url, { waitUntil: "networkidle2", timeout: timeoutMs });
    return await page.pdf({ format: "A4", printBackground: true });
  } finally {
    await page.close();
  }
}
