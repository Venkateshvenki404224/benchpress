<template>
	<div class="p-4">
		<ListView
			v-if="deployLogs.data?.length"
			:columns="columns"
			:rows="deployLogs.data"
			:options="{
				selectable: false,
				showTooltip: true,
				resizeColumn: true,
			}"
			row-key="name"
		/>
		<div v-else-if="deployLogs.loading" class="text-base text-ink-gray-5">Loading...</div>
		<div v-else class="text-base text-ink-gray-5">No deploy logs found.</div>
	</div>
</template>

<script setup>
import { ListView, createListResource } from "frappe-ui";

const columns = [
	{ label: "Bench", key: "bench", width: "200px" },
	{ label: "Log Type", key: "log_type", width: "150px" },
	{ label: "Message", key: "message" },
];

let deployLogs = createListResource({
	doctype: "Deploy Log",
	fields: ["name", "bench", "log_type", "message"],
	orderBy: "creation desc",
	start: 0,
	pageLength: 20,
	auto: true,
});
</script>
