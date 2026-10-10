<template>
	<div class="page-shell" data-test="labs">
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
					variant="solid"
					data-test="new-lab"
					@click="router.push('/labs/new')"
				>
					<template #prefix><PlusIcon class="size-3.5" /></template>
					New lab
				</Button>
			</div>
		</div>

		<Tabs :model-value="activeTab" :tabs="TABS" data-test="labs-tabs">
			<template #tab-panel="{ tab }">
				<TemplateCatalog v-if="tab.key === 'templates'" class="pt-4" />
				<div v-else class="pt-4">
					<div v-if="labs.length" class="mb-3 flex flex-wrap items-center gap-2">
						<FormControl
							class="w-[240px]"
							type="text"
							placeholder="Search labs"
							v-model="search"
							data-test="labs-search"
						>
							<template #prefix
								><SearchIcon class="size-3.5 text-ink-gray-4"
							/></template>
						</FormControl>
						<Select
							v-model="statusFilter"
							:options="statusOptions"
							data-test="filter-status"
						/>
						<Select
							v-model="versionFilter"
							:options="versionOptions"
							data-test="filter-version"
						/>
						<Select
							v-model="ownerFilter"
							class="max-w-full overflow-hidden"
							:options="ownerOptions"
							data-test="filter-owner"
						/>
					</div>

					<p
						v-if="labsResource.loading && !labs.length"
						class="text-body text-ink-gray-5"
					>
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
							<div
								v-if="column.key === 'lab'"
								class="flex min-w-0 items-center gap-2.5"
							>
								<span
									class="grid size-7 flex-none place-items-center rounded-md border border-outline-gray-1 bg-surface-white"
								>
									<AppIcon :app="primaryApp(row)" :size="17" />
								</span>
								<span class="min-w-0">
									<span class="block truncate text-body font-medium text-ink-gray-9">
										{{ row.title || row.lab_id }}
									</span>
									<span class="block truncate font-mono text-2xs text-ink-gray-4">
										{{ row.lab_id }}
									</span>
								</span>
							</div>

							<span
								v-else-if="column.key === 'version'"
								class="block truncate text-meta text-ink-gray-6"
							>
								{{ row.frappe_version }}
							</span>

							<div
								v-else-if="column.key === 'apps'"
								class="flex min-w-0 flex-wrap gap-1"
							>
								<AppChip
									v-for="app in displayApps(row)"
									:key="app"
									:app="app"
								/>
							</div>

							<StatusBadge
								v-else-if="column.key === 'status'"
								:status="row.deployed_as?.status || row.status"
							/>

							<span
								v-else-if="column.key === 'deployed_as'"
								class="block truncate text-meta text-ink-gray-6"
							>
								{{ deployedAsText(row) }}
							</span>

							<span
								v-else-if="column.key === 'last_run'"
								class="block truncate text-meta text-ink-gray-5"
							>
								{{ row.last_run ? dayjsLocal(row.last_run).fromNow() : "—" }}
							</span>
						</template>
					</DataTable>

					<SectionCard v-else :padded="false">
						<EmptyState message="No labs match these filters.">
							<template #action>
								<Button
									variant="subtle"
									data-test="clear-filters"
									@click="clearFilters"
								>
									Clear filters
								</Button>
							</template>
						</EmptyState>
					</SectionCard>
				</div>
			</template>
		</Tabs>
	</div>
</template>

<script setup>
import AppChip from "@/components/AppChip.vue";
import AppIcon from "@/components/AppIcon.vue";
import DataTable from "@/components/DataTable.vue";
import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import TemplateCatalog from "@/components/lab/TemplateCatalog.vue";
import OnboardingPanel from "@/components/overview/OnboardingPanel.vue";
import { labsResource } from "@/data/labs";
import { userContext } from "@/data/userContext";
import { ALL, matches, optionsFrom } from "@/utils/filters";
import { Button, FormControl, Select, Tabs, dayjsLocal } from "frappe-ui";
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import PlusIcon from "~icons/lucide/plus";
import SearchIcon from "~icons/lucide/search";

const TABS = [
	{ key: "labs", label: "My labs", route: "/labs" },
	{ key: "templates", label: "Templates", route: "/labs/templates" },
];

// Fixed widths mirror BenchInstances.vue's pattern: ListView's grid is in a
// `w-max` container, so fractional tracks size to the longest cell.
const COLUMNS = [
	{ label: "Lab", key: "lab", width: "260px" },
	{ label: "Version", key: "version", width: "120px" },
	{ label: "Apps", key: "apps", width: "200px" },
	{ label: "Status", key: "status", width: "110px" },
	{ label: "Deployed as", key: "deployed_as", width: "200px" },
	{ label: "Last run", key: "last_run", width: "120px" },
];

const router = useRouter();
const route = useRoute();
const activeTab = computed(() => (route.name === "LabTemplates" ? 1 : 0));

const search = ref("");
const statusFilter = ref(ALL);
const versionFilter = ref(ALL);
const ownerFilter = ref(ALL);

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

const rows = computed(() =>
	labs.value.filter(
		(lab) =>
			matches(lab.status, statusFilter.value) &&
			matches(lab.frappe_version, versionFilter.value) &&
			matches(lab.owner, ownerFilter.value) &&
			matchesSearch(lab)
	)
);

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

function labRoute(lab) {
	return { name: "LabDetail", params: { labId: lab.name } };
}

/** The first non-Frappe app icon; fall back to Frappe. */
function primaryApp(lab) {
	return (lab.app_names ?? []).find((app) => app.toLowerCase() !== "frappe") || "frappe";
}

/** At most 3 app chips — beyond that the column overflows. */
function displayApps(lab) {
	const apps = lab.app_names ?? [];
	return apps.length ? apps.slice(0, 3) : ["frappe"];
}

function deployedAsText(lab) {
	if (!lab.deployed_as) return "Never deployed";
	const { site, bench } = lab.deployed_as;
	return site || bench || "—";
}
</script>
