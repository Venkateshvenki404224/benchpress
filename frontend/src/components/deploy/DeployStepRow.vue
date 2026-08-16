<template>
	<li
		class="flex items-start gap-2.5 px-4 py-2"
		:data-test="`step-${step.key}`"
		:data-state="step.state"
	>
		<span class="mt-0.5 grid size-4 flex-none place-items-center">
			<CheckIcon v-if="step.state === DONE" class="size-3.5 text-ink-green-3" />
			<!-- The one spinner this design permits, and the only motion on the
			     page: it means the server is working on this step right now. -->
			<span
				v-else-if="step.state === ACTIVE"
				class="size-3.5 animate-step-spin rounded-full border-2 border-outline-gray-2 border-t-ink-blue-3"
			/>
			<span
				v-else-if="step.state === FAILED"
				class="grid size-3.5 place-items-center rounded-full bg-surface-red-4 text-[9px] font-bold leading-none text-surface-white"
			>
				!
			</span>
			<span v-else class="size-1.5 rounded-full bg-surface-gray-4" />
		</span>

		<div class="min-w-0 flex-1">
			<p class="text-body text-ink-gray-8" :class="emphasis">{{ step.label }}</p>
			<p
				v-if="step.detail"
				class="mt-0.5 truncate font-mono text-2xs text-ink-gray-5"
				:data-test="`step-detail-${step.key}`"
			>
				{{ step.detail }}
			</p>
		</div>

		<span
			class="mt-px flex-none text-2xs tabular-nums"
			:class="timingTone"
			:data-test="`step-timing-${step.key}`"
		>
			{{ stepTiming(step) }}
		</span>
	</li>
</template>

<script setup>
import { ACTIVE, DONE, FAILED, stepTiming } from "@/utils/deploySteps";
import { computed } from "vue";
import CheckIcon from "~icons/lucide/check";

// One step of the deploy pipeline. Everything it renders is a reading of what
// the backend emitted — this component has no timer and no state of its own.
const props = defineProps({
	step: { type: Object, required: true },
});

const emphasis = computed(() =>
	[ACTIVE, FAILED].includes(props.step.state) ? "font-semibold" : ""
);

const timingTone = computed(() => {
	if (props.step.state === FAILED) return "text-ink-red-4";
	if (props.step.state === ACTIVE) return "text-ink-blue-3";
	return "text-ink-gray-5";
});
</script>
