import { expect, test } from "@playwright/test";

test("/monitor uses MJPEG and never calls getUserMedia", async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).__getUserMediaCalled = false;

    const markCalled = () => {
      (window as any).__getUserMediaCalled = true;
      throw new Error("getUserMedia is forbidden on /monitor");
    };

    const nav = navigator as any;
    nav.getUserMedia = markCalled;
    if (!nav.mediaDevices) nav.mediaDevices = {};
    nav.mediaDevices.getUserMedia = markCalled;
  });

  const mjpegReq = page.waitForRequest((req) => req.url().includes("/api/video/mjpeg"));

  await page.goto("/monitor", { waitUntil: "domcontentloaded" });
  await mjpegReq;

  const called = await page.evaluate(() => (window as any).__getUserMediaCalled);
  expect(called).toBe(false);
});
