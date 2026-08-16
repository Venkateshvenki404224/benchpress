<template>
	<div class="rounded-card border border-outline-gray-1 bg-surface-white px-4 py-3">
		<p class="text-meta text-ink-gray-5">{{ label }}</p>
		<div class="mt-1 flex items-baseline gap-2">
			<span class="text-stat font-semibold tabular-nums" :class="valueClass">{{
				value
			}}</span>
			<span v-if="note" class="text-meta text-ink-gray-4">{{ note }}</span>
		</div>
	</div>
</template>

<script setup>
import { TONES } from "@/utils/statusThemes";
import { computed } from "vue";

const props = defineProps({
	label: { type: String, required: true },
	value: { type: [String, Number], required: true },
	note: { type: String, default: "" },
	// "red" makes a non-zero "Needs attention" read as a problem; "green"
	// marks a healthy count. Anything else stays ink.
	tone: { type: String, default: "" },
});

const valueClass = computed(() => TONES[props.tone]?.text ?? "text-ink-gray-9");
</script>
