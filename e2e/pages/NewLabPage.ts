import { type Locator, type Page } from "@playwright/test";
import { BasePage } from "./BasePage";

/**
 * The New lab form.
 *
 * `FormControl` forwards unknown attributes to the `<input>` itself, so every
 * hook below addresses the control, not a wrapper.
 */
export class NewLabPage extends BasePage {
  readonly root: Locator;
  readonly title: Locator;
  readonly labId: Locator;
  readonly description: Locator;
  readonly versions: Locator;
  readonly cpuCores: Locator;
  readonly addApp: Locator;
  readonly codeServer: Locator;
  readonly ssh: Locator;
  readonly summary: Locator;
  readonly saveAndBuild: Locator;
  readonly saveDraft: Locator;
  readonly backLink: Locator;

  constructor(page: Page) {
    super(page);
    this.root = this.testId("new-lab");
    this.title = this.testId("lab-title");
    this.labId = this.testId("lab-id");
    // The hook sits on the wrapper — frappe-ui's Textarea would otherwise carry
    // the same `data-test` on both its root div and the textarea itself.
    this.description = this.testId("lab-description").locator("textarea");
    this.versions = this.testId("frappe-version");
    this.cpuCores = this.testId("cpu_cores");
    this.addApp = this.testId("add-app");
    this.codeServer = this.testId("enable-code-server");
    this.ssh = this.testId("enable-ssh");
    this.summary = this.testId("new-lab-summary");
    this.saveAndBuild = this.testId("save-and-build");
    this.saveDraft = this.testId("save-draft");
    this.backLink = this.testId("back-link");
  }

  async goto() {
    await this.gotoFrontend("/labs/new");
    await this.root.waitFor({ timeout: 15_000 });
  }

  appRow(index: number): Locator {
    return this.testId(`app-row-${index}`);
  }

  appName(index: number): Locator {
    return this.testId(`app-name-${index}`);
  }

  appUrl(index: number): Locator {
    return this.testId(`app-url-${index}`);
  }

  appBranch(index: number): Locator {
    return this.testId(`app-branch-${index}`);
  }

  removeApp(index: number): Locator {
    return this.testId(`remove-app-${index}`);
  }

  async fillTitle(value: string) {
    await this.title.fill(value);
  }

  async labIdValue(): Promise<string> {
    return this.labId.inputValue();
  }

  async summaryText(): Promise<string> {
    return (await this.summary.innerText()).trim();
  }
}
