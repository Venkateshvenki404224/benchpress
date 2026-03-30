import { type Page } from "@playwright/test";

const API_BASE = "/api/resource";

export async function createTestLab(
  page: Page,
  overrides: Record<string, unknown> = {}
) {
  const suffix = Date.now().toString(36);
  const response = await page.request.post(`${API_BASE}/Lab`, {
    headers: { "Content-Type": "application/json" },
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
  const data = await response.json();
  return data.data;
}

export async function deleteTestDoc(
  page: Page,
  doctype: string,
  name: string
) {
  await page.request.delete(
    `${API_BASE}/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`
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
      headers: { "Content-Type": "application/json" },
      data: JSON.stringify({
        device_name: overrides.device_name || `test-device-${suffix}`,
        device_type: overrides.device_type || "Laptop",
        public_key: overrides.public_key || null,
      }),
    }
  );
  const data = await response.json();
  return data.message;
}

export async function removeTestDevice(page: Page, deviceName: string) {
  await page.request.post(
    "/api/method/benchpress.api.remove_device",
    {
      headers: { "Content-Type": "application/json" },
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
