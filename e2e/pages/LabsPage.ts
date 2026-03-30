import { type Page, type Locator, expect } from "@playwright/test";
import { BasePage } from "./BasePage";

export class LabsPage extends BasePage {
  readonly heading: Locator;
  readonly searchInput: Locator;
  readonly statusCombobox: Locator;
  readonly versionCombobox: Locator;
  readonly emptyState: Locator;
  readonly loadingState: Locator;

  constructor(page: Page) {
    super(page);
    this.heading = page.locator("h1", { hasText: "Labs" });
    this.searchInput = page.locator(
      'input[placeholder*="Search by Lab ID"]'
    );
    this.statusCombobox = page
      .locator('button[role="combobox"]')
      .filter({ hasText: /Status/ })
      .first();
    this.versionCombobox = page
      .locator('button[role="combobox"]')
      .filter({ hasText: /Version/ })
      .first();
    this.emptyState = page.locator("text=No labs");
    this.loadingState = page.locator("text=Loading...");
  }

  async goto() {
    await this.gotoFrontend("/labs");
  }

  async search(query: string) {
    await this.searchInput.fill(query);
    await this.page.waitForTimeout(300);
  }

  async clearSearch() {
    await this.searchInput.clear();
    await this.page.waitForTimeout(300);
  }

  async selectComboboxOption(
    combobox: Locator,
    optionLabel: string
  ) {
    await combobox.click();
    await this.page
      .locator('[role="option"]', { hasText: optionLabel })
      .click();
    await this.page.waitForTimeout(300);
  }

  async filterByStatus(status: string) {
    await this.selectComboboxOption(this.statusCombobox, status);
  }

  async filterByVersion(version: string) {
    await this.selectComboboxOption(this.versionCombobox, version);
  }

  async getNewLabButton(): Promise<Locator> {
    return this.page.locator('button:has-text("New Lab")');
  }

  async expectNewLabButtonVisible() {
    await expect(
      this.page.locator('button:has-text("New Lab")')
    ).toBeVisible({ timeout: 10_000 });
  }

  async expectNewLabButtonHidden() {
    await expect(
      this.page.locator('button:has-text("New Lab")')
    ).not.toBeVisible();
  }
}
