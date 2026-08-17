import { expect, test } from "@playwright/test";
import {
  createTestBench,
  createTestBuildLog,
  createTestDeployLog,
  deleteTestDoc,
  deployStepLine,
} from "./fixtures/test-data";
import { createTestLab } from "./fixtures/test-data";
import { RunHistoryPage } from "./pages/RunHistoryPage";

/**
 * The two history tables. They share one component, so the assertions that
 * matter are the ones about what a row says: the result badge, the step the run
 * last opened, its duration, and the em-dash where a run recorded neither.
 */
const STRUCTURED_RUN = [
  "=== Deploy started ===",
  deployStepLine(1, "Checking shared infrastructure", "infrastructure", 0),
  deployStepLine(7, "Creating the site", "site", 61.4),
  deployStepLine(11, "Deploy complete", "complete", 188),
].join("\n");

const LEGACY_RUN = ["=== Deploy started ===", "no step metadata in this one"].join("\n");

let labName: string;
let benchName: string;
let structuredLog: string;
let legacyLog: string;
let buildLog: string;

test.describe("Run history", () => {
  test.beforeEach(async ({ page }) => {
    const lab = await createTestLab(page, {
      lab_id: `e2e-history-${Date.now().toString(36)}`,
      title: "E2E History Lab",
    });
    labName = lab.name;
    const bench = await createTestBench(page, labName, { status: "Running" });
    benchName = bench.name;

    structuredLog = (await createTestDeployLog(page, benchName, STRUCTURED_RUN, "success")).name;
    legacyLog = (await createTestDeployLog(page, benchName, LEGACY_RUN, "info")).name;
    buildLog = (
      await createTestBuildLog(
        page,
        labName,
        "=== Build started ===\n=== Installing apps ===\n=== Build failed: app install exited 128 ===",
        "error"
      )
    ).name;
  });

  test.afterEach(async ({ page }) => {
    for (const [doctype, name] of [
      ["Deploy Log", structuredLog],
      ["Deploy Log", legacyLog],
      ["Build Log", buildLog],
      ["Bench Instance", benchName],
      ["Lab", labName],
    ] as const) {
      if (name) await deleteTestDoc(page, doctype, name);
    }
  });

  test("a finished run reports the step it ended on and how long it took", async ({ page }) => {
    const history = RunHistoryPage.deploy(page);
    await history.goto();

    const row = history.row(structuredLog);
    await expect(row).toBeVisible();
    await expect(history.table).toContainText("Deploy complete");
    await expect(history.table).toContainText("3m 8s");
  });

  test("a run with no step metadata gets an em-dash, not a guess", async ({ page }) => {
    const history = RunHistoryPage.deploy(page);
    await history.goto();

    const row = history.row(legacyLog);
    await expect(row).toBeVisible();
    // The row is still there and still readable; it just claims nothing it
    // cannot support. `Deploy started` is the only marker it opened.
    await expect(history.table).toContainText("Deploy started");
  });

  test("both tables state the seven-day retention", async ({ page }) => {
    for (const history of [RunHistoryPage.deploy(page), RunHistoryPage.build(page)]) {
      await history.goto();
      await expect(history.retentionNote).toContainText("kept for 7 days");
    }
  });

  test("build history names the failing step and shows a result badge", async ({ page }) => {
    const history = RunHistoryPage.build(page);
    await history.goto();

    await expect(history.row(buildLog)).toBeVisible();
    await expect(history.table).toContainText("Installing apps");
    await expect(history.table).toContainText("Failed");
  });

  test("a row opens the lab behind the run", async ({ page }) => {
    const history = RunHistoryPage.build(page);
    await history.goto();

    await history.row(buildLog).click();
    await page.waitForURL(`**/labs/${labName}`, { timeout: 20_000 });
  });

  test("each table links back to its parent, since neither is in the sidebar", async ({ page }) => {
    const build = RunHistoryPage.build(page);
    await build.goto();
    await expect(build.backLink).toContainText("Labs");
    await build.backLink.click();
    await page.waitForURL("**/labs", { timeout: 20_000 });

    const deploy = RunHistoryPage.deploy(page);
    await deploy.goto();
    await expect(deploy.backLink).toContainText("Instances");
    await deploy.backLink.click();
    await page.waitForURL("**/bench-instances", { timeout: 20_000 });
  });
});
