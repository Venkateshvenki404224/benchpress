import { type Locator, type Page } from "@playwright/test";
import { BasePage } from "./BasePage";

/**
 * Settings — a page since phase 6, not a dialog that opened over `/labs`.
 *
 * `/settings` is admin-gated by the router, so every test here runs as an
 * admin; a non-admin never reaches the screen at all.
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
  }

  async goto() {
    await this.gotoFrontend("/settings");
    await this.root.waitFor({ timeout: 15_000 });
    await this.baseDomain.waitFor({ timeout: 15_000 });
  }

  group(name: string): Locator {
    return this.testId(`group-${name}`);
  }
}
