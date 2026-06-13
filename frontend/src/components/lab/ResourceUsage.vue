<template>
	<div class="rounded-lg border border-outline-gray-1 bg-surface-white p-5">
		<div class="mb-4 flex items-center justify-between">
			<h2 class="text-base font-semibold text-ink-gray-9">Container Status</h2>
			<div class="flex items-center gap-2">
				<Badge
					v-if="bench.health_status"
					:label="bench.health_status"
					:theme="healthColor(bench.health_status)"
				/>
				<Badge :label="bench.status" :theme="statusColor(bench.status)" />
			</div>
		</div>
		<div class="grid grid-cols-2 gap-4">
			<div class="rounded-lg border border-outline-gray-1 p-4">
				<div class="text-xs text-ink-gray-5">CPU Usage</div>
				<div class="mt-1 text-lg font-semibold text-ink-gray-9">
					{{ bench.cpu_usage || 0 }}%
				</div>
				<Progress class="mt-2" :value="Math.min(bench.cpu_usage || 0, 100)" size="md" />
			</div>
			<div class="rounded-lg border border-outline-gray-1 p-4">
				<div class="text-xs text-ink-gray-5">Memory Usage</div>
				<div class="mt-1 text-lg font-semibold text-ink-gray-9">
					{{ bench.memory_usage || 0 }}%
				</div>
				<Progress class="mt-2" :value="Math.min(bench.memory_usage || 0, 100)" size="md" />
			</div>
		</div>
		<div v-if="bench.started_at" class="mt-3 text-xs text-ink-gray-5">
			Started: {{ bench.started_at }}
		</div>
	</div>
</template>

<script setup>
import { Badge, Progress } from "frappe-ui";

defineProps({
	bench: { type: Object, required: true },
});

function statusColor(status) {
	const map = {
		Draft: "gray",
		Building: "orange",
		Ready: "green",
		Running: "green",
		Deploying: "orange",
		Stopped: "red",
		Error: "red",
		Active: "green",
		Creating: "orange",
		Inactive: "gray",
	};
	return map[status] || "gray";
}

function healthColor(health) {
	const map = { Healthy: "green", Unhealthy: "red", Unknown: "gray" };
	return map[health] || "gray";
}
</script>
