import { type Locator, type Page, expect } from "@playwright/test";
import { BasePage } from "./BasePage";

/**
 * Instances table. Selects on `data-test` only — the previous version matched
 * `.list-view, [class*='list']`, which coupled the suite to frappe-ui's
 * internal class names.
 */
export class BenchInstancesPage extends BasePage {
  readonly page: Page;
  readonly root: Locator;
  readonly table: Locator;
  readonly scopeLine: Locator;
  readonly deployHistoryButton: Locator;

  constructor(page: Page) {
    super(page);
    this.page = page;
    this.root = this.testId("instances");
    this.table = this.testId("instances-table");
    this.scopeLine = this.testId("instances-scope");
    this.deployHistoryButton = this.testId("deploy-history");
  }

  async goto() {
    await this.gotoFrontend("/bench-instances");
    await this.root.waitFor({ timeout: 15_000 });
  }

  row(benchName: string): Locator {
    return this.testId(`bench-${benchName}`);
  }

  /** Every status pill in a row — status and container health are separate badges. */
  badge(status: string): Locator {
    return this.testId(`status-${status}`);
  }

  async expectRowVisible(benchName: string) {
    await expect(this.row(benchName)).toBeVisible({ timeout: 10_000 });
  }

  async expectRowHidden(benchName: string) {
    await expect(this.row(benchName)).toHaveCount(0);
  }

  /** Both axes render independently: a Running bench may still be Unhealthy. */
  async expectBothStatusAxes(status: string, health: string) {
    await expect(this.badge(status).first()).toBeVisible();
    await expect(this.badge(health).first()).toBeVisible();
  }

  async expectScopedTo(text: string | RegExp) {
    await expect(this.scopeLine).toContainText(text);
  }

  async expectEmptyState() {
    await expect(this.table).toHaveCount(0);
    await expect(this.root).toContainText("No instances yet");
  }
}
