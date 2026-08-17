<template>
	<div
		v-if="visible"
		class="mt-3 rounded-md border border-outline-gray-1 bg-surface-gray-1 p-3"
		data-test="always-on-upsell"
	>
		<template v-if="until">
			<p class="text-xs font-medium text-ink-gray-9">Always on</p>
			<p class="mt-0.5 text-2xs text-ink-gray-5">
				Exempt from the run limit until {{ untilLabel }}.
			</p>
		</template>

		<template v-else>
			<p class="text-xs font-medium text-ink-gray-9">Keep this instance up</p>
			<p class="mt-0.5 text-2xs text-ink-gray-5">
				An Always On Pass exempts it from the run limit — and from hourly credits — for
				{{ purchaseOptions.alwaysOnDays }} days.
			</p>
			<Button class="mt-2" variant="subtle" :loading="busy" @click="buy">
				Buy for {{ rupees }}
			</Button>
			<ErrorMessage v-if="error" class="mt-2" :message="error" />
		</template>
	</div>
</template>

<script setup>
// The upsell belongs where the frustration is: on an instance that has just been stopped by the
// clock, and on one already paid for so nobody buys a second month by mistake. It is deliberately
// not on a pricing page — a pass is worth nothing to somebody who is not looking at a stopped
// instance, and worth exactly its price to somebody who is.
import { buyAlwaysOnPass, loadPurchaseOptions, purchaseOptions } from "@/data/payments";
import { creditsEnabled } from "@/data/credits";
import { Button, ErrorMessage, dayjsLocal } from "frappe-ui";
import { computed, onMounted, ref } from "vue";

const props = defineProps({
	bench: { type: Object, required: true },
	label: { type: String, default: "This instance" },
});

const emit = defineEmits(["bought"]);

const busy = ref(false);
const error = ref("");

onMounted(loadPurchaseOptions);

const until = computed(() => props.bench?.always_on_until ?? null);
const untilLabel = computed(() =>
	until.value ? dayjsLocal(until.value).format("D MMM YYYY") : ""
);

/** Offer nothing unless there is a gateway, a price, and something to say. */
const visible = computed(
	() =>
		creditsEnabled.value &&
		(until.value || (purchaseOptions.available && purchaseOptions.alwaysOnInr))
);

const rupees = computed(
	() => `₹${Number(purchaseOptions.alwaysOnInr ?? 0).toLocaleString("en-IN")}`
);

async function buy() {
	busy.value = true;
	error.value = "";
	try {
		if (await buyAlwaysOnPass(props.bench.name, props.label)) emit("bought");
	} catch (failure) {
		error.value =
			failure?.messages?.[0] || failure?.message || "That purchase could not be started.";
	} finally {
		busy.value = false;
	}
}
</script>
