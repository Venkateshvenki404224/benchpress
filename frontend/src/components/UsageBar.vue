<template>
	<div class="min-w-0">
		<p class="truncate text-meta tabular-nums text-ink-gray-7">{{ usage.label }}</p>
		<p v-if="usage.note" class="truncate text-2xs text-ink-gray-4">{{ usage.note }}</p>
		<Progress class="mt-1" :class="fillClass" size="md" :value="usage.value" />
	</div>
</template>

<script setup>
// frappe-ui's Progress paints its fill `bg-surface-gray-7` with no colour prop.
// A measured, busy container is green in the design and a stale or idle one is
// neutral, so the tone is applied by re-colouring that fill from the wrapper
// rather than forking the component. If the class ever moves, the bar falls
// back to the stock fill — it never disappears.
import { Progress } from "frappe-ui";
import { computed } from "vue";

const props = defineProps({
	// The object `utils/benchUsage.usageFor` returns.
	usage: { type: Object, required: true },
});

const fillClass = computed(() =>
	props.usage.tone === "green"
		? "[&_.bg-surface-gray-7]:bg-surface-green-3"
		: "[&_.bg-surface-gray-7]:bg-surface-gray-3"
);
</script>
