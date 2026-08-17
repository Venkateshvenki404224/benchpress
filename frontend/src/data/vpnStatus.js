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
