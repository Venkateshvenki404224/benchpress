import { expect, test } from "@playwright/test";
import { createTestBench, createTestLab, deleteTestDoc } from "./fixtures/test-data";
import { LabsPage } from "./pages/LabsPage";

/**
 * The countdown is a renderer of a server instant, never a decrementing counter.
 *
 * Everything here stages `expires_at_ts` directly rather than deploying, because the property
 * under test is the rendering of a deadline and not how the deadline was bought. The epoch
 * integer is the contract: a datetime string would parse as browser-local in V8 and has
 * historically been `Invalid Date` in Safari.
 */

let labName: string;
let benchName: string | null = null;

const COUNTDOWN = '[data-test="lease-countdown"]';

/** Epoch seconds, the unit `Bench Instance.expires_at_ts` stores. */
function inSeconds(seconds: number): number {
  return Math.floor(Date.now() / 1000) + seconds;
}

async function labWithBench(page, benchOverrides: Record<string, unknown>) {
  const lab = await createTestLab(page, {
    title: "E2E Lease Lab",
    lab_id: `e2e-lease-${Date.now().toString(36)}`,
    frappe_version: "version-16",
    status: "Ready",
  });
  labName = lab.name;
  const bench = await createTestBench(page, lab.name, {
    status: "Running",
    ...benchOverrides,
  });
  benchName = bench.name;
  return { lab, bench };
}

test.describe("Lease countdown", () => {
  test.afterEach(async ({ page }) => {
    if (benchName) {
      await deleteTestDoc(page, "Bench Instance", benchName);
      benchName = null;
    }
    if (labName) {
      await deleteTestDoc(page, "Lab", labName);
    }
  });

  test("shows the time left on a bench that holds a lease", async ({ page }) => {
    await labWithBench(page, { expires_at_ts: inSeconds(25 * 60), lease_state: "Active" });

    const labsPage = new LabsPage(page);
    await labsPage.goto();

    const countdown = page.locator(COUNTDOWN).first();
    await expect(countdown).toBeVisible();
    await expect(countdown).toContainText(/Lease ends in 2[45]:\d{2}/);
  });

  test("counts down rather than holding a stale first paint", async ({ page }) => {
    await labWithBench(page, { expires_at_ts: inSeconds(120), lease_state: "Active" });

    const labsPage = new LabsPage(page);
    await labsPage.goto();

    const countdown = page.locator(COUNTDOWN).first();
    await expect(countdown).toBeVisible();
    const first = await countdown.innerText();

    // Recompute-never-decrement means the next tick is derived from the clock, so it must move.
    await expect(countdown).not.toHaveText(first, { timeout: 5_000 });
  });

  test("a bench with no lease renders no countdown at all", async ({ page }) => {
    await labWithBench(page, { expires_at_ts: 0 });

    const labsPage = new LabsPage(page);
    await labsPage.goto();

    await expect(page.locator(COUNTDOWN)).toHaveCount(0);
  });

  test("client zero says stopping and does not claim the bench stopped", async ({ page }) => {
    // Already past. The browser reaching zero is a rendering event with no authority: the row
    // still says Running, and only the server may say otherwise.
    await labWithBench(page, { expires_at_ts: inSeconds(-30), lease_state: "Active" });

    const labsPage = new LabsPage(page);
    await labsPage.goto();

    const countdown = page.locator(COUNTDOWN).first();
    await expect(countdown).toBeVisible();
    await expect(countdown).toContainText("Lease ended");
    await expect(page.locator(COUNTDOWN)).not.toContainText("Lease ends in");
  });
});
