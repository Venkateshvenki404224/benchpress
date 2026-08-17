<template>
	<div class="min-w-0">
		<p class="truncate text-meta tabular-nums text-ink-gray-7">{{ usage.label }}</p>
		<p v-if="usage.note" class="truncate text-2xs text-ink-gray-4">{{ usage.note }}</p>
		<Progress class="mt-1" :class="fillClass" size="md" :value="usage.value" />
	</div>
</template>

<script setup>
// A measured, busy container is green in the design, memory past its warning
// threshold is amber and a stale or idle one is neutral. The tone comes from the
// one colour map, `utils/statusThemes`, which owns the Progress-fill override
// too — see `fillFor` for why re-colouring beats forking the component.
import { fillFor } from "@/utils/statusThemes";
import { Progress } from "frappe-ui";
import { computed } from "vue";

const props = defineProps({
	// The object `utils/benchUsage.usageFor` or `utils/containerStats` returns.
	usage: { type: Object, required: true },
});

const fillClass = computed(() => fillFor(props.usage.tone));
</script>
