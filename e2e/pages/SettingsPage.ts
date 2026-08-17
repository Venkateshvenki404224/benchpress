import { type Locator, type Page } from "@playwright/test";
import { BasePage } from "./BasePage";

/**
 * Settings — a dialog shaped like frappe-ui's SettingsDialog: grouped nav on
 * the left, one panel per group on the right. It is opened from the sidebar
 * account menu, and `/settings` still resolves by opening it over Overview.
 *
 * The dialog is admin-gated by the router and by the account menu, so every
 * test here runs as an admin; a non-admin never reaches the screen at all.
 */
export class SettingsPage extends BasePage {
  readonly root: Locator;
  readonly baseDomain: Locator;
  readonly defaultImage: Locator;
  readonly dockerSocket: Locator;
  readonly traefikNetwork: Locator;
  readonly memoryLimit: Locator;
  readonly cpuQuota: Locator;
  readonly codeServerVersion: Locator;
  readonly lastSaved: Locator;
  readonly save: Locator;
  readonly discard: Locator;
  readonly close: Locator;

  constructor(page: Page) {
    super(page);
    this.root = this.testId("settings");
    this.baseDomain = this.testId("base_domain");
    this.defaultImage = this.testId("default_image");
    this.dockerSocket = this.testId("docker_socket");
    this.traefikNetwork = this.testId("traefik_network");
    this.memoryLimit = this.testId("container_memory_limit");
    this.cpuQuota = this.testId("container_cpu_quota");
    this.codeServerVersion = this.testId("code_server_version");
    this.lastSaved = this.testId("last-saved");
    this.save = this.testId("save-settings");
    this.discard = this.testId("discard-settings");
    this.close = this.testId("close-settings");
  }

  async goto() {
    await this.gotoFrontend("/settings");
    await this.root.waitFor({ timeout: 15_000 });
    await this.baseDomain.waitFor({ timeout: 15_000 });
  }

  /** Only the selected group's panel is mounted, so fields need their tab. */
  async openTab(name: string) {
    await this.tab(name).click();
    await this.group(name).waitFor({ timeout: 10_000 });
  }

  tab(name: string): Locator {
    return this.testId(`tab-${name}`);
  }

  group(name: string): Locator {
    return this.testId(`group-${name}`);
  }
}
