import { io } from "socket.io-client";

// The realtime endpoint is the page's own origin. Whatever serves this SPA also
// proxies `/socket.io` to the websocket service — nginx does in a deployment,
// vite's frappe proxy does in development — so the browser never needs to know
// which port the socket process listens on.
//
// Deriving a port from `window.location` instead aimed the client at `:9000`, a
// port no deployment publishes, and read the namespace from `window.site_name`,
// which the shell's boot payload did not set. Every connection therefore went to
// `http://<host>:9000/undefined` and no deploy log, build log or notification
// ever arrived. This mirrors frappe's own `socketio_client.get_host()`.
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
