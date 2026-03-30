import { type Page, type Locator, expect } from "@playwright/test";
import { BasePage } from "./BasePage";

export class DevicesPage extends BasePage {
  readonly heading: Locator;
  readonly addDeviceButton: Locator;
  readonly deviceCards: Locator;
  readonly emptyState: Locator;
  readonly loadingState: Locator;

  constructor(page: Page) {
    super(page);
    this.heading = page.locator("h1", { hasText: "VPN Devices" });
    this.addDeviceButton = page.getByRole("button", { name: "Add Device" });
    this.deviceCards = page.locator(".grid > div.flex.items-center");
    this.emptyState = page.locator("text=No devices registered yet");
    this.loadingState = page.locator("text=Loading devices...");
  }

  async goto() {
    await this.gotoFrontend("/devices");
  }

  async expectPageLoaded() {
    await expect(this.heading).toBeVisible({ timeout: 15_000 });
  }

  async getDeviceCount(): Promise<number> {
    await this.waitForPageLoad();
    return this.deviceCards.count();
  }

  async openAddDeviceDialog() {
    await this.addDeviceButton.click();
    await expect(
      this.page.locator('input[placeholder*="My Laptop"]')
    ).toBeVisible({ timeout: 5_000 });
  }

  async expectDeviceVisible(deviceName: string) {
    await expect(
      this.page.locator(`.font-medium:has-text("${deviceName}")`)
    ).toBeVisible({ timeout: 10_000 });
  }

  async openDeviceMenu(deviceName: string) {
    const card = this.deviceCards.filter({ hasText: deviceName });
    await card
      .locator('button[aria-haspopup="menu"]')
      .click();
    await this.page.waitForTimeout(300);
  }

  async clickMenuItem(label: string) {
    await this.page.locator(`li:has-text("${label}")`).click();
  }

  async expectDeviceRemoved(deviceName: string) {
    await expect(
      this.page.locator(`.font-medium:has-text("${deviceName}")`)
    ).not.toBeVisible({ timeout: 10_000 });
  }
}
