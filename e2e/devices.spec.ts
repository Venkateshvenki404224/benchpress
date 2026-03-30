import { test, expect } from "@playwright/test";
import { DevicesPage } from "./pages/DevicesPage";
import {
  createTestDevice,
  removeTestDevice,
} from "./fixtures/test-data";

test.describe("Devices Page", () => {
  test("loads and displays page heading", async ({ page }) => {
    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.expectPageLoaded();

    await expect(
      page.locator(
        "text=Register your devices once to access all lab containers"
      )
    ).toBeVisible();
  });

  test("shows Add Device button", async ({ page }) => {
    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.expectPageLoaded();

    await expect(devicesPage.addDeviceButton).toBeVisible();
  });

  test("shows empty state when no devices exist", async ({ page }) => {
    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.waitForPageLoad();

    const deviceCount = await devicesPage.getDeviceCount();
    if (deviceCount === 0) {
      await expect(devicesPage.emptyState).toBeVisible();
    }
  });

  test("opens Add Device dialog with form fields", async ({ page }) => {
    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.expectPageLoaded();

    await devicesPage.openAddDeviceDialog();

    await expect(
      page.locator('input[placeholder*="My Laptop"]')
    ).toBeVisible();
    await expect(
      page.locator("text=Auto Generate Keypair")
    ).toBeVisible();
  });

  test("auto-generate keypair checkbox toggles public key field", async ({
    page,
  }) => {
    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.expectPageLoaded();

    await devicesPage.openAddDeviceDialog();

    await expect(
      page.locator("text=A keypair will be generated automatically")
    ).toBeVisible();
    await expect(
      page.locator('input[placeholder*="public key"]')
    ).not.toBeVisible();

    await page.locator('input[type="checkbox"]').uncheck();
    await expect(
      page.locator('input[placeholder*="public key"]')
    ).toBeVisible();
  });

  test("device card shows name and type after API creation", async ({
    page,
  }) => {
    const deviceName = `e2e-card-${Date.now().toString(36)}`;
    const device = await createTestDevice(page, {
      device_name: deviceName,
      device_type: "Desktop",
    });

    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.waitForPageLoad();

    await expect(
      page.locator(`.font-medium:has-text("${deviceName}")`)
    ).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("text=Desktop").first()).toBeVisible();
    await expect(page.locator("text=Active").first()).toBeVisible();

    await removeTestDevice(page, device.name);
  });

  test("device dropdown menu has expected options", async ({ page }) => {
    const deviceName = `e2e-menu-${Date.now().toString(36)}`;
    const device = await createTestDevice(page, {
      device_name: deviceName,
    });

    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.waitForPageLoad();

    const card = page
      .locator(".grid > div")
      .filter({ hasText: deviceName });
    await card.locator('button[aria-haspopup="menu"]').click();
    await page.waitForTimeout(300);

    await expect(
      page.locator('[role="menuitem"]:has-text("Show Configuration")')
    ).toBeVisible();
    await expect(
      page.locator('[role="menuitem"]:has-text("Download Tunnel File")')
    ).toBeVisible();
    await expect(
      page.locator('[role="menuitem"]:has-text("Delete")')
    ).toBeVisible();

    await removeTestDevice(page, device.name);
  });

  test.fixme("delete shows confirmation dialog", async ({ page }) => {
    // frappe-ui Dropdown uses Reka UI which handles onSelect via internal
    // event dispatch — Playwright's click doesn't trigger the Vue onClick
    // handler. This test works in headed mode but fails in headless.
    const suffix = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    const deviceName = `e2e-remove-${suffix}`;
    const device = await createTestDevice(page, {
      device_name: deviceName,
    });

    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.waitForPageLoad();

    const card = page
      .locator(".grid > div")
      .filter({ hasText: deviceName });
    await expect(card).toBeVisible({ timeout: 10_000 });

    const menuBtn = card.locator('button[aria-haspopup="menu"]');
    await menuBtn.click();
    const deleteItem = page.locator('[role="menuitem"]:has-text("Delete")');
    await expect(deleteItem).toBeVisible({ timeout: 3_000 });
    await deleteItem.click({ force: true });

    await expect(
      page.locator("text=revoke its VPN access immediately")
    ).toBeVisible({ timeout: 8_000 });

    await removeTestDevice(page, device.name);
  });
});
