<template>
	<span v-if="lease.state !== NONE" class="text-2xs" :class="TONES[lease.tone].text" data-test="lease-countdown">
		<template v-if="lease.state === EXPIRING">Lease ended — stopping…</template>
		<template v-else>Lease ends in {{ lease.label }}</template>
	</span>
</template>

<script setup>
// The smallest leaf that ticks, so a repaint touches a text node rather than a
// row that also recomputes status theming and usage.
//
// At client zero it shows "stopping…" and waits. It does not flip the badge and
// it calls nothing: client zero precedes the real stop by up to the sweep's tick
// plus the stop itself, and the server is the only thing that decides expiry.
import { serverNow, subscribe } from "@/utils/clock";
import { EXPIRING, NONE, SECOND, leaseFor } from "@/utils/lease";
import { TONES } from "@/utils/statusThemes";
import { computed, onBeforeUnmount, ref, watch } from "vue";

const props = defineProps({
	// `Bench Instance.expires_at_ts` — epoch seconds, or null on a bench with no lease.
	expiresAtTs: { type: Number, default: null },
});

const now = ref(serverNow());
let unsubscribe = null;

const expiresAtMs = computed(() => (props.expiresAtTs ? props.expiresAtTs * SECOND : null));
const lease = computed(() => leaseFor(expiresAtMs.value, now.value));

watch(
	() => lease.value.tickPeriod,
	(period) => {
		unsubscribe?.();
		unsubscribe = null;
		if (period) unsubscribe = subscribe((corrected) => (now.value = corrected), period);
	},
	{ immediate: true }
);

onBeforeUnmount(() => unsubscribe?.());
</script>
