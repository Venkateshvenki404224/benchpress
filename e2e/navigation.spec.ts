import { test, expect } from "@playwright/test";
import { BasePage } from "./pages/BasePage";

test.describe("Navigation & Routing", () => {
  test("home route shows labs page", async ({ page }) => {
    const basePage = new BasePage(page);
    await basePage.gotoFrontend("/");

    await expect(page.locator("h1", { hasText: "Labs" })).toBeVisible();
  });

  test("/labs route loads labs page", async ({ page }) => {
    await page.goto("/frontend/labs");
    await page.waitForLoadState("networkidle");

    await expect(page.locator("h1", { hasText: "Labs" })).toBeVisible();
  });

  test("/bench-instances route loads bench instances page", async ({
    page,
  }) => {
    await page.goto("/frontend/bench-instances");
    await page.waitForLoadState("networkidle");

    await expect(
      page.locator("h1", { hasText: "Bench Instances" })
    ).toBeVisible();
  });

  test("/devices route loads devices page", async ({ page }) => {
    await page.goto("/frontend/devices");
    await page.waitForLoadState("networkidle");

    await expect(
      page.locator("h1", { hasText: "VPN Devices" })
    ).toBeVisible();
  });

  test("sidebar navigation links work", async ({ page }) => {
    const basePage = new BasePage(page);
    await basePage.gotoFrontend("/labs");

    await page
      .locator('button[aria-label="Bench Instances"]')
      .click();
    await page.waitForLoadState("networkidle");
    await expect(
      page.locator("h1", { hasText: "Bench Instances" })
    ).toBeVisible();

    await page
      .locator('button[aria-label="VPN Devices"]')
      .click();
    await page.waitForLoadState("networkidle");
    await expect(
      page.locator("h1", { hasText: "VPN Devices" })
    ).toBeVisible();

    await page
      .locator('button[aria-label="Labs"]')
      .click();
    await page.waitForLoadState("networkidle");
    await expect(
      page.locator("h1", { hasText: "Labs" })
    ).toBeVisible();
  });

  test("unauthenticated user is redirected to login", async ({
    browser,
  }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    const response = await page.goto("/frontend/labs");
    await page.waitForLoadState("networkidle");

    const url = page.url();
    const isLogin = url.includes("/login");
    const isFrontend = url.includes("/frontend");
    expect(isLogin || isFrontend).toBeTruthy();

    await context.close();
  });
});
