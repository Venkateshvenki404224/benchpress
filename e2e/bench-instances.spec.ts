import { expect, test } from "@playwright/test";
import { BenchInstancesPage } from "./pages/BenchInstancesPage";

test.describe("Bench Instances Page", () => {
  test("loads the page and states who the list is scoped to", async ({ page }) => {
    const instancesPage = new BenchInstancesPage(page);
    await instancesPage.goto();

    await expect(instancesPage.root).toBeVisible();
    await instancesPage.expectScopedTo(/across all owners|Containers you own/);
  });

  test("carries the Deploy history action", async ({ page }) => {
    const instancesPage = new BenchInstancesPage(page);
    await instancesPage.goto();

    await expect(instancesPage.deployHistoryButton).toBeVisible();
    await instancesPage.deployHistoryButton.click();
    await page.waitForURL("**/deploy-logs");
  });

  test("shows the six columns, or an empty state that offers a next step", async ({
    page,
  }) => {
    const instancesPage = new BenchInstancesPage(page);
    await instancesPage.goto();

    if (await instancesPage.table.count()) {
      for (const column of [
        "Bench",
        "Status",
        "Health",
        "CPU / memory",
        "Site",
        "Owner",
      ]) {
        await expect(instancesPage.table).toContainText(column);
      }
    } else {
      await instancesPage.expectEmptyState();
      await expect(instancesPage.root).toContainText("Start from a template");
    }
  });

  test("never renders a blank health pill", async ({ page }) => {
    const instancesPage = new BenchInstancesPage(page);
    await instancesPage.goto();
    test.skip(!(await instancesPage.table.count()), "no benches on this site");

    // container_health may be the empty string; it must read Unknown.
    const pills = instancesPage.table.locator('[data-test^="status-"]');
    for (const pill of await pills.all()) {
      await expect(pill).not.toHaveText(/^\s*$/);
    }
  });
});
