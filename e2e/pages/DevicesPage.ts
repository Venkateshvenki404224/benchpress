import { type Page, type Locator, expect } from "@playwright/test";
import { BasePage } from "./BasePage";

export class DevicesPage extends BasePage {
  readonly heading: Locator;
  readonly addDeviceButton: Locator;
  readonly addAnotherMachine: Locator;
  readonly banner: Locator;
  readonly bannerTitle: Locator;
  readonly bannerAction: Locator;
  readonly deviceList: Locator;
  readonly deviceCount: Locator;
  readonly emptyState: Locator;
  readonly howThisWorks: Locator;
  readonly connectionTest: Locator;
  readonly runConnectionTest: Locator;
  readonly testVerdict: Locator;

  constructor(page: Page) {
    super(page);
    this.heading = page.locator("h1", { hasText: "Devices" });
    this.addDeviceButton = page.locator('[data-test="add-device"]');
    this.addAnotherMachine = page.locator('[data-test="add-another-machine"]');
    this.banner = page.locator('[data-test="vpn-status-banner"]');
    this.bannerTitle = page.locator('[data-test="banner-title"]');
    this.bannerAction = page.locator('[data-test="banner-action"]');
    this.deviceList = page.locator('[data-test="device-list"]');
    this.deviceCount = page.locator('[data-test="device-count"]');
    this.emptyState = page.locator("text=No machine can reach your benches yet");
    this.howThisWorks = page.locator('[data-test="how-this-works"]');
    this.connectionTest = page.locator('[data-test="connection-test"]');
    this.runConnectionTest = page.locator('[data-test="run-connection-test"]');
    this.testVerdict = page.locator('[data-test="test-verdict"]');
  }

  async goto() {
    await this.gotoFrontend("/devices");
  }

  async expectPageLoaded() {
    await expect(this.heading).toBeVisible({ timeout: 15_000 });
    await expect(this.banner).toBeVisible({ timeout: 15_000 });
  }

  deviceRow(deviceName: string): Locator {
    return this.page.locator(`[data-test="device-row-${deviceName}"]`);
  }

  async getDeviceCount(): Promise<number> {
    await this.waitForPageLoad();
    return this.page.locator('[data-test^="device-row-"]').count();
  }

  async openAddDeviceDialog() {
    await this.addDeviceButton.click();
    await expect(this.page.locator('[data-test="device-name"]')).toBeVisible({
      timeout: 5_000,
    });
  }

  async expectDeviceVisible(deviceName: string) {
    await expect(this.deviceRow(deviceName)).toBeVisible({ timeout: 10_000 });
  }

  async expectDeviceRemoved(deviceName: string) {
    await expect(this.deviceRow(deviceName)).not.toBeVisible({
      timeout: 10_000,
    });
  }

  async openDeviceMenu(deviceName: string) {
    await this.deviceRow(deviceName).locator('[data-test="device-menu"]').click();
    await this.page.waitForTimeout(300);
  }

  async clickMenuItem(label: string) {
    await this.page.locator(`li:has-text("${label}")`).click();
  }

  async openDeviceConfig(deviceName: string) {
    await this.deviceRow(deviceName).locator('[data-test="device-config"]').click();
    await expect(this.page.locator('[data-test="config-text"]')).toBeVisible({
      timeout: 10_000,
    });
  }

  async runTest() {
    await this.runConnectionTest.click();
    await expect(this.testVerdict).toBeVisible({ timeout: 15_000 });
  }

  checkRow(check: string): Locator {
    return this.page.locator(`[data-test="connection-check-${check}"]`);
  }
}
