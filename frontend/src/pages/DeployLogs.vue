<template>
	<RunHistory
		title="Deploy history"
		description="Every deploy of the benches you can see, newest first. Open a run to read its log on the lab."
		back-to="/bench-instances"
		back-label="Instances"
		:columns="COLUMNS"
		:rows="rows"
		:loading="deployHistoryResource.loading"
		empty-message="Nothing has been deployed yet. Deploy a lab and the run appears here."
		empty-action="Go to Instances"
		:window-days="history.window_days ?? 7"
		:limit="history.limit ?? 0"
		:truncated="Boolean(history.truncated)"
		data-test="deploy-history"
	/>
</template>

<script setup>
// The same table as Build history, with a bench as the subject. `bench_name` is
// an md5, so a deploy row is named after the lab it deployed — `benchLabel` is
// the one place that convention lives.
import RunHistory from "@/components/RunHistory.vue";
import { deployHistoryResource } from "@/data/runHistory";
import { benchLabel } from "@/utils/labSpecs";
import { computed, onMounted } from "vue";

const COLUMNS = [
	{ label: "Bench", key: "subject", width: "240px" },
	{ label: "Result", key: "result", width: "112px" },
	{ label: "Last step", key: "last_step", width: "210px" },
	{ label: "Duration", key: "duration", width: "88px" },
	{ label: "Started", key: "started", width: "104px" },
];

onMounted(() => deployHistoryResource.reload());

const history = computed(() => deployHistoryResource.data ?? {});

const rows = computed(() =>
	(history.value.rows ?? []).map((run) => ({
		...run,
		subject: benchLabel(run.lab) || run.bench,
	}))
);
</script>
