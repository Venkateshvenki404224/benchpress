import { type Locator, type Page, expect } from "@playwright/test";
import { BasePage } from "./BasePage";

/**
 * Labs table. Every locator is a `data-test` hook, so the next redesign of the
 * markup does not break this suite — the previous version matched a search
 * placeholder string and a heading tag, both of which changed in phase 2.
 */
export class LabsPage extends BasePage {
  readonly page: Page;
  readonly root: Locator;
  readonly table: Locator;
  readonly searchInput: Locator;
  readonly statusFilter: Locator;
  readonly versionFilter: Locator;
  readonly ownerFilter: Locator;
  readonly onboardingPanel: Locator;
  readonly clearFilters: Locator;
  readonly newLabButton: Locator;
  readonly fromTemplateButton: Locator;
  readonly buildHistoryButton: Locator;

  constructor(page: Page) {
    super(page);
    this.page = page;
    this.root = this.testId("labs");
    this.table = this.testId("labs-table");
    // FormControl forwards attributes to the input itself, so the hook is the input.
    this.searchInput = this.testId("labs-search");
    this.statusFilter = this.testId("filter-status");
    this.versionFilter = this.testId("filter-version");
    this.ownerFilter = this.testId("filter-owner");
    this.onboardingPanel = this.testId("onboarding-panel");
    this.clearFilters = this.testId("clear-filters");
    this.newLabButton = this.testId("new-lab");
    this.fromTemplateButton = this.testId("from-template");
    this.buildHistoryButton = this.testId("build-history");
  }

  async goto() {
    await this.gotoFrontend("/labs");
    await this.root.waitFor({ timeout: 15_000 });
  }

  row(labName: string): Locator {
    return this.testId(`lab-${labName}`);
  }

  async search(query: string) {
    await this.searchInput.fill(query);
  }

  async clearSearch() {
    await this.searchInput.fill("");
  }

  /** Pick an option in one of the three filter dropdowns. */
  async selectFilter(filter: Locator, optionLabel: string) {
    await filter.click();
    await this.page.getByRole("option", { name: optionLabel, exact: true }).click();
  }

  async filterByStatus(status: string) {
    await this.selectFilter(this.statusFilter, status);
  }

  async filterByVersion(version: string) {
    await this.selectFilter(this.versionFilter, version);
  }

  async expectRowVisible(labName: string) {
    await expect(this.row(labName)).toBeVisible({ timeout: 10_000 });
  }

  async expectRowHidden(labName: string) {
    await expect(this.row(labName)).toHaveCount(0);
  }

  /** The status pill for a row — proves the status is a badge, not grey text. */
  statusBadge(labName: string, status: string): Locator {
    return this.testId(`status-${status}`);
  }

  async expectAdminActionsVisible() {
    await expect(this.newLabButton).toBeVisible({ timeout: 10_000 });
    await expect(this.buildHistoryButton).toBeVisible();
  }

  async expectAdminActionsHidden() {
    await expect(this.newLabButton).toHaveCount(0);
    await expect(this.buildHistoryButton).toHaveCount(0);
  }
}
