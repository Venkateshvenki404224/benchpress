<template>
	<SectionCard title="Container" data-test="container-status">
		<template #action>
			<StatusBadge :status="bench.status" />
		</template>

		<!-- The §8.7 fix: a bench's own state and what Docker reports about its
		     container are independent axes. Both are shown, always, and the
		     health badge carries the age of the reading behind it. -->
		<div class="flex flex-wrap items-center gap-2" data-test="container-health">
			<span class="text-meta text-ink-gray-6">Health</span>
			<StatusBadge :status="bench.container_health" />
			<span class="text-2xs text-ink-gray-5" data-test="health-checked">
				{{ healthCaption(healthAgeSeconds) }}
			</span>
		</div>

		<div class="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
			<div class="rounded-md border border-outline-gray-1 p-3" data-test="cpu-meter">
				<p class="mb-1.5 text-2xs uppercase tracking-wide text-ink-gray-5">CPU</p>
				<UsageBar :usage="cpu" />
			</div>
			<div class="rounded-md border border-outline-gray-1 p-3" data-test="memory-meter">
				<p class="mb-1.5 text-2xs uppercase tracking-wide text-ink-gray-5">Memory</p>
				<UsageBar :usage="memory" />
			</div>
		</div>

		<div class="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1">
			<p v-if="startedLabel" class="text-2xs text-ink-gray-5" data-test="container-started">
				Started {{ startedLabel }}
			</p>
			<span v-if="startedLabel && bench.expires_at_ts" class="text-2xs text-ink-gray-4"
				>·</span
			>
			<LeaseControl
				:bench="bench"
				@renewed="emit('renewed', $event)"
				@redeploy="emit('redeploy')"
			/>
		</div>
	</SectionCard>
</template>

<script setup>
import SectionCard from "@/components/SectionCard.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import UsageBar from "@/components/UsageBar.vue";
import LeaseControl from "@/components/lab/LeaseControl.vue";
import { cpuMeter, healthCaption, memoryMeter } from "@/utils/containerStats";
import { dayjsLocal } from "frappe-ui";
import { computed } from "vue";

const props = defineProps({
	bench: { type: Object, required: true },
	lab: { type: Object, required: true },
	// Age of `last_health_check` in seconds; null when the bench was never polled.
	healthAgeSeconds: { type: Number, default: null },
});

const emit = defineEmits(["renewed", "redeploy"]);

const cpu = computed(() => cpuMeter(props.bench, props.lab));
const memory = computed(() => memoryMeter(props.bench, props.lab));

const startedLabel = computed(() =>
	props.bench.started_at ? dayjsLocal(props.bench.started_at).fromNow() : ""
);
</script>
