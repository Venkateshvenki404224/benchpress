import { type Page, type Locator, expect } from "@playwright/test";
import { BasePage } from "./BasePage";

export class LabDetailPage extends BasePage {
  readonly title: Locator;
  readonly labIdBadge: Locator;
  readonly description: Locator;
  readonly buildImageButton: Locator;
  readonly deployButton: Locator;
  readonly stopButton: Locator;
  readonly dashboardTab: Locator;
  readonly sitesTab: Locator;
  readonly connectionInfo: Locator;
  readonly containerStatus: Locator;
  readonly newSiteButton: Locator;

  constructor(page: Page) {
    super(page);
    this.title = page.locator("h1").first();
    this.labIdBadge = page.locator("code").first();
    this.description = page.locator("p.text-sm.text-ink-gray-6").first();
    this.buildImageButton = page.getByRole("button", {
      name: /Build Image|Building/,
    });
    this.deployButton = page.getByRole("button", { name: "Deploy" });
    this.stopButton = page.getByRole("button", { name: "Stop" });
    this.dashboardTab = page.getByRole("tab", { name: "Dashboard" });
    this.sitesTab = page.getByRole("tab", { name: "Sites" });
    this.connectionInfo = page.locator("text=Connection Information");
    this.containerStatus = page.locator("text=Container Status");
    this.newSiteButton = page.getByRole("button", { name: "New Site" });
  }

  async goto(labId: string) {
    await this.gotoFrontend(`/labs/${labId}`);
  }

  async expectLabLoaded() {
    await expect(this.title).toBeVisible({ timeout: 15_000 });
  }

  async expectLabTitle(title: string) {
    await expect(this.title).toContainText(title);
  }

  async clickTab(name: string) {
    await this.page.getByRole("tab", { name }).click();
    await this.page.waitForTimeout(500);
  }

  async clickBuildImage() {
    await this.buildImageButton.click();
  }

  async clickDeploy() {
    await this.deployButton.click();
    await this.page.waitForTimeout(500);
  }

  async confirmDeploy() {
    const dialog = this.page.locator(".dialog, [class*='dialog']");
    await expect(dialog.locator("text=Deploy Lab")).toBeVisible();
    await dialog.getByRole("button", { name: "Deploy" }).click();
  }

  async clickStop() {
    await this.stopButton.click();
    await this.page.waitForTimeout(500);
  }

  async confirmStop() {
    const dialog = this.page.locator(".dialog, [class*='dialog']");
    await expect(dialog.locator("text=Stop Bench")).toBeVisible();
    await dialog.getByRole("button", { name: "Stop" }).click();
  }

  async expectConnectionInfoVisible() {
    await expect(this.connectionInfo).toBeVisible();
  }

  async expectContainerStatusVisible() {
    await expect(this.containerStatus).toBeVisible();
  }

  async expectNoActiveDeployment() {
    await expect(
      this.page.locator("text=No active deployment")
    ).toBeVisible();
  }

  async getAppBadges(): Promise<string[]> {
    const badges = this.page.locator(
      "text=Installed Apps ~ .flex-wrap .badge, text=Installed Apps ~ div .badge"
    );
    const count = await badges.count();
    const texts: string[] = [];
    for (let i = 0; i < count; i++) {
      texts.push((await badges.nth(i).textContent()) || "");
    }
    return texts;
  }

  async openNewSiteDialog() {
    await this.clickTab("Sites");
    await this.newSiteButton.click();
    await expect(
      this.page.locator("text=Create New Site")
    ).toBeVisible();
  }

  async fillNewSiteForm(siteName: string, apps: string[] = []) {
    await this.page
      .locator('input[placeholder*="mysite"]')
      .fill(siteName);
    for (const app of apps) {
      await this.page.locator(`label:has-text("${app}") input`).check();
    }
  }

  async submitNewSite() {
    await this.page.getByRole("button", { name: "Create Site" }).click();
  }

  async copyConnectionField(label: string) {
    const row = this.page.locator(`label:has-text("${label}")`).locator("..");
    await row.locator('button[class*="copy"], button:has(svg)').click();
  }
}
