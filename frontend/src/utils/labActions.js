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
// Resume the stopped container as it is — nothing is rebuilt, nothing is lost.
export const START = "start";
// Something the server is already doing; the button only reports it.
export const WAIT = "wait";

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
	// A stopped bench resumes. Deploy would replace the container — and the
	// container's writable layer is everything the user has done inside it —
	// so the destructive path is never the default. Redeploy lives in the
	// overflow menu, behind a confirmation that names what it destroys.
	if (state.benchStatus === "Stopped") {
		return { action: START, label: "Start", disabled: false, hint: "" };
	}
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
	if (!siteUrl) {
		return {
			action: OPEN,
			label: "Open site",
			disabled: true,
			hint: "This bench has no address yet.",
		};
	}
	// A public address answers from anywhere; only the tunnel-only fallback gates on VPN.
	if (urlNeedsVpn(siteUrl) && !vpnConnected) {
		return {
			action: OPEN,
			label: "Open site — VPN off",
			disabled: true,
			hint: "Register this device on the VPN to reach the site or the IDE.",
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
	if (urlNeedsVpn(siteUrl) && !vpnConnected) {
		return {
			action: CONNECT_VPN,
			label: "Connect VPN to open",
			disabled: false,
			loading: false,
		};
	}
	return { action: OPEN, label: "Open site", disabled: !siteUrl, loading: false };
}

/** The tunnel-only address — answers only for devices on the WireGuard network. */
export function privateSiteUrl(bench) {
	return bench?.addresses?.tunnel_site ?? null;
}

/**
 * Whether an address answers only over the tunnel.
 *
 * Both address kinds are built by this codebase, never typed by hand: public
 * ones are `https://` hostnames behind the reverse proxy, private ones are
 * plain-http tunnel IPs, and `benchpress/addressing.py` builds both. The scheme
 * is therefore a reliable discriminator, not a heuristic.
 */
export function urlNeedsVpn(url) {
	return !!url && url.startsWith("http://");
}

/**
 * Where a site actually answers, or null when nothing serves it.
 *
 * The public hostname wins when the bench has one — it works without the
 * tunnel — and the WireGuard address is the fallback for VPN-only deployments.
 *
 * With no site it is the bench's own site. With one, it is that row's address —
 * and a row naming anything else has none: the container pins `default_site` to
 * the bench's site and nginx serves only that, so claiming otherwise would open
 * one site from another site's button.
 *
 * The domain is a label, not a route — nothing resolves it.
 */
export function siteUrl(bench, site = null) {
	if (site && site.site_name !== bench?.site_name) return null;
	return bench?.addresses?.public_site || privateSiteUrl(bench);
}

/**
 * The Open button on one site row: what it says, and why it cannot be pressed.
 *
 * A stopped container and a down tunnel are different problems with different
 * remedies, so they never collapse into one word — telling a user on the VPN to
 * register a device is how this UI lost their trust once already. The button is
 * never hidden, only disabled with its reason, as everywhere else on this page.
 *
 * @param {object} state
 * @param {string} state.status `Bench Site.status`.
 * @param {string|null} state.url Where this row's site answers, if anything serves it.
 * @param {boolean} state.vpnConnected Whether this device's tunnel is up.
 * @returns {{label: string, disabled: boolean, hint: string}}
 */
export function siteOpenAction({ status, url, vpnConnected } = {}) {
	if (status !== "Active") {
		return {
			label: "Not running",
			disabled: true,
			hint: "This site's container is stopped. Deploy the lab to bring it back.",
		};
	}
	if (!url) {
		return {
			label: "Unreachable",
			disabled: true,
			hint: "Nothing serves this site — the container answers only on its own site.",
		};
	}
	if (urlNeedsVpn(url) && !vpnConnected) {
		return {
			label: "Unreachable",
			disabled: true,
			hint: "Register this device on the VPN to reach this site.",
		};
	}
	return { label: "Open", disabled: false, hint: "" };
}

/**
 * Where the IDE answers. The deploy stores the public IDE hostname on the bench
 * when the deployment has one; the tunnel address is the VPN-only fallback.
 */
export function ideUrl(bench) {
	const addresses = bench?.addresses;
	return addresses?.public_ide || addresses?.tunnel_ide || null;
}

/** What that address is called on screen. */
export function siteLabel(bench, site) {
	return site?.site_name || bench?.domain || bench?.site_name || hostLabel(bench);
}

function hostLabel(bench) {
	return bench?.addresses?.host_label ?? "";
}

export const PROMPT_LOADING = "loading";
export const PROMPT_READY = "ready";
export const PROMPT_ERROR = "error";

/**
 * What the IDE dialog says while the password it was opened for is fetched.
 *
 * The IDE tab is opened by the click itself; this dialog exists so the password
 * arrives with it instead of being hunted for behind the "Reveal secrets"
 * toggle. It is never put in the URL — a query parameter would land in browser
 * history, in the container's access log and in every proxy in between.
 *
 * @param {object} state
 * @param {boolean} state.loading Whether `get_code_server_credentials` is in flight.
 * @param {string|object} state.error What it failed with, if it failed.
 * @param {string} state.password What it returned.
 * @returns {{status: string, message: string, password: string, error: string}}
 */
export function codeServerPrompt({ loading, error, password } = {}) {
	if (loading) return prompt(PROMPT_LOADING, "Fetching this lab's IDE password…");
	if (error) {
		return prompt(
			PROMPT_ERROR,
			"The IDE opened, but its password could not be read. Connection details holds it.",
			{ error: errorText(error) }
		);
	}
	if (!password) {
		return prompt(
			PROMPT_ERROR,
			"This lab has no IDE password recorded. Redeploy it to set one."
		);
	}
	return prompt(
		PROMPT_READY,
		"code-server asks for this password. Every redeploy replaces it.",
		{
			password,
		}
	);
}

function prompt(status, message, rest = {}) {
	return { status, message, password: "", error: "", ...rest };
}

function errorText(error) {
	return typeof error === "string" ? error : error?.message || "";
}
