<template>
	<div class="p-4">
		<div class="mb-4 flex items-center justify-between">
			<h1 class="text-xl font-semibold text-ink-gray-9">Bench Instances</h1>
		</div>

		<ListView
			v-if="benches.data?.length"
			:columns="columns"
			:rows="benches.data"
			:options="{
				showTooltip: true,
				resizeColumn: true,
				selectable: false,
			}"
			row-key="name"
		/>
		<div v-else-if="benches.loading" class="text-base text-ink-gray-5">Loading...</div>
		<div v-else class="py-12 text-center text-base text-ink-gray-5">
			No bench instances found. Deploy a lab to create one.
		</div>
	</div>
</template>

<script setup>
import { ListView, Badge, useList } from "frappe-ui";
import { h } from "vue";

const columns = [
	{ label: "Bench Name", key: "bench_name", width: "200px" },
	{ label: "Lab", key: "lab", width: "150px" },
	{ label: "Version", key: "frappe_version", width: "120px" },
	{
		label: "Status",
		key: "status",
		width: "120px",
		getLabel: ({ row }) => row.status,
		prefix: ({ row }) => {
			const color =
				{
					Running: "green",
					Deploying: "orange",
					Stopped: "red",
					Error: "red",
					Draft: "gray",
				}[row.status] || "gray";
			return h(Badge, { label: row.status, theme: color, size: "sm" });
		},
	},
	{
		label: "Public",
		key: "is_public",
		width: "140px",
		getLabel: ({ row }) => (row.is_public ? "Public" : "Private"),
		prefix: ({ row }) => {
			const badge = h(Badge, {
				label: row.is_public ? "Public" : "Private",
				theme: row.is_public ? "green" : "gray",
				size: "sm",
			});
			return row.public_url
				? h(
						"a",
						{
							href: row.public_url,
							target: "_blank",
							rel: "noopener",
							onClick: (e) => e.stopPropagation(),
						},
						[badge]
				  )
				: badge;
		},
	},
	{
		label: "Health",
		key: "health_status",
		width: "120px",
		getLabel: ({ row }) => row.health_status || "—",
		prefix: ({ row }) =>
			row.health_status
				? h(Badge, {
						label: row.health_status,
						theme:
							{ Healthy: "green", Unhealthy: "red", Unknown: "gray" }[
								row.health_status
							] || "gray",
						size: "sm",
				  })
				: null,
	},
	{
		label: "IP Address",
		key: "wg_ip",
		width: "140px",
		getLabel: ({ row }) => row.wg_ip || row.container_ip || "—",
	},
	{ label: "CPU %", key: "cpu_usage", width: "80px" },
	{ label: "Memory %", key: "memory_usage", width: "100px" },
];

const benches = useList({
	doctype: "Bench Instance",
	fields: [
		"name",
		"bench_name",
		"lab",
		"frappe_version",
		"domain",
		"status",
		"is_public",
		"public_url",
		"health_status",
		"container_id",
		"container_ip",
		"wg_ip",
		"cpu_usage",
		"memory_usage",
		"started_at",
	],
	orderBy: "creation desc",
	limit: 100,
});
</script>
