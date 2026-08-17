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

  test("loads the table and its filters", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await expect(labsPage.table).toBeVisible();
    await expect(labsPage.searchInput).toBeVisible();
    await expect(labsPage.statusFilter).toBeVisible();
    await expect(labsPage.versionFilter).toBeVisible();
    await expect(labsPage.ownerFilter).toBeVisible();
  });

  test("shows the columns the old table omitted", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    for (const column of ["Lab", "Version", "Apps", "Status", "Deployed as", "Last run"]) {
      await expect(labsPage.table).toContainText(column);
    }
    // Memory and CPU moved to the lab detail header.
    await expect(labsPage.table).not.toContainText("Memory");
  });

  test("renders every status as a badge, never grey text", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await expect(labsPage.statusBadge(labName, "Draft").first()).toBeVisible();
  });

  test("an undeployed lab says so rather than leaving a blank cell", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await expect(labsPage.table).toContainText("Never deployed");
  });

  test("search narrows the list without a page reload", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await labsPage.search("E2E Test Lab");
    await labsPage.expectRowVisible(labName);

    await labsPage.search("nonexistent-lab-xyz-12345");
    await labsPage.expectRowHidden(labName);
    await expect(labsPage.clearFilters).toBeVisible();
  });

  test("clearing the filters brings every lab back", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await labsPage.search("nonexistent-lab-xyz-12345");
    await labsPage.clearFilters.click();

    await labsPage.expectRowVisible(labName);
  });

  test("the filters keep matching labs and drop the rest", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    // The fixture lab is Draft on version-16. Each dropdown only offers values
    // that some lab actually has, so filtering to another one must empty it out.
    await labsPage.filterByStatus("Draft");
    await labsPage.expectRowVisible(labName);

    await labsPage.filterByStatus("Status: all");
    await labsPage.filterByVersion("version-15");
    await labsPage.expectRowHidden(labName);
  });

  test("admin header actions are present for an admin", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await labsPage.expectAdminActionsVisible();
    await expect(labsPage.fromTemplateButton).toBeVisible();
  });

  test("clicking a lab opens its detail page", async ({ page }) => {
    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await labsPage.row(labName).click();
    await page.waitForURL(`**/labs/${labName}`);
  });
});
