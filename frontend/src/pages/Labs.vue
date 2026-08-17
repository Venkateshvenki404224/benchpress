<template>
	<div class="mx-auto max-w-[1180px] px-6 pb-10 pt-[22px]" data-test="labs">
		<div class="mb-3.5 flex flex-wrap items-start gap-3">
			<div>
				<h1 class="text-title font-semibold text-ink-gray-9">Labs</h1>
				<p class="mt-0.5 max-w-[560px] text-body text-ink-gray-5">
					A lab is a reusable recipe — Frappe version, apps and resources. Build it into
					an image, then deploy as many bench instances as you need.
				</p>
			</div>
			<div class="ml-auto flex flex-wrap gap-2">
				<Button
					v-if="userContext.isAdmin"
					variant="subtle"
					data-test="build-history"
					@click="router.push('/build-logs')"
				>
					Build history
				</Button>
				<Button
					variant="subtle"
					data-test="from-template"
					@click="router.push('/labs/templates')"
				>
					From template
				</Button>
				<Button
					v-if="userContext.isAdmin"
					variant="solid"
					data-test="new-lab"
					@click="router.push('/labs/new')"
				>
					<template #prefix><PlusIcon class="size-3.5" /></template>
					New lab
				</Button>
			</div>
		</div>

		<div v-if="labs.length" class="mb-3 flex flex-wrap items-center gap-2">
			<FormControl
				class="w-[240px]"
				type="text"
				placeholder="Search labs"
				v-model="search"
				data-test="labs-search"
			>
				<template #prefix><SearchIcon class="size-3.5 text-ink-gray-4" /></template>
			</FormControl>
			<Select v-model="statusFilter" :options="statusOptions" data-test="filter-status" />
			<Select v-model="versionFilter" :options="versionOptions" data-test="filter-version" />
			<Select v-model="ownerFilter" :options="ownerOptions" data-test="filter-owner" />
		</div>

		<p v-if="labsResource.loading && !labs.length" class="text-body text-ink-gray-5">
			Loading labs…
		</p>

		<OnboardingPanel v-else-if="!labs.length" />

		<DataTable
			v-else-if="rows.length"
			:columns="COLUMNS"
			:rows="rows"
			:row-route="labRoute"
			data-test="labs-table"
		>
			<template #cell="{ column, row }">
				<div v-if="column.key === 'lab'" class="flex min-w-0 items-center gap-2.5">
					<span
						class="grid size-7 flex-none place-items-center rounded-md border border-outline-gray-1 bg-surface-white"
					>
						<AppIcon :app="primaryApp(row)" :size="17" />
					</span>
					<span class="min-w-0" :data-test="`lab-${row.name}`">
						<span class="block truncate text-body font-medium text-ink-gray-9">
							{{ row.title || row.lab_id }}
						</span>
						<span class="block truncate font-mono text-2xs text-ink-gray-4">
							{{ row.lab_id }}
						</span>
					</span>
				</div>

				<span
					v-else-if="column.key === 'frappe_version'"
					class="truncate text-xs text-ink-gray-7"
				>
					{{ row.frappe_version }}
				</span>

				<div v-else-if="column.key === 'apps'" class="flex min-w-0 flex-wrap gap-1">
					<span
						v-for="app in row.app_names"
						:key="app"
						class="rounded bg-surface-gray-2 px-1.5 py-px text-2xs text-ink-gray-7"
					>
						{{ appLabel(app) }}
					</span>
					<span v-if="!row.app_names.length" class="text-2xs text-ink-gray-4">
						Bare bench
					</span>
				</div>

				<StatusBadge v-else-if="column.key === 'status'" :status="row.status" />

				<div v-else-if="column.key === 'deployed_as'" class="min-w-0">
					<template v-if="row.deployed_as">
						<span class="block truncate text-xs text-ink-blue-3">
							{{ row.deployed_as.site || "No site yet" }}
						</span>
						<span class="block truncate text-2xs text-ink-gray-4">
							{{ benchLabel(row.lab_id) }} · {{ row.deployed_as.status }}
						</span>
					</template>
					<span v-else class="text-xs text-ink-gray-4">Never deployed</span>
				</div>

				<span
					v-else-if="column.key === 'last_run'"
					class="truncate text-meta text-ink-gray-5"
				>
					{{ lastRun(row) }}
				</span>
			</template>
		</DataTable>

		<SectionCard v-else :padded="false">
			<EmptyState message="No labs match these filters.">
				<template #action>
					<Button variant="subtle" data-test="clear-filters" @click="clearFilters">
						Clear filters
					</Button>
				</template>
			</EmptyState>
		</SectionCard>
	</div>
</template>

<script setup>
import AppIcon from "@/components/AppIcon.vue";
import DataTable from "@/components/DataTable.vue";
import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import OnboardingPanel from "@/components/overview/OnboardingPanel.vue";
import { labsResource } from "@/data/labs";
import { userContext } from "@/data/userContext";
import { labelFor as appLabel } from "@/utils/appIcons";
import { benchLabel } from "@/utils/labSpecs";
import { Button, FormControl, Select, dayjsLocal } from "frappe-ui";
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import PlusIcon from "~icons/lucide/plus";
import SearchIcon from "~icons/lucide/search";

// Memory and CPU are deliberately absent — they belong on the detail header.
// These six columns answer what the old table omitted: is this lab deployed,
// where is its site, and when did it last run.
//
// Every width is fixed rather than fractional: ListView lays its grid out
// inside a `w-max` container, where an `fr` track resolves to max-content and
// one long site name pushes the last column off the card at any viewport.
const COLUMNS = [
	{ label: "Lab", key: "lab", width: "240px" },
	{ label: "Version", key: "frappe_version", width: "96px" },
	{ label: "Apps", key: "apps", width: "140px" },
	{ label: "Status", key: "status", width: "112px" },
	{ label: "Deployed as", key: "deployed_as", width: "190px" },
	{ label: "Last run", key: "last_run", width: "96px" },
];

const ALL = "__all__";

const router = useRouter();
const search = ref("");
const statusFilter = ref(ALL);
const versionFilter = ref(ALL);
const ownerFilter = ref(ALL);

// `get_labs` returns every lab the caller may see in one bounded response, so
// filtering here has no hidden page ceiling behind it.
onMounted(() => labsResource.reload());

const labs = computed(() => labsResource.data ?? []);

const statusOptions = computed(() =>
	optionsFrom(
		"Status",
		labs.value.map((lab) => lab.status)
	)
);
const versionOptions = computed(() =>
	optionsFrom(
		"Version",
		labs.value.map((lab) => lab.frappe_version)
	)
);
const ownerOptions = computed(() =>
	optionsFrom(
		"Owner",
		labs.value.map((lab) => lab.owner)
	)
);

/** "All" plus each value actually present, so no filter offers an empty result. */
function optionsFrom(label, values) {
	const present = [...new Set(values.filter(Boolean))].sort();
	return [
		{ label: `${label}: all`, value: ALL },
		...present.map((value) => ({ label: value, value })),
	];
}

const rows = computed(() =>
	labs.value.filter(
		(lab) =>
			matches(lab.status, statusFilter.value) &&
			matches(lab.frappe_version, versionFilter.value) &&
			matches(lab.owner, ownerFilter.value) &&
			matchesSearch(lab)
	)
);

function matches(value, filter) {
	return filter === ALL || value === filter;
}

function matchesSearch(lab) {
	const query = search.value.trim().toLowerCase();
	if (!query) return true;
	const haystack = [lab.lab_id, lab.title, lab.description, ...(lab.app_names ?? [])];
	return haystack.some((value) => (value || "").toLowerCase().includes(query));
}

function clearFilters() {
	search.value = "";
	statusFilter.value = ALL;
	versionFilter.value = ALL;
	ownerFilter.value = ALL;
}

/** The mark a lab wears — its first non-Frappe app, else the Frappe mark. */
function primaryApp(lab) {
	return (lab.app_names ?? []).find((app) => app.toLowerCase() !== "frappe") || "frappe";
}

function lastRun(lab) {
	return lab.last_run ? dayjsLocal(lab.last_run).fromNow() : "—";
}

function labRoute(lab) {
	return { name: "LabDetail", params: { labId: lab.name } };
}
</script>
