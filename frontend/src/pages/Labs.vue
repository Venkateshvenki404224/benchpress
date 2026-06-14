<template>
	<div class="p-4">
		<div class="mb-4 flex items-center justify-between">
			<h1 class="text-xl font-semibold text-ink-gray-9">Labs</h1>
			<div v-if="userContext.isAdmin" class="flex gap-2">
				<Button
					appearance="minimal"
					icon-left="grid"
					@click="$router.push('/labs/templates')"
				>
					From Template
				</Button>
				<Button appearance="primary" icon-left="plus" @click="$router.push('/labs/new')">
					New Lab
				</Button>
			</div>
		</div>

		<!-- Search & Filters -->
		<div class="mb-4 flex items-center gap-3">
			<FormControl
				class="flex-1"
				type="text"
				placeholder="Search by Lab ID, title, or app name..."
				v-model="searchQuery"
				icon-left="search"
			/>
			<FormControl
				type="select"
				:options="statusOptions"
				v-model="statusFilter"
				class="w-40"
			/>
			<FormControl
				type="select"
				:options="versionOptions"
				v-model="versionFilter"
				class="w-44"
			/>
		</div>

		<ListView
			v-if="filteredRows.length"
			:columns="columns"
			:rows="filteredRows"
			:options="{
				getRowRoute: (row) => ({ name: 'LabDetail', params: { labId: row.name } }),
				showTooltip: true,
				resizeColumn: true,
				selectable: false,
			}"
			row-key="name"
		/>
		<div v-else-if="labs.loading" class="text-base text-ink-gray-5">Loading...</div>
		<div v-else class="py-12 text-center text-base text-ink-gray-5">
			{{
				searchQuery || statusFilter !== "All" || versionFilter !== "All"
					? "No labs match your filters."
					: "No labs found. Create your first lab to get started."
			}}
		</div>
	</div>
</template>

<script setup>
import { ref, computed } from "vue";
import { ListView, Button, FormControl, createListResource } from "frappe-ui";
import { userContext } from "@/data/userContext";

const searchQuery = ref("");
const statusFilter = ref("All");
const versionFilter = ref("All");

const statusOptions = [
	{ label: "All Status", value: "All" },
	{ label: "Draft", value: "Draft" },
	{ label: "Building", value: "Building" },
	{ label: "Ready", value: "Ready" },
	{ label: "Error", value: "Error" },
];

const versionOptions = [
	{ label: "All Versions", value: "All" },
	{ label: "Version 14", value: "version-14" },
	{ label: "Version 15", value: "version-15" },
	{ label: "Version 16", value: "version-16" },
	{ label: "Develop", value: "develop" },
];

const columns = [
	{ label: "Lab ID", key: "lab_id", width: "180px" },
	{ label: "Title", key: "title", width: "200px" },
	{ label: "Frappe Version", key: "frappe_version", width: "150px" },
	{ label: "Status", key: "status", width: "120px" },
	{ label: "Memory", key: "memory_limit", width: "100px" },
	{ label: "CPU", key: "cpu_cores", width: "80px" },
];

const labs = createListResource({
	doctype: "Lab",
	fields: [
		"name",
		"lab_id",
		"title",
		"description",
		"frappe_version",
		"status",
		"memory_limit",
		"cpu_cores",
	],
	orderBy: "creation desc",
	pageLength: 100,
	auto: true,
});

const filteredRows = computed(() => {
	if (!labs.data) return [];

	let rows = labs.data;

	if (statusFilter.value !== "All") {
		rows = rows.filter((r) => r.status === statusFilter.value);
	}

	if (versionFilter.value !== "All") {
		rows = rows.filter((r) => r.frappe_version === versionFilter.value);
	}

	if (searchQuery.value) {
		const q = searchQuery.value.toLowerCase();
		rows = rows.filter(
			(r) =>
				(r.lab_id || "").toLowerCase().includes(q) ||
				(r.title || "").toLowerCase().includes(q) ||
				(r.description || "").toLowerCase().includes(q)
		);
	}

	return rows;
});
</script>
