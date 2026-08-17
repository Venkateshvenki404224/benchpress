/**
 * What the primary button on Lab detail says, and whether it can be pressed.
 *
 * The old header made `Stop` the loudest control on the page and hid the thing
 * a user actually wants. The primary action is now the next step in the lab's
 * own lifecycle — build, deploy, wait, or open — and Stop and Delete live in
 * the overflow menu. Nothing is ever hidden because it is unreachable: an
 * unreachable action stays visible, disabled, and says why.
 *
 * This is a pure function of four inputs so the whole matrix is testable
 * without a browser.
 */

export const DEPLOY = "deploy";
export const OPEN = "open";
export const REBUILD = "rebuild";
// Something the server is already doing; the button only reports it.
export const WAIT = "wait";

export const SITE_PORT = 8000;

/**
 * The primary button for a lab and the caller's deployment of it.
 *
 * @param {object} state
 * @param {string} state.labStatus `Lab.status`.
 * @param {string} state.benchStatus `Bench Instance.status`, "" when undeployed.
 * @param {boolean} state.vpnConnected Whether this device's tunnel is up.
 * @param {string|null} state.siteUrl Where the site answers, if it has an address.
 * @param {boolean} state.isAdmin Whether the caller may rebuild images.
 * @returns {{action: string, label: string, disabled: boolean, hint: string}}
 */
export function primaryAction(state = {}) {
	if (state.labStatus === "Error") return rebuildAction(state);
	if (state.labStatus === "Building") return waiting("Building image…");
	if (state.benchStatus === "Deploying") return waiting("Deploying…");
	if (state.benchStatus === "Running") return openAction(state);
	return { action: DEPLOY, label: "Deploy", disabled: false, hint: "" };
}

function rebuildAction({ isAdmin }) {
	return {
		action: REBUILD,
		label: "Rebuild image",
		disabled: !isAdmin,
		hint: isAdmin ? "" : "Only admins can rebuild a lab image.",
	};
}

function waiting(label) {
	return { action: WAIT, label, disabled: true, hint: "" };
}

function openAction({ vpnConnected, siteUrl }) {
	if (!vpnConnected) {
		return {
			action: OPEN,
			label: "Open site — VPN off",
			disabled: true,
			hint: "Register this device on the VPN to reach the site.",
		};
	}
	if (!siteUrl) {
		return {
			action: OPEN,
			label: "Open site",
			disabled: true,
			hint: "This bench has no address yet.",
		};
	}
	return { action: OPEN, label: "Open site", disabled: false, hint: "" };
}

export const VIEW_LOG = "view-log";
export const CONNECT_VPN = "connect-vpn";

/**
 * The deploy dialog's solid button, from the state of the run it is watching.
 *
 * It stays disabled and honest while the pipeline runs — the run ends when the
 * backend says it ended — and then offers the thing the user came for. With the
 * tunnel down the site is unreachable, so it routes to Devices instead of
 * opening an address that cannot answer.
 *
 * @param {object} state
 * @param {string} state.runState "running" / "success" / "failed" / "idle".
 * @param {boolean} state.vpnConnected Whether this device's tunnel is up.
 * @param {string|null} state.siteUrl Where the new site answers, if it has an address.
 * @returns {{action: string, label: string, disabled: boolean, loading: boolean}}
 */
export function deployDialogAction({ runState, vpnConnected, siteUrl } = {}) {
	if (runState === "failed") {
		return {
			action: VIEW_LOG,
			label: "View the failing log",
			disabled: false,
			loading: false,
		};
	}
	if (runState !== "success") {
		return { action: WAIT, label: "Deploying…", disabled: true, loading: true };
	}
	if (!vpnConnected) {
		return {
			action: CONNECT_VPN,
			label: "Connect VPN to open",
			disabled: false,
			loading: false,
		};
	}
	return { action: OPEN, label: "Open site", disabled: !siteUrl, loading: false };
}

/**
 * Where a bench's site actually answers.
 *
 * The domain is a label, not a route — nothing resolves it. The site is served
 * by the container itself, reachable over the tunnel on its WireGuard address.
 */
export function siteUrl(bench) {
	const host = bench?.wg_ip || bench?.container_ip;
	return host ? `http://${host}:${SITE_PORT}` : null;
}

/** What that address is called on screen. */
export function siteLabel(bench, site) {
	return (
		site?.full_domain ||
		site?.site_name ||
		bench?.domain ||
		bench?.site_name ||
		hostLabel(bench)
	);
}

function hostLabel(bench) {
	const host = bench?.wg_ip || bench?.container_ip;
	return host ? `${host}:${SITE_PORT}` : "";
}
