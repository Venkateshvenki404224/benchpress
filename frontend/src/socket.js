import { io } from "socket.io-client";

// Whatever serves this SPA also proxies `/socket.io` to the websocket service, so the
// endpoint is the page's own origin and the namespace is the site name. Mirrors
// frappe's `socketio_client.get_host()`.
let socket = null;

// Reconnection never gives up. Five attempts was roughly thirty seconds of trouble before
// the client stopped trying *for the life of the page*, and a laptop asleep through its
// lease would wake to a frozen countdown and never receive its expiry event. The backoff is
// capped so a long outage costs one attempt every half minute, and jittered so every open
// tab does not reconnect on the same beat.
const RECONNECT_DELAY_MS = 1000;
const RECONNECT_DELAY_MAX_MS = 30000;
const RECONNECT_JITTER = 0.5;

export function initSocket() {
	socket = io(`${window.location.origin}/${window.site_name}`, {
		withCredentials: true,
		reconnection: true,
		reconnectionAttempts: Number.POSITIVE_INFINITY,
		reconnectionDelay: RECONNECT_DELAY_MS,
		reconnectionDelayMax: RECONNECT_DELAY_MAX_MS,
		randomizationFactor: RECONNECT_JITTER,
	});
	return socket;
}

export function useSocket() {
	return socket;
}
