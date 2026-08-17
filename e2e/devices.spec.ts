import { test, expect } from "@playwright/test";
import { DevicesPage } from "./pages/DevicesPage";
import { createTestDevice, removeTestDevice } from "./fixtures/test-data";

test.describe("Devices Page", () => {
  test("loads with the journey copy and the status banner", async ({ page }) => {
    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.expectPageLoaded();

    await expect(
      page.locator("text=Bench instances live on a private WireGuard network")
    ).toBeVisible();
    await expect(devicesPage.bannerTitle).toBeVisible();
    await expect(devicesPage.bannerAction).toBeVisible();
  });

  test("offers the add action in the header and at the end of the list", async ({
    page,
  }) => {
    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.expectPageLoaded();

    await expect(devicesPage.addDeviceButton).toBeVisible();
    await expect(devicesPage.addAnotherMachine).toBeVisible();
  });

  test("explains the journey and offers the connection test", async ({
    page,
  }) => {
    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.expectPageLoaded();

    await expect(devicesPage.howThisWorks).toBeVisible();
    await expect(
      devicesPage.howThisWorks.locator("text=Register the machine here")
    ).toBeVisible();
    await expect(devicesPage.connectionTest).toBeVisible();
    await expect(devicesPage.runConnectionTest).toBeVisible();
  });

  test("empty state states the fix when no device is registered", async ({
    page,
  }) => {
    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.waitForPageLoad();

    if ((await devicesPage.getDeviceCount()) === 0) {
      await expect(devicesPage.emptyState).toBeVisible();
    }
  });

  test("add dialog focuses the name field and offers both handoffs", async ({
    page,
  }) => {
    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.expectPageLoaded();

    await devicesPage.openAddDeviceDialog();

    await expect(page.locator('[data-test="device-name"]')).toBeFocused();
    await expect(page.locator('[data-test="device-type"]')).toBeVisible();
    // The QR only exists once the peer does; until then the panel says so.
    await expect(page.locator('[data-test="device-qr-placeholder"]')).toBeVisible();
    await expect(page.locator('[data-test="download-conf"]')).toBeDisabled();
    await expect(page.locator('[data-test="register-and-connect"]')).toBeVisible();
  });

  test("device row shows name, type, IP and transfer", async ({ page }) => {
    const deviceName = `e2e-row-${Date.now().toString(36)}`;
    const device = await createTestDevice(page, {
      device_name: deviceName,
      device_type: "Desktop",
    });

    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.expectPageLoaded();

    const row = devicesPage.deviceRow(deviceName);
    await expect(row).toBeVisible({ timeout: 10_000 });
    await expect(row).toContainText("Desktop");
    await expect(row).toContainText("↓");
    await expect(devicesPage.deviceCount).toContainText("machine");

    await removeTestDevice(page, device.name);
  });

  test("the config dialog renders the tunnel file and a QR", async ({ page }) => {
    const deviceName = `e2e-config-${Date.now().toString(36)}`;
    const device = await createTestDevice(page, { device_name: deviceName });

    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.expectPageLoaded();
    await devicesPage.openDeviceConfig(deviceName);

    await expect(page.locator('[data-test="config-text"]')).toContainText(
      "[Interface]"
    );
    await expect(page.locator('[data-test="device-qr-canvas"]')).toBeVisible();

    await removeTestDevice(page, device.name);
  });

  test("the connection test names a specific failing check", async ({ page }) => {
    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.expectPageLoaded();
    await devicesPage.runTest();

    // Every check is reported, pass or fail, each with its own hint.
    for (const check of [
      "vpn_server",
      "device_registered",
      "peer_active",
      "handshake",
    ]) {
      await expect(devicesPage.checkRow(check)).toBeVisible();
    }
    await expect(devicesPage.testVerdict).toContainText(/check|passed/i);
  });

  test("the banner never hides the action, it labels it", async ({ page }) => {
    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.expectPageLoaded();

    await expect(devicesPage.bannerAction).toBeEnabled();
    await expect(devicesPage.bannerAction).toHaveText(
      /Add this device|Check again/
    );
  });

  test.fixme("delete shows confirmation dialog", async ({ page }) => {
    // frappe-ui Dropdown uses Reka UI which handles onSelect via internal
    // event dispatch — Playwright's click doesn't trigger the Vue onClick
    // handler. This test works in headed mode but fails in headless.
    const deviceName = `e2e-remove-${Date.now().toString(36)}`;
    const device = await createTestDevice(page, { device_name: deviceName });

    const devicesPage = new DevicesPage(page);
    await devicesPage.goto();
    await devicesPage.expectPageLoaded();
    await devicesPage.openDeviceMenu(deviceName);
    await devicesPage.clickMenuItem("Remove device");

    await expect(page.locator("text=loses VPN access immediately")).toBeVisible({
      timeout: 8_000,
    });

    await removeTestDevice(page, device.name);
  });
});
