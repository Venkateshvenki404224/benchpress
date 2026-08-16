import { type Page, type Locator, expect } from "@playwright/test";
import { BasePage } from "./BasePage";

/**
 * Lab detail, addressed entirely through `data-test`.
 *
 * The previous version matched `p.text-sm.text-ink-gray-6`, `.dialog`,
 * `button:has(svg)` and an input placeholder — every one of which the redesign
 * moved. Nothing here asserts on a class, a tag or a heading.
 */
export class LabDetailPage extends BasePage {
  readonly title: Locator;
  readonly labId: Locator;
  readonly primaryAction: Locator;
  readonly overflowTrigger: Locator;
  readonly containerStatus: Locator;
  readonly connectionDetails: Locator;
  readonly revealSecrets: Locator;
  readonly errorBanner: Locator;

  constructor(page: Page) {
    super(page);
    this.title = this.testId("lab-title");
    this.labId = this.testId("lab-id");
    this.primaryAction = this.testId("primary-action");
    this.overflowTrigger = this.testId("lab-overflow");
    this.containerStatus = this.testId("container-status");
    this.connectionDetails = this.testId("connection-details");
    this.revealSecrets = this.testId("reveal-secrets");
    this.errorBanner = this.testId("lab-error-banner");
  }

  async goto(labName: string) {
    await this.gotoFrontend(`/labs/${encodeURIComponent(labName)}`);
    await this.expectLoaded();
  }

  async expectLoaded() {
    await expect(this.title).toBeVisible({ timeout: 15_000 });
  }

  async expectTitle(title: string) {
    await expect(this.title).toContainText(title);
  }

  async expectPrimaryAction(label: string | RegExp) {
    await expect(this.primaryAction).toHaveText(label);
  }

  async clickTab(name: string) {
    await this.page.getByRole("tab", { name }).click();
  }

  /** A menu item in the `⋯` menu, which frappe-ui portals to the body. */
  menuItem(name: string): Locator {
    return this.page.getByRole("menuitem", { name });
  }

  async openOverflow() {
    await this.overflowTrigger.click();
    await expect(this.page.getByRole("menu")).toBeVisible();
  }

  /** The confirmation frappe-ui's `ConfirmDialog` opens. */
  dialog(): Locator {
    return this.page.getByRole("dialog");
  }

  async confirm() {
    await this.dialog().getByRole("button", { name: "Confirm" }).click();
  }

  /**
   * The masked input for a secret.
   *
   * `FormControl` forwards unrecognised attributes to the `<input>` itself, so
   * the hook lands on the control, not on a wrapper around it.
   */
  secret(field: string): Locator {
    return this.testId(`secret-${field}`);
  }

  async copyField(field: string) {
    await this.testId(`copy-${field}`).click();
  }

  async openNewSiteDialog() {
    await this.clickTab("Sites");
    await this.testId("new-site").click();
    await expect(this.testId("site-name-input")).toBeVisible();
  }

  async fillNewSiteForm(siteName: string, apps: string[] = []) {
    await this.testId("site-name-input").fill(siteName);
    for (const app of apps) {
      await this.testId(`site-app-${app}`).check();
    }
  }

  async submitNewSite() {
    await this.testId("create-site").click();
  }
}
