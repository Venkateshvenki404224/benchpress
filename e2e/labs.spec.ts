import { test, expect } from "@playwright/test";
import { LabsPage } from "./pages/LabsPage";
import { createTestLab, deleteTestDoc } from "./fixtures/test-data";

let labName: string;

test.describe("Labs Page", () => {
  test.beforeEach(async ({ page }) => {
    const lab = await createTestLab(page, {
      title: "E2E Test Lab",
      lab_id: `e2e-lab-${Date.now().toString(36)}`,
      frappe_version: "version-16",
      status: "Draft",
    });
    labName = lab.name;
  });

  test.afterEach(async ({ page }) => {
    if (labName) {
      await deleteTestDoc(page, "Lab", labName);
    }
  });

  test("loads and displays labs list heading", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await expect(labsPage.heading).toBeVisible();
    await expect(labsPage.searchInput).toBeVisible();
  });

  test("displays search and filter controls", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await expect(labsPage.searchInput).toBeVisible();
    await expect(labsPage.statusCombobox).toBeVisible();
    await expect(labsPage.versionCombobox).toBeVisible();
  });

  test("search filters labs by title", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();
    await labsPage.waitForPageLoad();

    await labsPage.search("E2E Test Lab");
    await expect(page.locator("text=E2E Test Lab")).toBeVisible();

    await labsPage.search("nonexistent-lab-xyz-12345");
    await expect(page.locator("text=No labs match")).toBeVisible();
  });

  test("search clears and shows all labs again", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();
    await labsPage.waitForPageLoad();

    await labsPage.search("E2E Test Lab");
    await labsPage.clearSearch();

    await expect(page.locator("text=E2E Test Lab")).toBeVisible();
  });

  test("status filter shows matching labs", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();
    await labsPage.waitForPageLoad();

    await labsPage.filterByStatus("Draft");
    await expect(page.locator("text=E2E Test Lab")).toBeVisible();
  });

  test("status filter hides non-matching labs", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();
    await labsPage.waitForPageLoad();

    await labsPage.filterByStatus("Ready");
    await expect(page.locator("text=E2E Test Lab")).not.toBeVisible();
  });

  test("version filter shows matching labs", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();
    await labsPage.waitForPageLoad();

    await labsPage.filterByVersion("Version 16");
    await expect(page.locator("text=E2E Test Lab")).toBeVisible();
  });

  test("version filter hides non-matching labs", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();
    await labsPage.waitForPageLoad();

    await labsPage.filterByVersion("Version 14");
    await expect(page.locator("text=E2E Test Lab")).not.toBeVisible();
  });

  test("clicking a lab navigates to lab detail", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();
    await labsPage.waitForPageLoad();

    await page.locator("text=E2E Test Lab").first().click();
    await page.waitForURL(`**/labs/${labName}`);
    await expect(page.locator("h1")).toContainText("E2E Test Lab");
  });
});
