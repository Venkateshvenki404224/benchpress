<template>
	<div class="flex flex-wrap items-center gap-2">
		<LeaseCountdown v-if="!stopped" :expires-at-ts="bench.expires_at_ts" />
		<span v-else class="text-2xs text-ink-gray-5" data-test="grace-countdown">
			<template v-if="grace.action === REDEPLOY">Torn down — redeploy to start again</template>
			<template v-else-if="grace.label">Can be restored for {{ grace.label }}</template>
			<template v-else>Can be restored</template>
		</span>

		<Button
			v-if="offered"
			variant="subtle"
			:data-test="action === RENEW ? 'renew-lease' : 'redeploy-lease'"
			@click="act"
		>
			{{ action === RENEW ? "Renew" : "Redeploy" }}
		</Button>

		<RenewDialog
			v-model="dialogOpen"
			:bench-name="bench.name"
			:stopped="stopped"
			@renewed="emit('renewed', $event)"
		/>
	</div>
</template>

<script setup>
// The call to action lives beside the countdown, because that is where somebody
// realises they need it. It changes to Redeploy once the reaper has taken the
// container: a button that fails is worse than one that changed.
import LeaseCountdown from "@/components/lab/LeaseCountdown.vue";
import RenewDialog from "@/components/lab/RenewDialog.vue";
import { creditsEnabled } from "@/data/credits";
import { serverNow, subscribe } from "@/utils/clock";
import { REDEPLOY, RENEW, SECOND, graceFor } from "@/utils/lease";
import { Button } from "frappe-ui";
import { computed, onBeforeUnmount, ref, watch } from "vue";

const props = defineProps({
	bench: { type: Object, required: true },
});

const emit = defineEmits(["renewed", "redeploy"]);

const now = ref(serverNow());
const dialogOpen = ref(false);
let unsubscribe = null;

const stopped = computed(() => props.bench.status === "Stopped");
const graceEndsAtMs = computed(() =>
	props.bench.grace_ends_at_ts ? props.bench.grace_ends_at_ts * SECOND : null
);
const grace = computed(() => graceFor(graceEndsAtMs.value, now.value));
const action = computed(() => (stopped.value ? grace.value.action : RENEW));

// Nothing to renew on a bench that never held a lease, and nothing to sell on a
// site with credits switched off.
const offered = computed(
	() => creditsEnabled.value && (stopped.value || !!props.bench.expires_at_ts)
);

watch(
	() => (stopped.value ? grace.value.tickPeriod : 0),
	(period) => {
		unsubscribe?.();
		unsubscribe = null;
		if (period) unsubscribe = subscribe((corrected) => (now.value = corrected), period);
	},
	{ immediate: true }
);

onBeforeUnmount(() => unsubscribe?.());

function act() {
	if (action.value === RENEW) dialogOpen.value = true;
	else emit("redeploy");
}
</script>
