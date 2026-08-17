import { expect, test } from "@playwright/test";
import { SettingsPage } from "./pages/SettingsPage";

/** Settings is a dialog with three grouped panels and one save bar. */
test.describe("Settings", () => {
  test("opens over Overview from /settings and switches between the groups", async ({
    page,
  }) => {
    const settings = new SettingsPage(page);
    await settings.goto();

    await expect(page).toHaveURL(/\/settings$/);
    for (const group of ["domains", "docker", "container"]) {
      await expect(settings.tab(group)).toBeVisible();
      await settings.openTab(group);
      await expect(settings.group(group)).toBeVisible();
    }
    await expect(settings.lastSaved).toBeVisible();
  });

  test("closing the dialog takes the URL off /settings", async ({ page }) => {
    const settings = new SettingsPage(page);
    await settings.goto();

    await settings.close.click();
    await expect(settings.root).toBeHidden();
    await expect(page).toHaveURL(/\/frontend\/?$/);
  });

  test("save and discard stay disabled until something changes", async ({ page }) => {
    const settings = new SettingsPage(page);
    await settings.goto();
    await settings.openTab("docker");

    await expect(settings.save).toBeDisabled();
    await expect(settings.discard).toBeDisabled();

    const original = await settings.traefikNetwork.inputValue();
    await settings.traefikNetwork.fill(`${original}-edited`);
    await expect(settings.save).toBeEnabled();

    await settings.discard.click();
    await expect(settings.traefikNetwork).toHaveValue(original);
    await expect(settings.save).toBeDisabled();
  });

  test("an empty base domain is refused by the form", async ({ page }) => {
    const settings = new SettingsPage(page);
    await settings.goto();

    const original = await settings.baseDomain.inputValue();
    await settings.baseDomain.fill("");
    await expect(settings.root).toContainText("A base domain is required");

    await settings.baseDomain.fill(original);
    await expect(settings.root).not.toContainText("A base domain is required");
  });

  test("saves and reports who saved it", async ({ page }) => {
    const settings = new SettingsPage(page);
    await settings.goto();
    await settings.openTab("docker");

    const original = await settings.traefikNetwork.inputValue();
    await settings.traefikNetwork.fill(`${original}`.replace(/-e2e$/, "") + "-e2e");
    await settings.save.click();

    await expect(settings.lastSaved).toContainText("Last saved by", { timeout: 15_000 });
    await expect(settings.save).toBeDisabled();

    // Put the network back the way the site had it.
    await settings.traefikNetwork.fill(original);
    await settings.save.click();
    await expect(settings.save).toBeDisabled({ timeout: 15_000 });
  });
});
