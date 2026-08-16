import { test, expect } from "@playwright/test";
import { LabDetailPage } from "./pages/LabDetailPage";
import {
  createTestBench,
  createTestBuildLog,
  createTestLab,
  deleteTestDoc,
} from "./fixtures/test-data";

let labName: string;
let benchName: string | null = null;
let buildLogName: string | null = null;

async function newLab(page, overrides = {}) {
  const lab = await createTestLab(page, {
    title: "E2E Detail Lab",
    lab_id: `e2e-detail-${Date.now().toString(36)}`,
    frappe_version: "version-16",
    status: "Ready",
    memory_limit: "4G",
    cpu_cores: 2,
    description: "A lab the detail suite drives.",
    ...overrides,
  });
  labName = lab.name;
  return lab;
}

test.describe("Lab detail", () => {
  test.afterEach(async ({ page }) => {
    if (benchName) {
      await deleteTestDoc(page, "Bench Instance", benchName);
      benchName = null;
    }
    if (buildLogName) {
      await deleteTestDoc(page, "Build Log", buildLogName);
      buildLogName = null;
    }
    if (labName) await deleteTestDoc(page, "Lab", labName);
  });

  test("header carries the identity and the spec chips the table gave up", async ({ page }) => {
    await newLab(page);
    const detail = new LabDetailPage(page);
    await detail.goto(labName);

    await detail.expectTitle("E2E Detail Lab");
    await expect(detail.labId).toContainText(labName);
    await expect(detail.testId("lab-description")).toBeVisible();
    await expect(detail.testId("lab-specs")).toContainText("version-16");
    await expect(detail.testId("lab-specs")).toContainText("4 GB");
    await expect(detail.testId("lab-specs")).toContainText("2 vCPU");
  });

  test("the duplicate Lab Information card is gone", async ({ page }) => {
    await newLab(page);
    const detail = new LabDetailPage(page);
    await detail.goto(labName);

    await expect(page.getByText("Lab Information")).toHaveCount(0);
  });

  test("an undeployed lab offers Deploy and has no container card", async ({ page }) => {
    await newLab(page);
    const detail = new LabDetailPage(page);
    await detail.goto(labName);

    await detail.expectPrimaryAction("Deploy");
    await expect(detail.containerStatus).toHaveCount(0);
    await expect(page.getByText("never been deployed")).toBeVisible();
  });

  test("Stop is unreachable until the overflow menu is opened", async ({ page }) => {
    const lab = await newLab(page);
    benchName = (await createTestBench(page, lab.name, { status: "Running" })).name;

    const detail = new LabDetailPage(page);
    await detail.goto(labName);

    // §8.5: the destructive action is no longer the loudest thing on the page.
    await expect(page.getByRole("button", { name: "Stop bench" })).toHaveCount(0);
    await detail.openOverflow();
    await expect(detail.menuItem("Stop bench")).toBeVisible();
  });

  test("stopping a bench asks first", async ({ page }) => {
    const lab = await newLab(page);
    benchName = (await createTestBench(page, lab.name, { status: "Running" })).name;

    const detail = new LabDetailPage(page);
    await detail.goto(labName);
    await detail.openOverflow();
    await detail.menuItem("Stop bench").click();

    await expect(detail.dialog()).toContainText("Stop this bench?");
  });

  test("deleting a bench spells out what is destroyed", async ({ page }) => {
    const lab = await newLab(page);
    benchName = (await createTestBench(page, lab.name, { status: "Running" })).name;

    const detail = new LabDetailPage(page);
    await detail.goto(labName);
    await detail.openOverflow();
    await detail.menuItem("Delete bench").click();

    await expect(detail.dialog()).toContainText("Docker volume");
    await expect(detail.dialog()).toContainText("database");
  });

  test("both status axes render for a deployed bench", async ({ page }) => {
    const lab = await newLab(page);
    benchName = (
      await createTestBench(page, lab.name, {
        status: "Running",
        container_health: "Unhealthy",
      })
    ).name;

    const detail = new LabDetailPage(page);
    await detail.goto(labName);

    // §8.7: bench status and container health are independent signals.
    await expect(detail.containerStatus).toContainText("Running");
    await expect(detail.testId("container-health")).toContainText("Unhealthy");
  });

  test("a never-polled bench reads Unknown, not a blank pill", async ({ page }) => {
    const lab = await newLab(page);
    benchName = (await createTestBench(page, lab.name, { status: "Running" })).name;

    const detail = new LabDetailPage(page);
    await detail.goto(labName);

    await expect(detail.testId("container-health")).toContainText("Unknown");
    await expect(detail.testId("health-checked")).toContainText("never checked");
  });

  test("a stopped container shows em-dashes, not zeros", async ({ page }) => {
    const lab = await newLab(page);
    benchName = (await createTestBench(page, lab.name, { status: "Stopped" })).name;

    const detail = new LabDetailPage(page);
    await detail.goto(labName);

    await expect(detail.testId("cpu-meter")).toContainText("—");
    await expect(detail.testId("cpu-meter")).toContainText("container not running");
    await expect(detail.testId("cpu-meter")).not.toContainText("0%");
  });

  test("every secret is masked until one toggle reveals them", async ({ page }) => {
    const lab = await newLab(page);
    benchName = (await createTestBench(page, lab.name, { status: "Running" })).name;

    const detail = new LabDetailPage(page);
    await detail.goto(labName);

    // §8.8: a real mask, not a "••••" string rendered beside a plaintext copy.
    const sshPassword = detail.secret("ssh-password");
    await expect(sshPassword).toHaveAttribute("type", "password");
    await detail.revealSecrets.click();
    await expect(sshPassword).toHaveAttribute("type", "text");
  });

  test("the reveal resets on navigation", async ({ page }) => {
    const lab = await newLab(page);
    benchName = (await createTestBench(page, lab.name, { status: "Running" })).name;

    const detail = new LabDetailPage(page);
    await detail.goto(labName);
    await detail.revealSecrets.click();

    await detail.gotoFrontend("/labs");
    await detail.goto(labName);
    await expect(detail.secret("ssh-password")).toHaveAttribute("type", "password");
  });

  test("a failed build names the step and the reason", async ({ page }) => {
    await newLab(page, { status: "Error" });
    buildLogName = (
      await createTestBuildLog(
        page,
        labName,
        "=== Installing apps ===\n=== Build failed: app install exited 128 ==="
      )
    ).name;

    const detail = new LabDetailPage(page);
    await detail.goto(labName);

    await expect(detail.errorBanner).toBeVisible();
    await expect(detail.testId("failure-step")).toContainText("Installing apps");
    await expect(detail.testId("failure-reason")).toContainText("app install exited 128");
  });

  test("sites tab offers an empty state that explains itself", async ({ page }) => {
    await newLab(page);
    const detail = new LabDetailPage(page);
    await detail.goto(labName);

    await detail.clickTab("Sites");
    await expect(page.getByText("No site yet")).toBeVisible();
  });

  test("the log tabs are named, not positional", async ({ page }) => {
    await newLab(page);
    const detail = new LabDetailPage(page);
    await detail.goto(labName);

    await detail.clickTab("Deploy log");
    await expect(page.getByText("No deploy has run yet")).toBeVisible();
    await detail.clickTab("Build log");
    await expect(page.getByText("No image build has run yet")).toBeVisible();
  });
});
