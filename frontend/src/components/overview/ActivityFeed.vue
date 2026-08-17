<template>
	<SectionCard title="Recent activity" :padded="false" data-test="activity">
		<EmptyState
			v-if="!events.length"
			:message="`Nothing has been deployed or built in the last ${windowDays} days.`"
		/>
		<ActivityRow
			v-for="(event, index) in events"
			:key="`${event.timestamp}-${index}`"
			:event="event"
			class="border-b border-outline-gray-1 last:border-b-0"
		/>
	</SectionCard>
</template>

<script setup>
import ActivityRow from "@/components/ActivityRow.vue";
import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";

defineProps({
	events: { type: Array, default: () => [] },
	windowDays: { type: Number, default: 7 },
});
</script>
