import { type Locator, type Page, expect } from "@playwright/test";

/**
 * Selector convention: every screen exposes `data-test` hooks and the page
 * objects address them through `testId()`. Names are kebab-case and describe
 * the thing, not its markup — a region is its own name (`overview`,
 * `environments`), a nav item is `nav-<route>`, a row is
 * `<collection>-<record name>` and a control inside a row is
 * `<collection>-action-<record name>`. Never assert on tag names, classes or
 * heading text; a redesign must not break the suite.
 */
export class BasePage {
  constructor(protected page: Page) {}

  testId(name: string): Locator {
    return this.page.locator(`[data-test="${name}"]`);
  }

  async login(
    user = process.env.FRAPPE_ADMIN_USER || "Administrator",
    password = process.env.FRAPPE_ADMIN_PASSWORD || "admin"
  ) {
    await this.page.goto("/login");
    await this.page.locator("#login_email").fill(user);
    await this.page.locator("#login_password").fill(password);
    // Login page has a second .btn-login for the email-link flow; target the password submit.
    await this.page.locator("button.btn-login[type=submit]:not(.btn-login-with-email-link)").click();
    await this.page.waitForURL(/\/(app|desk)/, { timeout: 20_000 });
  }

  async gotoFrontend(path = "/") {
    await this.page.goto(`/frontend${path}`);
    await this.page.waitForLoadState("networkidle", { timeout: 20_000 });
  }

  async waitForPageLoad() {
    await this.page.waitForLoadState("networkidle", { timeout: 15_000 });
  }

  async waitForUserContext() {
    await this.page.waitForResponse(
      (resp) =>
        resp.url().includes("get_user_context") && resp.status() === 200,
      { timeout: 10_000 }
    ).catch(() => {});
    await this.page.waitForTimeout(300);
  }

  async clickNav(route: string) {
    await this.testId(`nav-${route}`).click();
    await this.waitForPageLoad();
  }

  async expectHeading(text: string) {
    await expect(this.page.locator("h1").first()).toContainText(text);
  }
}
