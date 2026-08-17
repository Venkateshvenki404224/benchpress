<template>
	<div
		class="flex flex-wrap items-center gap-3 rounded-card border px-4 py-3.5"
		:class="
			connected
				? 'border-outline-green-1 bg-surface-green-1'
				: 'border-outline-amber-1 bg-surface-amber-1'
		"
		data-test="vpn-status-banner"
	>
		<span
			class="size-2.5 flex-none rounded-full"
			:class="connected ? 'bg-surface-green-3' : 'bg-surface-amber-2 animate-vpn-pulse'"
		/>
		<div class="min-w-[220px] flex-1">
			<p
				class="text-body font-semibold"
				:class="connected ? 'text-ink-green-3' : 'text-ink-amber-3'"
				data-test="banner-title"
			>
				{{ banner.title }}
			</p>
			<p class="mt-0.5 text-2xs text-ink-gray-7" data-test="banner-body">
				{{ banner.body }}
			</p>
		</div>
		<Button
			:variant="connected ? 'subtle' : 'solid'"
			:loading="checking"
			data-test="banner-action"
			@click="emit('act', banner.action)"
		>
			{{ banner.actionLabel }}
		</Button>
	</div>
</template>

<script setup>
// Whether this machine is on the tunnel. The verdict is the server's — this
// component only renders it and offers the one action the browser can perform.
import { bannerState } from "@/utils/vpnJourney";
import { Button } from "frappe-ui";
import { computed } from "vue";

const props = defineProps({
	connected: { type: Boolean, default: false },
	handshakeAgeSeconds: { type: Number, default: null },
	deviceCount: { type: Number, default: 0 },
	checking: { type: Boolean, default: false },
});

const emit = defineEmits(["act"]);

const banner = computed(() =>
	bannerState({
		connected: props.connected,
		handshakeAgeSeconds: props.handshakeAgeSeconds,
		deviceCount: props.deviceCount,
	})
);
</script>
