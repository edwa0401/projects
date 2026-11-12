import { expect, test } from "@playwright/test";
import { signIn } from "./helpers";

test("demo mode is clearly labeled and the queue filters work", async ({ page }) => {
  await signIn(page);
  await expect(page.getByText("Demo mode", { exact: true })).toBeVisible();
  await expect(page.getByText(/Simulated analysis \(deterministic rules, not AI\)/)).toBeVisible();
  await page.getByLabel("Priority").selectOption("urgent");
  await expect(page).toHaveURL(/priority=urgent/);
  const rows = page.locator("tbody tr");
  await expect(rows.first()).toBeVisible();
  for (const badge of await rows.locator("td[data-label=Priority]").allTextContents()) expect(badge).toContain("Urgent");
  await page.getByRole("searchbox").fill("zzzz-no-match");
  await expect(page.getByText("No inquiries match these filters")).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(rows.first()).toBeVisible();
});

test("create, review, approve, copy, resolve, and persist after refresh", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await signIn(page);
  await page.getByRole("link", { name: "+ New inquiry" }).click();
  await page.getByRole("button", { name: "Save and analyze" }).click();
  await expect(page.getByText("Enter the customer's message")).toBeVisible();
  await page.getByLabel(/Customer message/).fill("Hi, I need an estimate to move a three-bedroom house from Sherman to Plano on June 9. Thanks!");
  await page.getByLabel("Customer name").fill("E2E Tester");
  await page.getByRole("button", { name: "Save and analyze" }).click();

  await expect(page.getByRole("heading", { name: "E2E Tester" })).toBeVisible();
  await expect(page.getByText("Simulated analysis (demo rules)")).toBeVisible();
  await expect(page.locator(".extracted")).toContainText("June 9");
  await expect(page.locator(".extracted")).toContainText("Not provided");

  // Staff correction + draft save
  await page.getByRole("combobox", { name: /^Priority/ }).selectOption("high");
  await page.getByLabel("Assigned to").selectOption("alex");
  await expect(page.getByText(/Corrected from AI suggestion/)).toBeVisible();
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.locator(".audit")).toContainText("Changed priority from Normal to High");

  // Approval needs verification and no commitments
  const approve = page.getByRole("button", { name: /approve response/i });
  await expect(approve).toBeDisabled();
  const draft = page.getByLabel(/^Response draft/);
  await draft.fill("Hi! Your move is confirmed for $900.");
  await expect(page.getByText(/Approval blocked/)).toBeVisible();
  await draft.fill("Hi! Thanks for reaching out. A team member will follow up with an estimate and next steps.");
  for (const box of await page.getByRole("checkbox").all()) await box.check();
  await expect(approve).toBeEnabled();
  await approve.click();
  await expect(page.getByRole("heading", { name: "Approved response" })).toBeVisible();
  await page.getByRole("button", { name: "Copy approved response" }).click();
  await expect(page.getByRole("button", { name: "Copied" })).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain("A team member will follow up");

  await page.getByRole("button", { name: "Mark resolved" }).click();
  await expect(page.getByText(/Resolved .* by Maya Chen/)).toBeVisible();

  // Refresh persistence
  await page.reload();
  await expect(page.getByText(/Resolved .* by Maya Chen/)).toBeVisible();
  await expect(page.locator(".audit")).toContainText("Approved the response after completing human verification");
  await expect(page.locator(".audit")).toContainText("Status: Draft approved → Resolved");
});

test("expired or invalid sessions return to sign-in with a clear message", async ({ page }) => {
  await signIn(page);
  await page.evaluate(() => {
    const s = JSON.parse(sessionStorage.getItem("leadrescue.session")!);
    s.token = "demo.tampered.token";
    sessionStorage.setItem("leadrescue.session", JSON.stringify(s));
  });
  await page.goto("/results");
  await expect(page.getByRole("heading", { name: "Staff sign-in" })).toBeVisible();
  await expect(page.getByText("Session expired")).toBeVisible();
  await page.getByRole("button", { name: "Sign in to demo" }).click();

  await expect(page).toHaveURL(/\/results$/); // returned to where the staff member was
  await page.evaluate(() => {
    const s = JSON.parse(sessionStorage.getItem("leadrescue.session")!);
    s.expiresAt = Math.floor(Date.now() / 1000) - 1;
    sessionStorage.setItem("leadrescue.session", JSON.stringify(s));
  });
  await page.goto("/companions");
  await expect(page.getByRole("heading", { name: "Staff sign-in" })).toBeVisible();
});

test("sign out ends the session", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByText("You signed out.")).toBeVisible();
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Staff sign-in" })).toBeVisible();
});

test("API rejects unauthenticated calls", async ({ request }) => {
  const res = await request.get("/api/inquiries");
  expect(res.status()).toBe(401);
});
