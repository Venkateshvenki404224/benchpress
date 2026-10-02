import { expect, test } from "@playwright/test";
import { createTestLab, deleteTestDoc } from "./fixtures/test-data";
import { LabsPage } from "./pages/LabsPage";

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

  test("loads the grid and its filters", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await expect(labsPage.grid).toBeVisible();
    await expect(labsPage.searchInput).toBeVisible();
    await expect(labsPage.statusFilter).toBeVisible();
    await expect(labsPage.versionFilter).toBeVisible();
    await expect(labsPage.ownerFilter).toBeVisible();
  });

  test("the fixture card shows its version, its badge and where it is deployed", async ({
    page,
  }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    const card = labsPage.card(labName);
    await expect(card).toContainText("version-16");
    await expect(card.locator('[data-test="status-Draft"]')).toBeVisible();
    await expect(card).toContainText("Never deployed");
  });

  test("renders every status as a badge, never grey text", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await expect(labsPage.statusBadge(labName, "Draft").first()).toBeVisible();
  });

  test("an undeployed lab says so rather than leaving a blank cell", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await expect(labsPage.grid).toContainText("Never deployed");
  });

  test("search narrows the list without a page reload", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await labsPage.search("E2E Test Lab");
    await labsPage.expectCardVisible(labName);

    await labsPage.search("nonexistent-lab-xyz-12345");
    await labsPage.expectCardHidden(labName);
    await expect(labsPage.clearFilters).toBeVisible();
  });

  test("clearing the filters brings every lab back", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await labsPage.search("nonexistent-lab-xyz-12345");
    await labsPage.clearFilters.click();

    await labsPage.expectCardVisible(labName);
  });

  test("the filters keep matching labs and drop the rest", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    // The fixture lab is Draft on version-16. Each dropdown only offers values
    // that some lab actually has, so filtering to another one must empty it out.
    await labsPage.filterByStatus("Draft");
    await labsPage.expectCardVisible(labName);

    await labsPage.filterByStatus("Status: all");
    await labsPage.filterByVersion("version-15");
    await labsPage.expectCardHidden(labName);
  });

  test("admin header actions are present for an admin", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await labsPage.expectAdminActionsVisible();
  });

  test("the Templates tab opens the catalog at its own URL", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await labsPage.templatesTab.click();
    await page.waitForURL("**/labs/templates");
    await expect(labsPage.testId("templates")).toBeVisible();
  });

  test("clicking a lab opens its detail page", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await labsPage.card(labName).click();
    await page.waitForURL(`**/labs/${labName}`);
  });
});
