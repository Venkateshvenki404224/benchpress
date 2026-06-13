<template>
	<div class="space-y-2 rounded-lg bg-surface-gray-7 p-3">
		<LogStep
			v-for="(step, idx) in steps"
			:key="idx"
			:title="step.title"
			:output="step.output"
			:status="step.status"
			:duration="step.duration"
			:defaultOpen="step.defaultOpen"
		/>
		<div v-if="!steps.length" class="py-8 text-center text-sm text-ink-gray-5">
			No log output yet.
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import LogStep from "./LogStep.vue";

const props = defineProps({
	rawLog: { type: String, default: "" },
});

const steps = computed(() => parseLog(props.rawLog));

function parseLog(raw) {
	if (!raw) return [];

	const lines = raw.split("\n");
	const steps = [];
	let current = null;

	for (const line of lines) {
		const stepMatch = line.match(/^Step (\d+\/\d+)\s*:\s*(.*)/);
		const headerMatch = line.match(/^===\s*(.*)/);

		if (stepMatch) {
			if (current) steps.push(current);
			current = {
				title: `Step ${stepMatch[1]} : ${stepMatch[2]}`,
				output: "",
				status: "running",
				defaultOpen: false,
			};
		} else if (headerMatch) {
			const text = headerMatch[1].trim();
			if (current) steps.push(current);

			if (
				text.toLowerCase().includes("build complete") ||
				text.toLowerCase().includes("build successful") ||
				text.toLowerCase().includes("deploy complete")
			) {
				current = { title: text, output: "", status: "success", defaultOpen: false };
			} else if (
				text.toLowerCase().includes("build failed") ||
				text.toLowerCase().includes("deploy failed") ||
				text.toLowerCase().includes("error")
			) {
				current = { title: text, output: "", status: "error", defaultOpen: true };
			} else {
				current = { title: text, output: "", status: "running", defaultOpen: false };
			}
		} else if (current) {
			current.output += (current.output ? "\n" : "") + line;
		} else {
			if (!steps.length || steps[steps.length - 1]?.title !== "Initialization") {
				current = {
					title: "Initialization",
					output: line,
					status: "running",
					defaultOpen: true,
				};
			} else {
				current = steps.pop();
				current.output += "\n" + line;
			}
		}
	}

	if (current) steps.push(current);

	for (let i = 0; i < steps.length; i++) {
		const s = steps[i];
		if (s.status === "error") continue;
		if (s.output.match(/ERROR|error|FAILED|failed/)) {
			s.status = "error";
			s.defaultOpen = true;
		} else if (i < steps.length - 1) {
			if (s.status === "running") s.status = "success";
		}
	}

	if (steps.length) {
		steps[steps.length - 1].defaultOpen = true;
	}

	return steps;
}
</script>
