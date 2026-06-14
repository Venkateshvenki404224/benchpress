import { io } from "socket.io-client";

// Resolve the socket.io port at runtime. Frappe exposes `window.socketio_port`
// in the boot data block on desk/website pages (frappe core's website.js reads
// the same global); when it is absent we fall back to Frappe's default port.
// This replaces a build-time `import` of sites/common_site_config.json, which
// only exists inside a running bench and broke `yarn build` in CI/contributor
// checkouts.
function getSocketioPort() {
	return window.socketio_port || 9000;
}

let socket = null;
export function initSocket() {
	const host = window.location.hostname;
	const siteName = window.site_name;
	const port = window.location.port ? `:${getSocketioPort()}` : "";
	const protocol = port ? "http" : "https";
	const url = `${protocol}://${host}${port}/${siteName}`;

	socket = io(url, {
		withCredentials: true,
		reconnectionAttempts: 5,
	});
	return socket;
}

export function useSocket() {
	return socket;
}
