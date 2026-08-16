import { describe, expect, it } from "vitest";
import { DEPLOY, OPEN, REBUILD, WAIT, primaryAction, siteLabel, siteUrl } from "./labActions";

const SITE = "http://172.27.0.2:8000";

// The whole contextual matrix the header has to get right. It is pure logic,
// so it is asserted here rather than clicked through four times in a browser.
const MATRIX = [
	{
		name: "an undeployed lab offers Deploy whether or not the tunnel is up",
		state: { labStatus: "Ready", benchStatus: "" },
		up: { action: DEPLOY, label: "Deploy", disabled: false },
		down: { action: DEPLOY, label: "Deploy", disabled: false },
	},
	{
		name: "a Draft lab still offers Deploy — the pipeline builds the image",
		state: { labStatus: "Draft", benchStatus: "" },
		up: { action: DEPLOY, label: "Deploy", disabled: false },
		down: { action: DEPLOY, label: "Deploy", disabled: false },
	},
	{
		name: "a deploy in flight reports itself and cannot be pressed",
		state: { labStatus: "Ready", benchStatus: "Deploying" },
		up: { action: WAIT, label: "Deploying…", disabled: true },
		down: { action: WAIT, label: "Deploying…", disabled: true },
	},
	{
		name: "a running bench opens its site, and says so when the tunnel is down",
		state: { labStatus: "Ready", benchStatus: "Running", siteUrl: SITE },
		up: { action: OPEN, label: "Open site", disabled: false },
		down: { action: OPEN, label: "Open site — VPN off", disabled: true },
	},
	{
		name: "a failed image offers a rebuild in both tunnel states",
		state: { labStatus: "Error", benchStatus: "Error", isAdmin: true },
		up: { action: REBUILD, label: "Rebuild image", disabled: false },
		down: { action: REBUILD, label: "Rebuild image", disabled: false },
	},
];

describe("primaryAction", () => {
	for (const row of MATRIX) {
		it(row.name, () => {
			expect(primaryAction({ ...row.state, vpnConnected: true })).toMatchObject(row.up);
			expect(primaryAction({ ...row.state, vpnConnected: false })).toMatchObject(row.down);
		});
	}

	it("never hides an unreachable action — it disables it and says why", () => {
		const offline = primaryAction({
			labStatus: "Ready",
			benchStatus: "Running",
			siteUrl: SITE,
			vpnConnected: false,
		});

		expect(offline.label).toContain("VPN off");
		expect(offline.disabled).toBe(true);
		expect(offline.hint).not.toBe("");
	});

	it("disables the rebuild for a user who may not build images", () => {
		const state = { labStatus: "Error", vpnConnected: true };

		expect(primaryAction({ ...state, isAdmin: true }).disabled).toBe(false);
		expect(primaryAction({ ...state, isAdmin: false }).disabled).toBe(true);
	});

	it("cannot open a running bench that has no address yet", () => {
		const action = primaryAction({
			labStatus: "Ready",
			benchStatus: "Running",
			vpnConnected: true,
			siteUrl: null,
		});

		expect(action).toMatchObject({ action: OPEN, disabled: true });
	});

	it("reports the image build before anything the bench is doing", () => {
		expect(
			primaryAction({ labStatus: "Building", benchStatus: "Running", vpnConnected: true })
		).toMatchObject({ action: WAIT, label: "Building image…", disabled: true });
	});
});

describe("siteUrl", () => {
	it("routes over the tunnel address, falling back to the container IP", () => {
		expect(siteUrl({ wg_ip: "172.27.0.2", container_ip: "172.30.0.5" })).toBe(SITE);
		expect(siteUrl({ container_ip: "172.30.0.5" })).toBe("http://172.30.0.5:8000");
	});

	it("has no address for a bench that never got one", () => {
		expect(siteUrl({})).toBeNull();
		expect(siteUrl(null)).toBeNull();
	});
});

describe("siteLabel", () => {
	it("prefers the site's own domain and falls back to the address", () => {
		expect(siteLabel({ wg_ip: "172.27.0.2" }, { full_domain: "crm.lab" })).toBe("crm.lab");
		expect(siteLabel({ domain: "bench.lab" }, null)).toBe("bench.lab");
		expect(siteLabel({ wg_ip: "172.27.0.2" }, null)).toBe("172.27.0.2:8000");
	});
});
