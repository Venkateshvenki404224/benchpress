import { test, expect } from "@playwright/test";
import { LabDetailPage } from "./pages/LabDetailPage";
import {
  createTestBench,
  createTestBuildLog,
  createTestDeployLog,
  createTestLab,
  deleteTestDoc,
  deployStepLine,
} from "./fixtures/test-data";

let labName: string;
let benchName: string | null = null;
let buildLogName: string | null = null;
let deployLogName: string | null = null;

/** A run that reached the WireGuard peer and is still working on it. */
const MID_RUN_LOG = [
  "=== Deploy started ===",
  deployStepLine(1, "Checking shared infrastructure", "infrastructure", 0.2),
  "MariaDB reachable at benchpress-mariadb:3306",
  deployStepLine(2, "Preparing the lab image", "image", 3.4),
  "Using cached lab image: benchpress/e2e:version-16",
  deployStepLine(3, "Creating the container", "container", 9.1),
  deployStepLine(4, "Waiting for the container IP", "container_ip", 11.6),
  "container_ip 172.30.0.99",
  deployStepLine(5, "Configuring the WireGuard peer", "vpn_peer", 14.2),
].join("\n");

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
    // The deploy log links its bench, so it goes first or the bench delete
    // fails on a link that still exists.
    if (deployLogName) {
      await deleteTestDoc(page, "Deploy Log", deployLogName);
      deployLogName = null;
    }
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

  test("the deploy log tab renders the pipeline the log recorded", async ({ page }) => {
    const lab = await newLab(page);
    benchName = (await createTestBench(page, lab.name, { status: "Deploying" })).name;
    deployLogName = (await createTestDeployLog(page, benchName, MID_RUN_LOG)).name;

    const detail = new LabDetailPage(page);
    await detail.goto(labName);
    await detail.clickTab("Deploy log");

    await expect(detail.pipeline).toBeVisible();
    // State is derived from the emitted step lines, never from a timer.
    await detail.expectStepState("infrastructure", "done");
    await detail.expectStepState("vpn_peer", "active");
    await detail.expectStepState("site", "pending");
    await detail.expectStepState("complete", "pending");
    await expect(detail.testId("step-detail-container_ip")).toContainText("172.30.0.99");
    await expect(detail.testId("step-timing-image")).toHaveText("6s");
  });

  test("the raw log sits collapsed under the stepper", async ({ page }) => {
    const lab = await newLab(page);
    benchName = (await createTestBench(page, lab.name, { status: "Deploying" })).name;
    deployLogName = (await createTestDeployLog(page, benchName, MID_RUN_LOG)).name;

    const detail = new LabDetailPage(page);
    await detail.goto(labName);
    await detail.clickTab("Deploy log");

    await expect(detail.rawLog).toBeVisible();
    await expect(detail.testId("raw-log-body")).toHaveCount(0);
    await expect(detail.testId("raw-log-count")).toHaveText("9 lines");

    await detail.openRawLog();
    await expect(detail.testId("raw-log-body")).toContainText("container_ip 172.30.0.99");
  });

  test("a failed run marks the failing step and nothing after it", async ({ page }) => {
    const lab = await newLab(page);
    benchName = (await createTestBench(page, lab.name, { status: "Error" })).name;
    deployLogName = (
      await createTestDeployLog(
        page,
        benchName,
        [
          MID_RUN_LOG,
          deployStepLine(6, "Writing common_site_config.json", "site_config", 15.0),
          deployStepLine(7, "Creating the site", "site", 16.2),
          "=== Deploy failed: bench new-site failed (exit 1) ===",
          "Cleanup: nothing to roll back — no container was created",
        ].join("\n"),
        "error"
      )
    ).name;

    const detail = new LabDetailPage(page);
    await detail.goto(labName);
    await detail.clickTab("Deploy log");

    await detail.expectStepState("site", "failed");
    await detail.expectStepState("assets", "pending");
    await expect(detail.testId("step-timing-site")).toHaveText("failed");
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
