import { test as setup } from "@playwright/test";
import { BasePage } from "./pages/BasePage";

setup("authenticate as admin", async ({ page }) => {
  const basePage = new BasePage(page);
  await basePage.login();
  await page.context().storageState({ path: ".auth/admin.json" });
});
