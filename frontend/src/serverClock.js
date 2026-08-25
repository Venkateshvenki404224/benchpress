/**
 * Anchors `utils/clock` against the server, once at boot and again whenever a
 * countdown notices the browser clock moved under it.
 *
 * Kept out of `utils/clock.js` so that module stays pure and directly testable:
 * the arithmetic lives there, the request lives here.
 */
import { onResync, recordSkew } from "@/utils/clock";
import { call } from "frappe-ui";

export async function anchorClock() {
	const sentAt = Date.now();
	const { server_now_ms } = await call("benchpress.api.server_time");
	recordSkew(sentAt, server_now_ms);
}

/** Anchor now, and re-anchor on request. Failures are ignored: an unanchored clock still counts. */
export function startServerClock() {
	onResync(() => anchorClock().catch(() => {}));
	return anchorClock().catch(() => {});
}
