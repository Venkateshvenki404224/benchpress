/**
 * The Devices screen's pure logic: how a transfer counter reads, and what the
 * status banner says.
 *
 * Freshness is never decided here. `connected` is the server's answer from
 * `get_vpn_status`, which compares the newest handshake against the VPN app's
 * own poll interval; a second threshold in the client would disagree with the
 * poller within two minutes.
 */

import { shortAge } from "@/utils/benchUsage";

const BYTE_UNITS = ["B", "KB", "MB", "GB", "TB"];

/** A byte count in the one unit worth reading — "0 B", "996 KB", "1.4 GB". */
export function formatBytes(bytes) {
	const number = Number(bytes);
	if (!Number.isFinite(number) || number <= 0) return "0 B";
	let value = number;
	let unit = 0;
	while (value >= 1024 && unit < BYTE_UNITS.length - 1) {
		value /= 1024;
		unit += 1;
	}
	return `${unit === 0 ? Math.round(value) : value.toFixed(1)} ${BYTE_UNITS[unit]}`;
}

/** Both directions of a peer's transfer on one line. */
export function transferLabel(receivedBytes, sentBytes) {
	return `${formatBytes(receivedBytes)} ↓ / ${formatBytes(sentBytes)} ↑`;
}

export const ADD_DEVICE = "add-device";
export const RECHECK = "recheck";

/**
 * The banner above the device list: state, sentence, and the button beside it.
 *
 * The design's button "toggles" the tunnel. A browser cannot start or stop
 * WireGuard on the machine it runs on, so the honest action is the one the app
 * can actually perform: register this machine when there is nothing to connect
 * with, otherwise ask the server again.
 *
 * @param {object} state
 * @param {boolean} state.connected The server's verdict on this user's tunnel.
 * @param {number|null} state.handshakeAgeSeconds Age of the newest handshake.
 * @param {number} state.deviceCount How many devices this account has.
 * @returns {{tone: string, title: string, body: string, action: string, actionLabel: string}}
 */
export function bannerState({ connected, handshakeAgeSeconds, deviceCount } = {}) {
	if (connected) {
		return {
			tone: "green",
			title: "WireGuard is up on this device",
			body: `${handshakeLine(handshakeAgeSeconds)} Sites, SSH and VS Code all resolve.`,
			action: RECHECK,
			actionLabel: "Check again",
		};
	}
	if (!deviceCount) {
		return {
			tone: "amber",
			title: "This device is not on the VPN",
			body: "Register the machine, import the config, then everything below becomes reachable.",
			action: ADD_DEVICE,
			actionLabel: "Add this device",
		};
	}
	return {
		tone: "amber",
		title: "This device is not on the VPN",
		body: `${machines(
			deviceCount
		)} registered, none with a recent handshake. Turn the tunnel on in your WireGuard client, then check again.`,
		action: RECHECK,
		actionLabel: "Check again",
	};
}

function handshakeLine(handshakeAgeSeconds) {
	if (!Number.isFinite(handshakeAgeSeconds)) return "The server sees this device.";
	return `Handshake ${shortAge(handshakeAgeSeconds)} ago.`;
}

function machines(count) {
	return count === 1 ? "1 machine" : `${count} machines`;
}

/** The device's second line: what kind of machine it is and when it joined. */
export function deviceSubtitle(deviceType, registeredLabel) {
	return registeredLabel ? `${deviceType} · registered ${registeredLabel}` : deviceType;
}
