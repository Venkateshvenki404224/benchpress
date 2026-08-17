import { io } from "socket.io-client";

// Whatever serves this SPA also proxies `/socket.io` to the websocket service, so the
// endpoint is the page's own origin and the namespace is the site name. Mirrors
// frappe's `socketio_client.get_host()`.
let socket = null;

export function initSocket() {
	socket = io(`${window.location.origin}/${window.site_name}`, {
		withCredentials: true,
		reconnectionAttempts: 5,
	});
	return socket;
}

export function useSocket() {
	return socket;
}
