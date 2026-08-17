import { type Locator, type Page } from "@playwright/test";
import { BasePage } from "./BasePage";

/**
 * Build history and deploy history are one component with two subjects, so
 * they are one page object addressed by the screen's own `data-test` root.
 */
export class RunHistoryPage extends BasePage {
  readonly root: Locator;
  readonly table: Locator;
  readonly retentionNote: Locator;
  readonly backLink: Locator;
  readonly emptyAction: Locator;

  constructor(
    page: Page,
    private readonly key: "build-history" | "deploy-history",
    private readonly path: string
  ) {
    super(page);
    this.root = this.testId(key);
    this.table = this.testId(`${key}-table`);
    this.retentionNote = this.testId("retention-note");
    this.backLink = this.testId("back-link");
    this.emptyAction = this.testId("empty-action");
  }

  static build(page: Page) {
    return new RunHistoryPage(page, "build-history", "/build-logs");
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
