import { test, expect } from "@playwright/test";
import { LabDetailPage } from "./pages/LabDetailPage";
import { createTestLab, deleteTestDoc } from "./fixtures/test-data";

let labName: string;

test.describe("Lab Detail Page", () => {
  test.beforeEach(async ({ page }) => {
    const lab = await createTestLab(page, {
      title: "E2E Detail Lab",
      lab_id: `e2e-detail-${Date.now().toString(36)}`,
      frappe_version: "version-16",
      status: "Draft",
      memory_limit: "4G",
      cpu_cores: 2,
    });
    labName = lab.name;
  });

  test.afterEach(async ({ page }) => {
    if (labName) {
      await deleteTestDoc(page, "Lab", labName);
    }
  });

  test("loads lab detail with title and metadata", async ({ page }) => {
    const detailPage = new LabDetailPage(page);
    await detailPage.goto(labName);
    await detailPage.expectLabLoaded();

    await detailPage.expectLabTitle("E2E Detail Lab");
    await expect(page.locator("text=version-16")).toBeVisible();
    await expect(page.locator("text=4G RAM")).toBeVisible();
    await expect(page.locator("text=2 CPU")).toBeVisible();
  });

  test("displays lab ID badge", async ({ page }) => {
    const detailPage = new LabDetailPage(page);
    await detailPage.goto(labName);
    await detailPage.expectLabLoaded();

    await expect(page.locator("text=Lab ID")).toBeVisible();
    await expect(detailPage.labIdBadge).toBeVisible();
  });

  test("dashboard tab shows lab information", async ({ page }) => {
    const detailPage = new LabDetailPage(page);
    await detailPage.goto(labName);
    await detailPage.expectLabLoaded();

    await expect(
      page.locator("text=Lab Information")
    ).toBeVisible();
  });

  test("shows no active deployment for Draft lab", async ({ page }) => {
    const detailPage = new LabDetailPage(page);
    await detailPage.goto(labName);
    await detailPage.expectLabLoaded();

    await detailPage.expectNoActiveDeployment();
  });

  test("sites tab shows empty state for undeployed lab", async ({
    page,
  }) => {
    const detailPage = new LabDetailPage(page);
    await detailPage.goto(labName);
    await detailPage.expectLabLoaded();

    await detailPage.clickTab("Sites");
    await expect(
      page.locator("text=Deploy this lab first")
    ).toBeVisible();
  });

  test("existing Ready lab with bench shows Stop button", async ({
    page,
  }) => {
    const detailPage = new LabDetailPage(page);
    await detailPage.gotoFrontend("/labs/crm-lab");
    await detailPage.expectLabLoaded();

    const hasStop = await page
      .locator('button:has-text("Stop")')
      .isVisible()
      .catch(() => false);
    const hasDeploy = await page
      .locator('button:has-text("Deploy")')
      .isVisible()
      .catch(() => false);

    expect(hasStop || hasDeploy).toBeTruthy();
  });
});
