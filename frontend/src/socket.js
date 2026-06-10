import { io } from "socket.io-client";

let socket = null;
export function initSocket() {
	const socketio_port = window.socketio_port || 9000;
	const host = window.location.hostname;
	const siteName = import.meta.env.DEV ? host : window.site_name;
	const port = window.location.port ? `:${socketio_port}` : "";
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
