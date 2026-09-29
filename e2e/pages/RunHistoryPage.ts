import { type Locator, type Page } from "@playwright/test";
import { BasePage } from "./BasePage";

export class RunHistoryPage extends BasePage {
  readonly root: Locator;
  readonly table: Locator;
  readonly retentionNote: Locator;
  readonly backLink: Locator;
  readonly emptyAction: Locator;

  constructor(
    page: Page,
    private readonly key: "deploy-history",
    private readonly path: string
  ) {
    super(page);
    this.root = this.testId(key);
    this.table = this.testId(`${key}-table`);
    this.retentionNote = this.testId("retention-note");
    this.backLink = this.testId("back-link");
    this.emptyAction = this.testId("empty-action");
  }

  static deploy(page: Page) {
    return new RunHistoryPage(page, "deploy-history", "/deploy-logs");
  }

  async goto() {
    await this.gotoFrontend(this.path);
    await this.root.waitFor({ timeout: 15_000 });
  }

  row(logName: string): Locator {
    return this.testId(`run-${logName}`);
  }
}
