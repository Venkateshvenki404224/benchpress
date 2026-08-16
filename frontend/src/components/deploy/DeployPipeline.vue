<template>
	<div data-test="deploy-pipeline">
		<SectionCard :padded="false">
			<template #default>
				<header
					class="flex flex-wrap items-center gap-2 border-b border-outline-gray-1 px-4 py-3"
				>
					<h2 class="text-sm font-semibold text-ink-gray-9">{{ title }}</h2>
					<StatusBadge :status="RESULTS[run.state]" />
					<span class="ml-auto text-2xs text-ink-gray-5" data-test="run-elapsed">
						{{ elapsedLabel }}
					</span>
				</header>

				<ol v-if="run.structured" class="divide-y divide-outline-gray-1" data-test="step-list">
					<DeployStepRow v-for="step in run.steps" :key="step.key" :step="step" />
				</ol>
				<p v-else class="px-4 py-3 text-body text-ink-gray-5" data-test="no-step-data">
					This run was recorded before the pipeline reported its steps — only the raw
					log below was kept.
				</p>
			</template>
		</SectionCard>

		<RawLogPanel class="mt-3" :raw-log="rawLog" :file-name="fileName" />
	</div>
</template>

<script setup>
import SectionCard from "@/components/SectionCard.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import DeployStepRow from "@/components/deploy/DeployStepRow.vue";
import RawLogPanel from "@/components/deploy/RawLogPanel.vue";
import { deriveRun, formatDuration } from "@/utils/deploySteps";
import { computed } from "vue";

// The eleven steps, their state and their real durations, all read out of the
// log the backend wrote. Live and historical runs take the same path: the only
// difference between them is whether the string is still growing.
const RESULTS = {
	success: "Success",
	failed: "Failed",
	running: "Deploying",
	idle: "Pending",
};

const props = defineProps({
	rawLog: { type: String, default: "" },
	title: { type: String, default: "Deploy run" },
	fileName: { type: String, default: "deploy.log" },
});

const run = computed(() => deriveRun(props.rawLog));

const elapsedLabel = computed(() => {
	if (!run.value.structured) return "";
	const total = formatDuration(run.value.totalElapsed);
	return run.value.state === "running" ? `${total} so far` : total;
});
</script>
