import { describe, expect, it } from "vitest";
import {
	CONNECT_VPN,
	DEPLOY,
	OPEN,
	PROMPT_ERROR,
	PROMPT_LOADING,
	PROMPT_READY,
	REBUILD,
	START,
	VIEW_LOG,
	WAIT,
	codeServerPrompt,
	deployDialogAction,
	ideUrl,
	primaryAction,
	siteLabel,
	siteOpenAction,
	siteUrl,
	urlNeedsVpn,
} from "./labActions";

// The address set as `benchpress/addressing.py` builds it. Every fixture below
// states one literally rather than deriving it from a port, which is the
// duplication this payload exists to remove.
const SITE = "http://172.27.0.2:8000";
const PUBLIC = "https://abc123.benchpress.cloud";
const IDE = "http://172.27.0.2:8080/";
const PUBLIC_IDE = "https://ide-abc123.benchpress.cloud";
const HOST_LABEL = "172.27.0.2:8000";

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
		name: "a bench with a public address opens with or without the tunnel",
		state: { labStatus: "Ready", benchStatus: "Running", siteUrl: PUBLIC },
		up: { action: OPEN, label: "Open site", disabled: false },
		down: { action: OPEN, label: "Open site", disabled: false },
	},
	{
		name: "a failed image offers a rebuild in both tunnel states",
		state: { labStatus: "Error", benchStatus: "Error", isAdmin: true },
		up: { action: REBUILD, label: "Rebuild image", disabled: false },
		down: { action: REBUILD, label: "Rebuild image", disabled: false },
	},
	{
		// The container's writable layer is everything the user has done inside
		// it, and a deploy replaces the container. Resume is the default; the
		// destructive path lives behind a confirmation in the overflow menu.
		name: "a stopped bench starts again — deploy is never the default over user data",
		state: { labStatus: "Ready", benchStatus: "Stopped" },
		up: { action: START, label: "Start", disabled: false },
		down: { action: START, label: "Start", disabled: false },
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
	it("routes over the tunnel address when the bench has no public hostname", () => {
		expect(siteUrl({ addresses: { tunnel_site: SITE } })).toBe(SITE);
	});

	it("prefers the public hostname over the tunnel address", () => {
		expect(siteUrl({ addresses: { public_site: PUBLIC, tunnel_site: SITE } })).toBe(PUBLIC);
	});

	it("has no address for a bench that never got one", () => {
		expect(siteUrl({})).toBeNull();
		expect(siteUrl(null)).toBeNull();
	});

	it("answers for the row it is handed, not for the bench", () => {
		const bench = { addresses: { tunnel_site: SITE }, site_name: "lab-abc" };
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

	it("opens a public address with the tunnel down", () => {
		expect(
			siteOpenAction({ status: "Active", url: PUBLIC, vpnConnected: false })
		).toMatchObject({
			label: "Open",
			disabled: false,
		});
	});

	it("stays disabled for a running site nothing serves", () => {
		const state = siteOpenAction({ status: "Active", url: null, vpnConnected: true });
		expect(state).toMatchObject({ label: "Unreachable", disabled: true });
		expect(state.hint).toContain("Nothing serves");
	});
});

describe("ideUrl", () => {
	it("is the tunnel address when the deployment has no public hostname", () => {
		expect(ideUrl({ addresses: { tunnel_ide: IDE } })).toBe(IDE);
		expect(ideUrl({})).toBeNull();
	});

	it("prefers the address the deploy stored — public when the deployment has one", () => {
		expect(ideUrl({ addresses: { public_ide: PUBLIC_IDE, tunnel_ide: IDE } })).toBe(
			PUBLIC_IDE
		);
	});
});

describe("urlNeedsVpn", () => {
	it("gates tunnel IPs and passes public hostnames", () => {
		expect(urlNeedsVpn(SITE)).toBe(true);
		expect(urlNeedsVpn(PUBLIC)).toBe(false);
		expect(urlNeedsVpn(null)).toBe(false);
	});
});

describe("siteLabel", () => {
	it("prefers the site's own domain and falls back to the address", () => {
		expect(
			siteLabel({ addresses: { host_label: HOST_LABEL } }, { full_domain: "crm.lab" })
		).toBe("crm.lab");
		expect(siteLabel({ domain: "bench.lab" }, null)).toBe("bench.lab");
		expect(siteLabel({ addresses: { host_label: HOST_LABEL } }, null)).toBe(HOST_LABEL);
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

	it("offers a public address even with the tunnel down", () => {
		expect(
			deployDialogAction({ runState: "success", vpnConnected: false, siteUrl: PUBLIC })
		).toMatchObject({ action: OPEN, label: "Open site", disabled: false });
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

describe("codeServerPrompt", () => {
	it("says the password is on its way while the fetch is in flight", () => {
		expect(codeServerPrompt({ loading: true })).toMatchObject({
			status: PROMPT_LOADING,
			password: "",
		});
	});

	it("hands over the password the fetch returned", () => {
		expect(codeServerPrompt({ password: "s3cret" })).toMatchObject({
			status: PROMPT_READY,
			password: "s3cret",
		});
	});

	it("points at Connection details when the fetch failed", () => {
		const prompt = codeServerPrompt({ error: new Error("Bench must be running") });
		expect(prompt.status).toBe(PROMPT_ERROR);
		expect(prompt.error).toBe("Bench must be running");
		expect(prompt.password).toBe("");
	});

	it("treats a missing password as a failure, not as an empty one", () => {
		expect(codeServerPrompt({ password: "" })).toMatchObject({
			status: PROMPT_ERROR,
			password: "",
		});
	});

	it("reads a string error as its own message", () => {
		expect(codeServerPrompt({ error: "denied" }).error).toBe("denied");
	});
});
