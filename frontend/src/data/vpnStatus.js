import { createResource } from "frappe-ui";
import { reactive } from "vue";

/**
 * The session user's tunnel state, shared by the header chip and the
 * Overview banner. "Connected" means a handshake newer than the server's own
 * stale threshold — the client never decides that on its own.
 */
export const vpnStatus = reactive({
	connected: false,
	lastHandshake: null,
	peerCount: 0,
	ready: false,
});

const vpnStatusResource = createResource({
	url: "/api/method/benchpress.api.get_vpn_status",
	auto: true,
	onSuccess(data) {
		const status = data?.message ?? data ?? {};
		vpnStatus.connected = status.connected ?? false;
		vpnStatus.lastHandshake = status.last_handshake ?? null;
		vpnStatus.peerCount = status.peer_count ?? 0;
		vpnStatus.ready = true;
	},
	onError() {
		vpnStatus.ready = true;
	},
});

export async function reloadVpnStatus() {
	await vpnStatusResource.reload();
}

/**
 * Refresh on a real signal rather than on a timer.
 *
 * The tunnel is brought up outside this app, in the WireGuard client, so nothing
 * here can be told when it happens. Fetching once per boot meant a user who
 * connected while sitting on a lab page watched "Open site" and "Open VS Code"
 * stay disabled until a hard reload, which reads as a broken button rather than
 * a stale one. Coming back to the tab is exactly when that is most likely to
 * have just changed, and it costs one request — so this stays an event, not the
 * poll this codebase avoids everywhere else.
 */
if (typeof window !== "undefined") {
	window.addEventListener("focus", reloadVpnStatus);
}
