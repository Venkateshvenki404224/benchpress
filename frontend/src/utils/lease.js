/**
 * What a lease deadline looks like on screen.
 *
 * Pure: it takes both ends of the subtraction, so it stays free of the date
 * layer and remains directly testable — the same reason `benchUsage.js` takes
 * ages already resolved. The clock that supplies `nowMs` is `clock.js`, which
 * corrects for the browser being wrong.
 *
 * Nothing here decides anything. The server owns expiry; this only renders it.
 */

export const SECOND = 1000;
export const MINUTE = 60 * SECOND;
export const HOUR = 60 * MINUTE;
export const DAY = 24 * HOUR;

export const NONE = "none";
export const ACTIVE = "active";
export const EXPIRING = "expiring";

// Below this the countdown turns amber. Long enough to save work and renew.
export const WARN_SECONDS = 5 * 60;

const EMPTY = { state: NONE, label: "", tone: "gray", tickPeriod: 0 };

/**
 * The countdown for one bench.
 *
 * @param {number|null} expiresAtMs Deadline in epoch milliseconds, or null for
 *   a bench that holds no lease — every row predating the feature.
 * @param {number} nowMs The corrected current time, from `clock.serverNow()`.
 * @returns {{state: string, label: string, tone: string, tickPeriod: number}}
 *   `tickPeriod` is how often the widget should repaint, `0` for never.
 */
export function leaseFor(expiresAtMs, nowMs) {
	if (!expiresAtMs) return { ...EMPTY };
	// Rounded up, so a lease with a millisecond left reads 00:01 rather than 00:00.
	const seconds = Math.ceil((expiresAtMs - nowMs) / SECOND);
	if (seconds <= 0) {
		return { state: EXPIRING, label: "00:00", tone: "red", tickPeriod: SECOND };
	}
	return {
		state: ACTIVE,
		label: labelFor(seconds),
		tone: seconds <= WARN_SECONDS ? "orange" : "green",
		// A repaint a second is only worth it while the seconds are on screen.
		tickPeriod: seconds > HOUR / SECOND ? MINUTE : SECOND,
	};
}

function labelFor(seconds) {
	if (seconds >= DAY / SECOND) {
		return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
	}
	if (seconds >= HOUR / SECOND) {
		return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
	}
	return `${pad(Math.floor(seconds / 60))}:${pad(seconds % 60)}`;
}

function pad(value) {
	return String(value).padStart(2, "0");
}
