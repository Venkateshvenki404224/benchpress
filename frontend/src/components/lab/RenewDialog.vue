<template>
	<Dialog v-model="isOpen" :options="{ title: 'Renew lease', size: 'sm' }" data-test="renew-dialog">
		<template #body-content>
			<p class="text-body text-ink-gray-6">
				{{ prompt }}
			</p>

			<div class="mt-3 space-y-1.5">
				<label
					v-for="plan in leasePlans.plans"
					:key="plan.name"
					class="flex cursor-pointer items-center justify-between rounded-md border p-2.5"
					:class="
						chosen === plan.name
							? 'border-outline-gray-4 bg-surface-gray-2'
							: 'border-outline-gray-1'
					"
					:data-test="`renew-plan-${plan.name}`"
				>
					<span class="flex items-center gap-2">
						<input v-model="chosen" type="radio" :value="plan.name" name="lease-plan" />
						<span class="text-sm text-ink-gray-8">{{ plan.plan_label }}</span>
					</span>
					<span class="text-2xs text-ink-gray-5">{{ plan.credits }} credits</span>
				</label>
			</div>

			<!-- The price is on the button, not only in the list: a purchase confirmed
			     by a button that does not name its price is a support ticket. -->
			<Button
				class="mt-3 w-full"
				variant="solid"
				:disabled="!chosen"
				:loading="busy"
				data-test="renew-confirm"
				@click="confirm"
			>
				{{ buttonLabel }}
			</Button>
			<ErrorMessage class="mt-2" :message="error" />
		</template>
	</Dialog>
</template>

<script setup>
// Nothing is selected by default. A renewal spends credits, so the first click
// picks a duration and the second one buys it.
import { leasePlans, loadLeasePlans, newRequestId, renewBench } from "@/data/lease";
import { Button, Dialog, ErrorMessage } from "frappe-ui";
import { computed, ref, watch } from "vue";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	benchName: { type: String, required: true },
	// Shown when the bench is stopped, where renewing also starts it again.
	stopped: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue", "renewed"]);

const chosen = ref("");
const busy = ref(false);
const error = ref("");
// Held for the whole dialog, so a retry after a failure is the same purchase.
let requestId = newRequestId();

const isOpen = computed({
	get: () => props.modelValue,
	set: (value) => emit("update:modelValue", value),
});

const prompt = computed(() =>
	props.stopped
		? "This starts the bench again and buys it a new window."
		: "Time is added to the deadline you already have."
);

const buttonLabel = computed(() => {
	const plan = leasePlans.plans.find((row) => row.name === chosen.value);
	if (!plan) return "Renew";
	return `Renew ${plan.plan_label} · ${plan.credits} credits`;
});

watch(isOpen, (open) => {
	if (!open) return;
	loadLeasePlans();
	chosen.value = "";
	error.value = "";
	requestId = newRequestId();
});

async function confirm() {
	if (!chosen.value || busy.value) return;
	busy.value = true;
	error.value = "";
	try {
		emit("renewed", await renewBench({ benchName: props.benchName, plan: chosen.value, requestId }));
		isOpen.value = false;
	} catch (failure) {
		error.value = failure?.messages?.[0] || failure?.message || "That renewal did not go through.";
	} finally {
		busy.value = false;
	}
}
</script>
