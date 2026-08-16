<template>
	<SectionCard title="Shared infrastructure" data-test="infrastructure">
		<div
			v-for="check in checks"
			:key="check.check"
			class="flex items-center gap-2.5 py-1.5"
			:data-test="`infrastructure-${check.check}`"
		>
			<span class="flex-1 truncate text-body text-ink-gray-7">{{ check.label }}</span>
			<Tooltip :text="check.hint">
				<StatusBadge :status="check.status" />
			</Tooltip>
		</div>
	</SectionCard>
</template>

<script setup>
import SectionCard from "@/components/SectionCard.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { Tooltip } from "frappe-ui";

// The five real checks from benchpress.diagnostics — never a placeholder list.
defineProps({
	checks: { type: Array, default: () => [] },
});
</script>
