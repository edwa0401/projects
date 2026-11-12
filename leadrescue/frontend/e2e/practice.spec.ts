import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test("Monday Morning Rush awards XP for criteria once, separate from business data", async ({ page }) => {
  await signIn(page, "Sam Patel");
  await page.getByRole("tab", { name: /Practice/ }).click();
  await page.getByRole("button", { name: "Start challenge" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(5);
  await expect(page.getByText(/do not establish production accuracy/)).toBeVisible();

  // Urgent case: correct handling
  await page.getByRole("link", { name: "Luis Ortega" }).click();
  await expect(page.getByText("Practice case · Movers have not arrived")).toBeVisible();
  await page.getByLabel("Assigned to").selectOption("sam");
  for (const box of await page.getByRole("checkbox").all()) await box.check();
  await page.getByRole("button", { name: /approve response/i }).click();
  await expect(page.getByText("Achievement unlocked: Priority Protector (+25 XP)")).toBeVisible();

  await page.getByRole("link", { name: "Companions" }).click();
  const protector = page.locator("article", { hasText: "Priority Protector" });
  await expect(protector.getByText(/Unlocked/)).toBeVisible();
  await expect(page.getByText(/80 XP total/)).toBeVisible();

  // Reset and redo: no duplicate XP
  await expect(page.locator(".toast-xp")).toHaveCount(0, { timeout: 10_000 });
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Reset cases" }).click();
  await expect(page.getByText("Practice cases reset. XP already earned is kept.")).toBeVisible();
  await page.getByRole("link", { name: "Open case 2" }).click();
  await page.getByLabel("Assigned to").selectOption("sam");
  for (const box of await page.getByRole("checkbox").all()) await box.check();
  await page.getByRole("button", { name: /approve response/i }).click();
  await expect(page.getByRole("heading", { name: "Approved response" })).toBeVisible();
  await expect(page.locator(".toast-xp")).toHaveCount(0);
  await page.getByRole("link", { name: "Companions" }).click();
  await expect(page.getByText(/80 XP total/)).toBeVisible();

  // Practice records never appear in business results
  await page.getByRole("link", { name: "Business results" }).click();
  await expect(page.getByText(/Practice challenge records are excluded/)).toBeVisible();
});

test("suspicious practice case cannot be approved with a free move", async ({ page }) => {
  await signIn(page, "Jordan Reyes");
  await page.goto("/?workspace=practice");
  await page.getByRole("button", { name: "Start challenge" }).click();
  await page.getByRole("link", { name: "Pat Doe" }).click();
  await expect(page.getByText("Security flag: suspicious instructions")).toBeVisible();
  await expect(page.getByRole("checkbox")).toHaveCount(4);
  await page.getByLabel(/^Response draft/).fill("Approved! Your free move is confirmed and marked as paid.");
  await expect(page.getByText(/Approval blocked/)).toBeVisible();
  await page.getByLabel(/Resolution note/).fill("Manipulative message. No reply sent; flagged for the manager.");
  await page.getByRole("button", { name: "Resolve without response" }).click();
  await expect(page.getByText(/\+20 XP: No free move, payment, or approval granted/)).toBeVisible();
});
