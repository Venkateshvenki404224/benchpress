<template>
	<section
		class="rounded-card border border-outline-red-1 bg-surface-red-1 p-4"
		data-test="lab-error-banner"
	>
		<div class="flex items-start gap-2.5">
			<AlertIcon class="mt-px size-4 flex-none text-ink-red-4" />
			<div class="min-w-0 flex-1">
				<h2 class="text-sm font-semibold text-ink-red-4" data-test="failure-step">
					{{ headline }}
				</h2>
				<pre
					class="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-words rounded border border-outline-red-1 bg-surface-white px-2.5 py-2 font-mono text-2xs text-ink-gray-8"
					data-test="failure-reason"
					>{{ failure.reason || "No reason was recorded in the log." }}</pre
				>
				<div class="mt-3 flex flex-wrap gap-2">
					<Button
						v-if="isAdmin"
						variant="subtle"
						data-test="edit-and-rebuild"
						@click="emit('edit')"
					>
						Edit apps and rebuild
					</Button>
					<Button variant="subtle" data-test="view-failing-log" @click="emit('view-log')">
						View failing log lines
					</Button>
				</div>
			</div>
		</div>
	</section>
</template>

<script setup>
// Journey §7D: a failed run must say which step broke and why, on the screen
// the user is already on. The step and reason are extracted server-side by
// `lab_detail`, so nothing here parses a raw log.
import { Button } from "frappe-ui";
import { computed } from "vue";

import AlertIcon from "~icons/lucide/circle-alert";

const RUN_LABEL = { build: "Image build failed", deploy: "Deploy failed" };

const props = defineProps({
	// The `failure` object `benchpress.api.get_lab` returns.
	failure: { type: Object, required: true },
	isAdmin: { type: Boolean, default: false },
});

const emit = defineEmits(["edit", "view-log"]);

const headline = computed(() => {
	const run = RUN_LABEL[props.failure.source] ?? "Last run failed";
	return props.failure.step ? `${run} at: ${props.failure.step}` : run;
});
</script>
