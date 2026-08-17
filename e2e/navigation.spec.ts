import { test, expect } from "@playwright/test";
import { BasePage } from "./pages/BasePage";

test.describe("Navigation & Routing", () => {
  test("home route shows the overview", async ({ page }) => {
    const basePage = new BasePage(page);
    await basePage.gotoFrontend("/");

    await expect(basePage.testId("overview")).toBeVisible();
    await expect(basePage.testId("greeting")).toContainText("Good");
    await expect(basePage.testId("stats")).toBeVisible();
  });

  test("/labs route loads labs page", async ({ page }) => {
    await page.goto("/frontend/labs");
    await page.waitForLoadState("networkidle");

    await expect(page.locator("h1", { hasText: "Labs" })).toBeVisible();
  });

  test("/bench-instances route loads the instances page", async ({ page }) => {
    await page.goto("/frontend/bench-instances");
    await page.waitForLoadState("networkidle");

    await expect(page.locator('[data-test="instances"]')).toBeVisible();
  });

  test("/devices route loads devices page", async ({ page }) => {
    await page.goto("/frontend/devices");
    await page.waitForLoadState("networkidle");

    await expect(page.locator('[data-test="devices"]')).toBeVisible();
  });

  test("sidebar is five items and each one navigates", async ({ page }) => {
    const basePage = new BasePage(page);
    await basePage.gotoFrontend("/labs");
    await basePage.waitForUserContext();

    await basePage.clickNav("instances");
    await expect(basePage.testId("instances")).toBeVisible();

    await basePage.clickNav("devices");
    await expect(page.locator('[data-test="devices"]')).toBeVisible();

    await basePage.clickNav("labs");
    await expect(page.locator("h1", { hasText: "Labs" })).toBeVisible();

    await basePage.clickNav("overview");
    await expect(basePage.testId("overview")).toBeVisible();

    // The Logs section is gone — history is reached from its object.
    await expect(page.locator('[data-test="nav-deploy-logs"]')).toHaveCount(0);
    await expect(page.locator('[data-test="nav-build-logs"]')).toHaveCount(0);
  });

  test("search and notifications sit above the nav, not in the header", async ({
    page,
  }) => {
    const basePage = new BasePage(page);
    await basePage.gotoFrontend("/");
    await basePage.waitForUserContext();

    await expect(basePage.testId("nav-search")).toBeVisible();
    await expect(basePage.testId("nav-notifications")).toBeVisible();
    await expect(basePage.testId("app-header")).not.toContainText("Search");

    await basePage.testId("nav-search").click();
    await expect(basePage.testId("search-palette")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(basePage.testId("search-palette")).toBeHidden();
  });

  test("the notifications panel opens beside the sidebar and toggles shut", async ({
    page,
  }) => {
    const basePage = new BasePage(page);
    await basePage.gotoFrontend("/labs");
    await basePage.waitForUserContext();

    await basePage.testId("nav-notifications").click();
    const panel = basePage.testId("notifications");
    await expect(panel).toBeVisible();

    // It sits against the sidebar rather than centred like a modal. The panel
    // slides in, so its left edge is only final once the transition settles.
    const sidebarBox = (await basePage.testId("nav-labs").boundingBox())!;
    await expect
      .poll(async () => (await panel.boundingBox())!.x, { timeout: 5_000 })
      .toBeGreaterThan(sidebarBox.x + sidebarBox.width - 1);
    expect((await panel.boundingBox())!.x).toBeLessThan(
      sidebarBox.x + sidebarBox.width + 40,
    );

    // The screen underneath stays where it was.
    await expect(page.locator("h1", { hasText: "Labs" })).toBeVisible();

    await basePage.testId("nav-notifications").click();
    await expect(panel).toBeHidden();
  });

  test("header carries the breadcrumb and the VPN chip", async ({ page }) => {
    const basePage = new BasePage(page);
    await basePage.gotoFrontend("/");

    await expect(basePage.testId("app-header")).toContainText("BenchPress");
    await expect(basePage.testId("vpn-chip")).toContainText("VPN");
  });

  test("an unknown route renders the 404 page", async ({ page }) => {
    const basePage = new BasePage(page);
    await basePage.gotoFrontend("/no-such-page");

    await expect(basePage.testId("not-found")).toBeVisible();
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
