import { expect, type Page } from "@playwright/test";

export async function signIn(page: Page, name = "Maya Chen") {
  await page.goto("/signin");
  await page.getByLabel(new RegExp(name)).check();
  await page.getByRole("button", { name: "Sign in to demo" }).click();
  // Sign-in returns staff to the page they were on; always land on the queue for test setup.
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  if (new URL(page.url()).pathname !== "/") await page.goto("/");
  await expect(page.getByRole("heading", { name: /Inquiry queue/ })).toBeVisible();
}
