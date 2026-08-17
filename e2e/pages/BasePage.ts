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

  /**
   * Authenticate through `/api/method/login` rather than the desk login form.
   *
   * The form submit does not reliably land on `/app` here — where it redirects
   * depends on the user's home page — and the suite only needs the session
   * cookie. Posting the credentials sets exactly that, and fails loudly with
   * the server's own status when they are wrong.
   */
  async login(
    user = process.env.FRAPPE_ADMIN_USER || "Administrator",
    password = process.env.FRAPPE_ADMIN_PASSWORD || "admin"
  ) {
    await this.page.goto("/login");
    const response = await this.page.request.post("/api/method/login", {
      headers: { "Content-Type": "application/json" },
      data: JSON.stringify({ usr: user, pwd: password }),
    });
    if (!response.ok()) {
      throw new Error(`Login failed for ${user}: ${response.status()} ${await response.text()}`);
    }
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
