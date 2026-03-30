import { type Page, type Locator, expect } from "@playwright/test";
import { BasePage } from "./BasePage";

export class BenchInstancesPage extends BasePage {
  readonly heading: Locator;
  readonly listView: Locator;
  readonly emptyState: Locator;
  readonly loadingState: Locator;

  constructor(page: Page) {
    super(page);
    this.heading = page.locator("h1", { hasText: "Bench Instances" });
    this.listView = page.locator(".list-view, [class*='list']").first();
    this.emptyState = page.locator("text=No bench instances found");
    this.loadingState = page.locator("text=Loading...");
  }

  async goto() {
    await this.gotoFrontend("/bench-instances");
  }

  async expectPageLoaded() {
    await expect(this.heading).toBeVisible({ timeout: 15_000 });
  }

  async getRowCount(): Promise<number> {
    const rows = this.page.locator(".list-row, [class*='row']");
    return rows.count();
  }

  async expectBenchVisible(benchName: string) {
    await expect(
      this.page.locator(`text=${benchName}`)
    ).toBeVisible();
  }

  async expectStatusBadge(benchName: string, status: string) {
    const row = this.page.locator(`tr, [class*='row']`).filter({
      hasText: benchName,
    });
    await expect(row.locator(`text=${status}`)).toBeVisible();
  }

  async expectEmptyState() {
    await expect(this.emptyState).toBeVisible();
  }
}
