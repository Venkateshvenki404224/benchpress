/**
 * The one map from a product status value to a colour.
 *
 * Every status enum in BenchPress resolves here — Lab.status,
 * Bench Instance.status, Bench Instance.container_health (including the
 * persisted empty string), Bench Site.status, Database Server.status and
 * VPN Peer.status — plus the lowercase Deploy Log / Build Log outcomes the
 * activity feed renders. StatusBadge.vue is the only consumer; nothing else
 * may map a status to a colour. An unrecognised value degrades to neutral
 * grey rather than throwing.
 */

export const TONES = {
	green: {
		theme: "green",
		dot: "bg-surface-green-3",
		text: "text-ink-green-3",
		// frappe-ui's green subtle already matches the handoff.
		badgeClass: "",
	},
	blue: {
		theme: "blue",
		dot: "bg-surface-blue-2",
		text: "text-ink-blue-3",
		// frappe-ui 0.1.278's blue subtle is bg-surface-blue-2 (blue-500) behind
		// text-ink-blue-2 (blue-400) — a solid fill the handoff never uses and
		// which fails contrast. The other four themes need no correction.
		badgeClass: "!bg-surface-blue-1 !text-ink-blue-3",
	},
	orange: {
		theme: "orange",
		dot: "bg-surface-amber-2",
		text: "text-ink-amber-3",
		badgeClass: "",
	},
	red: {
		theme: "red",
		dot: "bg-surface-red-4",
		text: "text-ink-red-4",
		badgeClass: "",
	},
	gray: {
		theme: "gray",
		dot: "bg-surface-gray-4",
		text: "text-ink-gray-6",
		badgeClass: "",
	},
};

export const NEUTRAL_TONE = "gray";
export const UNKNOWN_LABEL = "Unknown";

// Keys are lowercase; lookups are case-insensitive so "Error" and the
// Deploy Log "error" log_type share one entry.
const STATUS_TONES = {
	// Success — Ready / Running / Active / Healthy
	ready: "green",
	running: "green",
	active: "green",
	healthy: "green",
	success: "green",
	// In progress — Building / Deploying / Creating
	building: "blue",
	deploying: "blue",
	creating: "blue",
	info: "blue",
	// Warning
	stale: "orange",
	warning: "orange",
	// Error / Failed / Unhealthy — Revoked is a terminal deny, not a pause
	error: "red",
	failed: "red",
	unhealthy: "red",
	revoked: "red",
	// Neutral — Stopped / Unknown / Idle / Draft / Pending
	stopped: "gray",
	unknown: "gray",
	idle: "gray",
	draft: "gray",
	pending: "gray",
	inactive: "gray",
	disabled: "gray",
};

/** The tone name for a status value; unknown and empty values are neutral. */
export function toneFor(status) {
	return STATUS_TONES[normalize(status).toLowerCase()] ?? NEUTRAL_TONE;
}

/** The colour set for a status value. */
export function themeFor(status) {
	return TONES[toneFor(status)];
}

/** What the badge reads; a never-polled container_health says "Unknown". */
export function labelFor(status) {
	return normalize(status) || UNKNOWN_LABEL;
}

function normalize(status) {
	return typeof status === "string" ? status.trim() : "";
}
