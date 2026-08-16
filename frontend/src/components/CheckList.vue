<template>
	<div
		v-for="check in checks"
		:key="check.check"
		class="py-1.5"
		:data-test="`${testPrefix}-${check.check}`"
	>
		<div class="flex items-center gap-2.5">
			<span class="flex-1 truncate text-body text-ink-gray-7">{{ check.label }}</span>
			<Tooltip :text="check.hint">
				<StatusBadge :status="check.status" />
			</Tooltip>
		</div>
		<p v-if="failed(check)" class="mt-1 text-2xs text-ink-gray-6" data-test="check-hint">
			{{ check.hint }}
		</p>
	</div>
</template>

<script setup>
// One renderer for both check lists: the admin's shared-infrastructure rows and
// the user's connection test. A failing row spells its hint out on the screen —
// a tooltip is the wrong place for the one sentence that says what to do.
import StatusBadge from "@/components/StatusBadge.vue";
import { Tooltip } from "frappe-ui";

defineProps({
	checks: { type: Array, default: () => [] },
	testPrefix: { type: String, required: true },
});

function failed(check) {
	return check.status !== "Active";
}
</script>
