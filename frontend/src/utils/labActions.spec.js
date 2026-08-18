import { describe, expect, it } from "vitest";
import {
	CONNECT_VPN,
	DEPLOY,
	OPEN,
	REBUILD,
	VIEW_LOG,
	WAIT,
	deployDialogAction,
	ideUrl,
	primaryAction,
	siteLabel,
	siteOpenAction,
	siteUrl,
} from "./labActions";

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

	it("answers for the row it is handed, not for the bench", () => {
		const bench = { wg_ip: "172.27.0.2", site_name: "lab-abc" };
		expect(siteUrl(bench, { site_name: "lab-abc" })).toBe(SITE);
		// The container serves its own site and nothing else, so any other row is
		// unreachable — opening the bench's site from it would be the old lie.
		expect(siteUrl(bench, { site_name: "somebody-elses" })).toBeNull();
	});
});

describe("siteOpenAction", () => {
	const active = { status: "Active", url: SITE };

	it("opens only when the site is running and the tunnel is up", () => {
		expect(siteOpenAction({ ...active, vpnConnected: true })).toMatchObject({
			label: "Open",
			disabled: false,
			hint: "",
		});
	});

	it("blames the tunnel when the site is running and the tunnel is not", () => {
		const state = siteOpenAction({ ...active, vpnConnected: false });
		expect(state).toMatchObject({ label: "Unreachable", disabled: true });
		expect(state.hint).toContain("VPN");
	});

	// The two reasons send the user somewhere different — the VPN page, or Deploy —
	// so a stopped site says so even with the tunnel up, and never says "Unreachable".
	it("blames the container when the site is not running, tunnel or no tunnel", () => {
		for (const status of ["Inactive", "Creating", "Error"]) {
			for (const vpnConnected of [true, false]) {
				const state = siteOpenAction({ status, url: SITE, vpnConnected });
				expect(state).toMatchObject({ label: "Not running", disabled: true });
				expect(state.hint).toContain("stopped");
			}
		}
	});

	it("stays disabled for a running site nothing serves", () => {
		const state = siteOpenAction({ status: "Active", url: null, vpnConnected: true });
		expect(state).toMatchObject({ label: "Unreachable", disabled: true });
		expect(state.hint).toContain("Nothing serves");
	});
});

describe("ideUrl", () => {
	it("is the same host on code-server's port", () => {
		expect(ideUrl({ wg_ip: "172.27.0.2" })).toBe("http://172.27.0.2:8080/");
		expect(ideUrl({})).toBeNull();
	});
});

describe("siteLabel", () => {
	it("prefers the site's own domain and falls back to the address", () => {
		expect(siteLabel({ wg_ip: "172.27.0.2" }, { full_domain: "crm.lab" })).toBe("crm.lab");
		expect(siteLabel({ domain: "bench.lab" }, null)).toBe("bench.lab");
		expect(siteLabel({ wg_ip: "172.27.0.2" }, null)).toBe("172.27.0.2:8000");
	});
});

describe("deployDialogAction", () => {
	it("stays disabled while the run is still going", () => {
		for (const runState of ["idle", "running"]) {
			expect(
				deployDialogAction({ runState, vpnConnected: true, siteUrl: SITE })
			).toMatchObject({
				action: WAIT,
				label: "Deploying…",
				disabled: true,
				loading: true,
			});
		}
	});

	it("offers the site once the backend says the run finished", () => {
		expect(
			deployDialogAction({ runState: "success", vpnConnected: true, siteUrl: SITE })
		).toMatchObject({ action: OPEN, label: "Open site", disabled: false });
	});

	it("routes to Devices instead of a site the tunnel cannot reach", () => {
		expect(
			deployDialogAction({ runState: "success", vpnConnected: false, siteUrl: SITE })
		).toMatchObject({ action: CONNECT_VPN, label: "Connect VPN to open", disabled: false });
	});

	it("cannot open a deployed bench that has no address yet", () => {
		expect(
			deployDialogAction({ runState: "success", vpnConnected: true, siteUrl: null })
		).toMatchObject({ action: OPEN, disabled: true });
	});

	it("sends a failed run to its log", () => {
		expect(deployDialogAction({ runState: "failed", vpnConnected: true })).toMatchObject({
			action: VIEW_LOG,
			label: "View the failing log",
			disabled: false,
		});
	});
});
