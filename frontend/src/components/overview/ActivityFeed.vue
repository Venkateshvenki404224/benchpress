<template>
	<SectionCard title="Recent activity" :padded="false" data-test="activity">
		<EmptyState
			v-if="!events.length"
			:message="`Nothing has been deployed or built in the last ${windowDays} days.`"
		/>
		<div
			v-for="(event, index) in events"
			:key="`${event.timestamp}-${index}`"
			class="flex items-baseline gap-2.5 border-b border-outline-gray-1 px-4 py-2.5 last:border-b-0"
		>
			<span class="size-[6px] flex-none rounded-full" :class="dotClass(event)" />
			<p class="min-w-0 flex-1 text-xs text-ink-gray-7">{{ event.message }}</p>
			<span class="flex-none text-2xs text-ink-gray-4">{{
				relativeTime(event.timestamp)
			}}</span>
		</div>
	</SectionCard>
</template>

<script setup>
import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";
import { themeFor } from "@/utils/statusThemes";
import { dayjsLocal } from "frappe-ui";

defineProps({
	events: { type: Array, default: () => [] },
	windowDays: { type: Number, default: 7 },
});

function dotClass(event) {
	return themeFor(event.log_type).dot;
}

function relativeTime(timestamp) {
	return timestamp ? dayjsLocal(timestamp).fromNow() : "";
}
</script>
