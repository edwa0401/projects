import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

async function noSeriousViolations(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(serious.map((v) => `${v.id}: ${v.nodes.length} nodes`)).toEqual([]);
}

test("keyboard: skip link and sign-in work without a mouse", async ({ page }) => {
  await page.goto("/signin");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to sign in" })).toBeFocused();
  await page.waitForSelector("text=Maya Chen");
  await page.getByLabel(/Maya Chen/).focus();
  await page.keyboard.press("ArrowDown");
  await expect(page.getByLabel(/Jordan Reyes/)).toBeChecked();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: /Inquiry queue/ })).toBeVisible();
  // On a fresh load the skip link is the first Tab stop.
  await page.reload();
  await expect(page.getByRole("heading", { name: /Inquiry queue/ })).toBeVisible();
  await page.locator("body").focus();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main")).toBeFocused();
});

test("accessibility scan: sign-in, mission control, workspace, companions, results", async ({ page }) => {
  await page.goto("/signin");
  await page.waitForSelector("text=Maya Chen");
  await noSeriousViolations(page);
  await signIn(page);
  await noSeriousViolations(page);
  await page.locator("a.row-link").first().click();
  await expect(page.getByRole("heading", { name: "Staff review" })).toBeVisible();
  await noSeriousViolations(page);
  for (const path of ["/companions", "/results", "/guide"]) {
    await page.goto(path);
    await page.waitForSelector("h1");
    await page.waitForTimeout(300);
    await noSeriousViolations(page);
  }
});

for (const vp of [
  { name: "phone", width: 375, height: 812 },
  { name: "tablet", width: 768, height: 1024 },
]) {
  test(`responsive layout without horizontal scrolling (${vp.name})`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await signIn(page);
    for (const path of ["/", "/companions", "/results", "/guide", "/inquiries/new"]) {
      await page.goto(path);
      await page.waitForSelector("h1");
      await page.waitForTimeout(250);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow, `horizontal overflow on ${path}`).toBeLessThanOrEqual(0);
    }
    await page.goto("/");
    await page.locator("a.row-link").first().click();
    await expect(page.getByRole("heading", { name: "Staff review" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
}
