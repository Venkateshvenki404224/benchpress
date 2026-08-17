import { expect, test } from "@playwright/test";
import { deleteTestDoc } from "./fixtures/test-data";
import { NewLabPage } from "./pages/NewLabPage";

/**
 * The New lab form. The cases that matter are the ones the old form got wrong:
 * a lab ID the backend would reject, a CPU count below the baseline, and a save
 * error that used to disappear into an empty `catch`.
 */
test.describe("New lab", () => {
  test("derives a read-only lab ID from the title", async ({ page }) => {
    const newLab = new NewLabPage(page);
    await newLab.goto();

    await newLab.fillTitle("Support Sandbox v2");
    expect(await newLab.labIdValue()).toBe("support-sandbox-v2");
    await expect(newLab.labId).toHaveAttribute("readonly", /.*/);
  });

  test("the summary rail recomputes as the form is edited", async ({ page }) => {
    const newLab = new NewLabPage(page);
    await newLab.goto();

    await newLab.fillTitle("Summary Lab");
    await expect(newLab.summary).toContainText("benchpress/summary-lab:latest");
    await expect(newLab.summary).toContainText("no extra apps");

    await newLab.addApp.click();
    await newLab.appName(0).fill("erpnext");
    await newLab.appUrl(0).fill("https://github.com/frappe/erpnext");
    await newLab.appBranch(0).fill("version-16");
    await expect(newLab.summary).toContainText("with erpnext");
  });

  test("every hook on the form addresses exactly one element", async ({ page }) => {
    // frappe-ui's Textarea inherits `$attrs` on its root as well as its
    // textarea, so a `data-test` handed to that control silently matches twice
    // and Playwright's strict mode fails on it.
    const newLab = new NewLabPage(page);
    await newLab.goto();

    const duplicates = await page.evaluate(() => {
      const seen = new Map<string, number>();
      for (const element of document.querySelectorAll("[data-test]")) {
        const name = element.getAttribute("data-test") as string;
        seen.set(name, (seen.get(name) ?? 0) + 1);
      }
      return [...seen].filter(([, count]) => count > 1).map(([name]) => name);
    });
    expect(duplicates).toEqual([]);
    await expect(newLab.description).toHaveCount(1);
  });

  test("an app row can be removed again", async ({ page }) => {
    const newLab = new NewLabPage(page);
    await newLab.goto();

    await newLab.addApp.click();
    await expect(newLab.appRow(0)).toBeVisible();
    await newLab.removeApp(0).click();
    await expect(newLab.appRow(0)).toHaveCount(0);
  });

  test("a title that cannot become a valid lab ID is caught in the form", async ({ page }) => {
    const newLab = new NewLabPage(page);
    await newLab.goto();

    // Nothing in "!!!" survives the Docker tag grammar, so the ID is empty.
    await newLab.fillTitle("!!!");
    expect(await newLab.labIdValue()).toBe("");

    await newLab.saveDraft.click();
    await expect(newLab.root).toContainText("A lab ID is required");
    // The form never reached the server: it is still the form.
    await expect(page).toHaveURL(/\/labs\/new$/);
  });

  test("a CPU count below one is rejected inline, not by the server", async ({ page }) => {
    const newLab = new NewLabPage(page);
    await newLab.goto();

    await newLab.fillTitle("Cpu Guard Lab");
    await newLab.cpuCores.fill("0");
    await newLab.saveDraft.click();

    await expect(newLab.root).toContainText("CPU cores must be at least 1");
    await expect(page).toHaveURL(/\/labs\/new$/);
  });

  test("saves a draft and opens the lab it created", async ({ page }) => {
    const labId = `e2e-new-lab-${Date.now().toString(36)}`;
    const newLab = new NewLabPage(page);
    await newLab.goto();

    await newLab.fillTitle(labId);
    await newLab.saveDraft.click();

    await page.waitForURL(`**/labs/${labId}`, { timeout: 20_000 });
    await deleteTestDoc(page, "Lab", labId);
  });

  test("a save that fails says so instead of silently doing nothing", async ({ page }) => {
    const labId = `e2e-dup-lab-${Date.now().toString(36)}`;
    const newLab = new NewLabPage(page);

    await newLab.goto();
    await newLab.fillTitle(labId);
    await newLab.saveDraft.click();
    await page.waitForURL(`**/labs/${labId}`, { timeout: 20_000 });

    // The same title a second time collides on the lab ID, which is the name.
    await newLab.goto();
    await newLab.fillTitle(labId);
    await newLab.saveDraft.click();

    await expect(newLab.root).toContainText("already exists", { timeout: 15_000 });
    await expect(page).toHaveURL(/\/labs\/new$/);
    await deleteTestDoc(page, "Lab", labId);
  });
});
