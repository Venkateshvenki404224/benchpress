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
					<SearchFilterBar
						v-if="labs.length"
						v-model="search"
						v-model:selected="selected"
						:controls="controls"
						search-placeholder="Search labs"
						search-test-id="labs-search"
					/>

					<p
						v-if="labsResource.loading && !labs.length"
						class="text-body text-ink-gray-5"
					>
						Loading labs…
					</p>

					<OnboardingPanel v-else-if="!labs.length" />

					<div
						v-else-if="rows.length"
						class="grid gap-3.5"
						style="
							grid-template-columns: repeat(
								auto-fill,
								minmax(min(300px, 100%), 1fr)
							);
						"
						data-test="labs-grid"
					>
						<RecipeCard
							v-for="lab in rows"
							:key="lab.name"
							class="cursor-pointer"
							:title="lab.title || lab.lab_id"
							:subtitle="`${lab.lab_id} · ${lab.frappe_version}`"
							:logo="lab.logo || ''"
							:description="lab.description || ''"
							:apps="lab.app_names"
							:chips="resourceChips(lab)"
							:data-test="`lab-card-${lab.name}`"
							@click="openLab(lab)"
						>
							<!-- A deployed lab's card answers "what is it doing now": the running
							     instance's state outranks the image's Ready. Undeployed labs keep
							     showing the image lifecycle (Draft/Building/Ready/Error). -->
							<template #badge>
								<StatusBadge :status="lab.deployed_as?.status || lab.status" />
							</template>
							<template #footer>
								<div class="min-w-0 flex-1">
									<template v-if="lab.deployed_as">
										<span class="block truncate text-meta text-ink-gray-6">
											{{ lab.deployed_as.site || "No site yet" }}
										</span>
										<LeaseCountdown
											:expires-at-ts="lab.deployed_as.expires_at_ts"
										/>
									</template>
									<span v-else class="block truncate text-meta text-ink-gray-4">
										Never deployed
									</span>
									<span
										v-if="lab.last_run"
										class="block truncate text-2xs text-ink-gray-4"
									>
										Last run {{ dayjsLocal(lab.last_run).fromNow() }}
									</span>
								</div>
								<Button
									class="flex-none"
									variant="solid"
									:data-test="`lab-open-${lab.name}`"
									@click.stop="openLab(lab)"
								>
									Open lab
								</Button>
							</template>
						</RecipeCard>
					</div>

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
import EmptyState from "@/components/EmptyState.vue";
import SearchFilterBar from "@/components/SearchFilterBar.vue";
import SectionCard from "@/components/SectionCard.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import LeaseCountdown from "@/components/lab/LeaseCountdown.vue";
import RecipeCard from "@/components/lab/RecipeCard.vue";
import TemplateCatalog from "@/components/lab/TemplateCatalog.vue";
import OnboardingPanel from "@/components/overview/OnboardingPanel.vue";
import { useSearchFilters } from "@/composables/useSearchFilters";
import { labsResource } from "@/data/labs";
import { userContext } from "@/data/userContext";
import { resourceChips } from "@/utils/labSpecs";
import { Button, Tabs, dayjsLocal } from "frappe-ui";
import { computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";

import PlusIcon from "~icons/lucide/plus";

const TABS = [
	{ key: "labs", label: "My labs", route: "/labs" },
	{ key: "templates", label: "Templates", route: "/labs/templates" },
];

const LAB_FILTERS = [
	{ key: "status", label: "Status", value: (lab) => lab.status, testId: "filter-status" },
	{
		key: "version",
		label: "Version",
		value: (lab) => lab.frappe_version,
		testId: "filter-version",
	},
	{
		key: "owner",
		label: "Owner",
		value: (lab) => lab.owner,
		testId: "filter-owner",
		class: "max-w-full overflow-hidden",
	},
];

const router = useRouter();
const route = useRoute();
const activeTab = computed(() => (route.name === "LabTemplates" ? 1 : 0));

// `get_labs` returns every lab the caller may see in one bounded response, so
// filtering here has no hidden page ceiling behind it.
onMounted(() => labsResource.reload());

const labs = computed(() => labsResource.data ?? []);

const { search, selected, controls, rows, clearFilters } = useSearchFilters(labs, {
	searchIn: (lab) => [lab.lab_id, lab.title, lab.description, ...(lab.app_names ?? [])],
	filters: LAB_FILTERS,
});

function openLab(lab) {
	router.push({ name: "LabDetail", params: { labId: lab.name } });
}
</script>
