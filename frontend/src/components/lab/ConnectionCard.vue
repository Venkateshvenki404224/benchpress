<template>
	<SectionCard title="Connection" data-test="connection-card">
		<div
			class="rounded-md border p-3"
			:class="
				connected
					? 'border-outline-green-1 bg-surface-green-1'
					: 'border-outline-amber-1 bg-surface-amber-1'
			"
		>
			<div class="flex items-center gap-2">
				<span
					class="size-[5px] rounded-full"
					:class="
						connected ? 'bg-surface-green-3' : 'bg-surface-amber-2 animate-vpn-pulse'
					"
				/>
				<p
					class="text-sm font-semibold"
					:class="connected ? 'text-ink-green-3' : 'text-ink-amber-3'"
					data-test="connection-state"
				>
					{{ connected ? "VPN connected" : "VPN off" }}
				</p>
			</div>
			<p class="mt-1.5 text-2xs text-ink-gray-6">
				{{
					connected
						? "This device is on the tunnel, so the site, SSH and the IDE are reachable."
						: "This bench only answers over WireGuard. Register this device to reach its site, SSH and IDE."
				}}
			</p>
			<Button
				v-if="!connected"
				class="mt-3"
				variant="subtle"
				size="sm"
				data-test="register-device"
				@click="emit('register')"
			>
				Register this device
			</Button>
		</div>
	</SectionCard>
</template>

<script setup>
// Whether this device can actually reach the bench. The state is the server's
// call — `get_vpn_status` compares the newest handshake against the VPN app's
// own stale threshold — so nothing is decided here.
import SectionCard from "@/components/SectionCard.vue";
import { Button } from "frappe-ui";

defineProps({
	connected: { type: Boolean, default: false },
});

const emit = defineEmits(["register"]);
</script>
