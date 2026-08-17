<template>
	<RunHistory
		title="Build history"
		description="Image builds across every lab. Admin only — users see the deploy history for their own benches."
		back-to="/labs"
		back-label="Labs"
		:columns="COLUMNS"
		:rows="rows"
		:loading="buildHistoryResource.loading"
		empty-message="No image has been built yet. Building a lab is what turns a recipe into something deployable."
		empty-action="Go to Labs"
		:window-days="history.window_days ?? 7"
		:limit="history.limit ?? 0"
		:truncated="Boolean(history.truncated)"
		data-test="build-history"
	/>
</template>

<script setup>
// The table is `RunHistory`; this page supplies what a build run is of. The
// image tag column is what tells two builds of the same lab apart.
import RunHistory from "@/components/RunHistory.vue";
import { buildHistoryResource } from "@/data/runHistory";
import { computed, onMounted } from "vue";

const COLUMNS = [
	{ label: "Lab", key: "subject", width: "196px" },
	{ label: "Image tag", key: "image_tag", width: "184px" },
	{ label: "Result", key: "result", width: "104px" },
	{ label: "Last step", key: "last_step", width: "180px" },
	{ label: "Duration", key: "duration", width: "80px" },
	{ label: "Started", key: "started", width: "96px" },
];

onMounted(() => buildHistoryResource.reload());

const history = computed(() => buildHistoryResource.data ?? {});

const rows = computed(() =>
	(history.value.rows ?? []).map((run) => ({ ...run, subject: run.lab_title || run.lab }))
);
</script>
