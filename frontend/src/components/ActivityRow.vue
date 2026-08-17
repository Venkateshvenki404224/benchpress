<template>
	<div class="flex items-baseline gap-2.5 px-4 py-2.5">
		<span class="size-[6px] flex-none rounded-full" :class="themeFor(event.log_type).dot" />
		<p class="min-w-0 flex-1 text-xs text-ink-gray-7">{{ event.message }}</p>
		<span class="flex-none text-2xs text-ink-gray-4">{{ relativeTime }}</span>
	</div>
</template>

<script setup>
// One deploy or build event, rendered the same way in the Overview feed and in
// the notifications panel — both read the same `activity` payload.
import { themeFor } from "@/utils/statusThemes";
import { dayjsLocal } from "frappe-ui";
import { computed } from "vue";

const props = defineProps({
	event: { type: Object, required: true },
});

const relativeTime = computed(() =>
	props.event.timestamp ? dayjsLocal(props.event.timestamp).fromNow() : ""
);
</script>
