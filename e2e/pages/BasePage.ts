import { type Page, expect } from "@playwright/test";

export class BasePage {
  constructor(protected page: Page) {}

  async login(
    user = process.env.FRAPPE_ADMIN_USER || "Administrator",
    password = process.env.FRAPPE_ADMIN_PASSWORD || "admin"
  ) {
    await this.page.goto("/login");
    await this.page.locator("#login_email").fill(user);
    await this.page.locator("#login_password").fill(password);
    await this.page.locator(".btn-login").click();
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

  async expectHeading(text: string) {
    await expect(this.page.locator("h1").first()).toContainText(text);
  }
}
