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
