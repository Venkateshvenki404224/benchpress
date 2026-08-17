import { type Page } from "@playwright/test";

const API_BASE = "/api/resource";

/**
 * Frappe rejects a session-authenticated write without a CSRF header, and the
 * REST API answers with a 400 whose body is the only explanation. The SPA boot
 * page injects the token, so one visit is enough to read it.
 */
async function csrfHeaders(page: Page): Promise<Record<string, string>> {
  let token = await page
    .evaluate(() => (window as unknown as { csrf_token?: string }).csrf_token)
    .catch(() => undefined);
  if (!token) {
    await page.goto("/frontend/");
    token = await page.evaluate(
      () => (window as unknown as { csrf_token?: string }).csrf_token
    );
  }
  return {
    "Content-Type": "application/json",
    ...(token ? { "X-Frappe-CSRF-Token": token } : {}),
  };
}

/** Fail with the server's own message instead of an undefined document. */
async function unwrap(response: { ok(): boolean; status(): number; text(): Promise<string>; json(): Promise<any> }, what: string) {
  if (!response.ok()) {
    throw new Error(`${what} failed: ${response.status()} ${await response.text()}`);
  }
  return response.json();
}

export async function createTestLab(
  page: Page,
  overrides: Record<string, unknown> = {}
) {
  const suffix = Date.now().toString(36);
  const response = await page.request.post(`${API_BASE}/Lab`, {
    headers: await csrfHeaders(page),
    data: JSON.stringify({
      lab_id: overrides.lab_id || `test-lab-${suffix}`,
      title: overrides.title || `Test Lab ${suffix}`,
      frappe_version: overrides.frappe_version || "version-16",
      status: overrides.status || "Draft",
      memory_limit: overrides.memory_limit || "2G",
      cpu_cores: overrides.cpu_cores || 2,
      ...overrides,
    }),
  });
  const data = await unwrap(response, "Creating a test Lab");
  return data.data;
}

/**
 * A bench for a lab, in whatever state the test needs.
 *
 * `Bench Instance` autonames from `md5(session user + lab)`, so the name is a
 * function of the lab — one bench per lab per user, and the caller never picks
 * it. Every state field is `read_only`, which is a form concern only: the REST
 * insert persists them.
 */
export async function createTestBench(
  page: Page,
  lab: string,
  overrides: Record<string, unknown> = {}
) {
  const response = await page.request.post(`${API_BASE}/Bench Instance`, {
    headers: await csrfHeaders(page),
    data: JSON.stringify({
      lab,
      frappe_version: overrides.frappe_version || "version-16",
      status: overrides.status || "Running",
      container_id: overrides.container_id || "e2e-container",
      container_ip: overrides.container_ip || "172.30.0.99",
      // A deployed bench always has credentials; the connection panel only
      // masks a secret that exists, so an empty one would render as an
      // em-dash instead of a password field.
      ssh_password: overrides.ssh_password || "e2e-ssh-password",
      admin_password: overrides.admin_password || "e2e-admin-password",
      ...overrides,
    }),
  });
  const data = await unwrap(response, "Creating a test Bench Instance");
  return data.data;
}

/** A build log for a lab — how a failed run is staged without running one. */
export async function createTestBuildLog(
  page: Page,
  lab: string,
  message: string,
  logType = "error"
) {
  const response = await page.request.post(`${API_BASE}/Build Log`, {
    headers: await csrfHeaders(page),
    data: JSON.stringify({
      lab,
      log_type: logType,
      message,
      timestamp: new Date().toISOString().slice(0, 19).replace("T", " "),
    }),
  });
  const data = await unwrap(response, "Creating a test Build Log");
  return data.data;
}

/** A deploy log for a bench — how a pipeline run is staged without running one. */
export async function createTestDeployLog(
  page: Page,
  bench: string,
  message: string,
  logType = "info"
) {
  const response = await page.request.post(`${API_BASE}/Deploy Log`, {
    headers: await csrfHeaders(page),
    data: JSON.stringify({
      bench,
      log_type: logType,
      message,
      timestamp: new Date().toISOString().slice(0, 19).replace("T", " "),
    }),
  });
  const data = await unwrap(response, "Creating a test Deploy Log");
  return data.data;
}

/**
 * A step marker exactly as `benchpress/deploy_pipeline.py` writes it.
 *
 * The suite builds runs out of these rather than copying whole logs, so a
 * change to the line format fails here instead of silently rendering nothing.
 */
export function deployStepLine(
  index: number,
  label: string,
  key: string,
  elapsed: number
) {
  return `=== Step ${index}/11: ${label} [${key} @${elapsed.toFixed(1)}s] ===`;
}

export async function deleteTestDoc(
  page: Page,
  doctype: string,
  name: string
) {
  await page.request.delete(
    `${API_BASE}/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`,
    { headers: await csrfHeaders(page) }
  );
}

export async function createTestDevice(
  page: Page,
  overrides: Record<string, unknown> = {}
) {
  const suffix = Date.now().toString(36);
  const response = await page.request.post(
    "/api/method/benchpress.api.add_device",
    {
      headers: await csrfHeaders(page),
      data: JSON.stringify({
        device_name: overrides.device_name || `test-device-${suffix}`,
        device_type: overrides.device_type || "Laptop",
        public_key: overrides.public_key || null,
      }),
    }
  );
  const data = await unwrap(response, "Creating a test device");
  return data.message;
}

export async function removeTestDevice(page: Page, deviceName: string) {
  await page.request.post(
    "/api/method/benchpress.api.remove_device",
    {
      headers: await csrfHeaders(page),
      data: JSON.stringify({ device_name: deviceName }),
    }
  );
}

export async function getLabList(page: Page) {
  const response = await page.request.get(
    `${API_BASE}/Lab?fields=["name","lab_id","title","status","frappe_version"]&order_by=creation desc&limit_page_length=100`
  );
  const data = await response.json();
  return data.data || [];
}
