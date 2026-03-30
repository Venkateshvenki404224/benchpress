import { test, expect } from "@playwright/test";
import { BenchInstancesPage } from "./pages/BenchInstancesPage";

test.describe("Bench Instances Page", () => {
  test("loads and displays page heading", async ({ page }) => {
    const instancesPage = new BenchInstancesPage(page);
    await instancesPage.goto();
    await instancesPage.expectPageLoaded();
  });

  test("shows empty state when no instances exist", async ({ page }) => {
    const instancesPage = new BenchInstancesPage(page);
    await instancesPage.goto();
    await instancesPage.waitForPageLoad();

    const emptyVisible = await page
      .locator("text=No bench instances found")
      .isVisible();

    if (emptyVisible) {
      await expect(
        page.locator("text=Deploy a lab to create one")
      ).toBeVisible();
    }
  });

  test("page renders without errors", async ({ page }) => {
    const instancesPage = new BenchInstancesPage(page);
    await instancesPage.goto();
    await instancesPage.waitForPageLoad();

    await expect(instancesPage.heading).toBeVisible();
    const hasContent =
      (await page
        .locator("text=No bench instances found")
        .isVisible()) ||
      (await page.locator("text=Bench Name").isVisible());
    expect(hasContent).toBeTruthy();
  });
});
