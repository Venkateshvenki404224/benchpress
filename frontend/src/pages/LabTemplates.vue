<template>
	<div class="page-shell" data-test="templates">
		<div class="mb-4">
			<h1 class="text-title font-semibold text-ink-gray-9">Templates</h1>
			<p class="mt-0.5 max-w-[600px] text-body text-ink-gray-5">
				Ready-made recipes. Pick one and BenchPress creates the lab for you — no form to
				fill in.
			</p>
		</div>

		<div v-if="allTemplates.length" class="mb-3 flex flex-wrap items-center gap-2">
			<FormControl
				class="w-[240px]"
				type="text"
				placeholder="Search templates"
				v-model="search"
				data-test="templates-search"
			>
				<template #prefix><SearchIcon class="size-3.5 text-ink-gray-4" /></template>
			</FormControl>
			<Select v-model="appsFilter" :options="appOptions" data-test="filter-apps" />
			<Select v-model="versionFilter" :options="versionOptions" data-test="filter-version" />
		</div>

		<p v-if="templates.loading && !allTemplates.length" class="text-body text-ink-gray-5">
			Loading templates…
		</p>

		<div
			v-else-if="rows.length"
			class="grid gap-3.5"
			style="grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr))"
		>
			<RecipeCard
				v-for="template in rows"
				:key="template.key"
				:title="template.title"
				:subtitle="template.frappe_version"
				:logo="template.logo || ''"
				:description="template.description || ''"
				:apps="templateApps(template)"
				:chips="resourceChips(template)"
				:data-test="`template-${template.key}`"
			>
				<template #badge>
					<Badge
						v-if="template.most_used"
						theme="green"
						variant="subtle"
						size="sm"
						label="Most used"
						data-test="most-used"
					/>
				</template>
				<template #footer>
					<span
						class="min-w-0 truncate text-meta"
						:class="template.lab ? 'text-ink-gray-6' : 'text-ink-gray-4'"
						:data-test="`template-footnote-${template.key}`"
					>
						{{ footnote(template) }}
					</span>
					<Button
						v-if="template.lab"
						class="ml-auto flex-none"
						variant="solid"
						:data-test="`open-lab-${template.key}`"
						@click="router.push(`/labs/${template.lab.name}`)"
					>
						Go to lab
					</Button>
					<Button
						v-else
						class="ml-auto flex-none"
						variant="solid"
						:loading="pendingKey === template.key"
						:disabled="Boolean(pendingKey)"
						:data-test="`use-template-${template.key}`"
						@click="useTemplate(template)"
					>
						Use template
					</Button>
				</template>
			</RecipeCard>
		</div>

		<SectionCard v-else-if="allTemplates.length" :padded="false">
			<EmptyState message="No templates match these filters.">
				<template #action>
					<Button variant="subtle" data-test="clear-filters" @click="clearFilters">
						Clear filters
					</Button>
				</template>
			</EmptyState>
		</SectionCard>

		<SectionCard v-else :padded="false">
			<EmptyState
				message="The template catalog is empty — create a lab from scratch instead."
			>
				<template #action>
					<Button variant="solid" @click="router.push('/labs/new')">New lab</Button>
				</template>
			</EmptyState>
		</SectionCard>

		<ErrorMessage class="mt-3" :message="launchAction.error" />
	</div>
</template>

<script setup>
import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";
import RecipeCard from "@/components/lab/RecipeCard.vue";
import { openDeployRun } from "@/data/deployRun";
import { labsResource } from "@/data/labs";
import { labelFor as appLabel } from "@/utils/appIcons";
import { ALL, matches, optionsFrom } from "@/utils/filters";
import { etaLabel, installedApps, resourceChips } from "@/utils/labSpecs";
import {
	Badge,
	Button,
	ErrorMessage,
	FormControl,
	Select,
	createResource,
	toast,
} from "frappe-ui";
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import SearchIcon from "~icons/lucide/search";

// The catalog is `benchpress/lab_templates.py` — every entry, its apps, its
// resources, its estimate and the "Most used" flag come from there. Nothing
// about a template is restated in this file.
const router = useRouter();
const pendingKey = ref("");

const LAB_STATES = {
	Draft: "not built yet",
	Building: "building now",
	Ready: "ready",
	Error: "build failed",
};

const templates = createResource({ url: "benchpress.api.get_lab_templates", auto: true });

const allTemplates = computed(() => templates.data ?? []);

const search = ref("");
const appsFilter = ref(ALL);
const versionFilter = ref(ALL);

const appOptions = computed(() =>
	optionsFrom("Apps", allTemplates.value.flatMap(templateApps), appLabel)
);
const versionOptions = computed(() =>
	optionsFrom(
		"Version",
		allTemplates.value.map((template) => template.frappe_version)
	)
);

const rows = computed(() =>
	allTemplates.value.filter(
		(template) =>
			matches(template.frappe_version, versionFilter.value) &&
			matchesApps(template) &&
			matchesSearch(template)
	)
);

function matchesApps(template) {
	return appsFilter.value === ALL || templateApps(template).includes(appsFilter.value);
}

function matchesSearch(template) {
	const query = search.value.trim().toLowerCase();
	if (!query) return true;
	const haystack = [
		template.key,
		template.title,
		template.description,
		...templateApps(template),
	];
	return haystack.some((value) => (value || "").toLowerCase().includes(query));
}

function clearFilters() {
	search.value = "";
	appsFilter.value = ALL;
	versionFilter.value = ALL;
}

const launchAction = createResource({ url: "benchpress.api.launch_template" });

function templateApps(template) {
	return installedApps(template.apps.map((app) => app.app_name));
}

function footnote(template) {
	if (!template.lab) return etaLabel(template.eta_minutes);
	const status = template.lab.status || "";
	return `Already used — ${LAB_STATES[status] || status.toLowerCase() || "created"}`;
}

// One click is one call: the server chains the build and the deploy into a
// single job, so closing the tab cannot lose the second half.
async function useTemplate(template) {
	pendingKey.value = template.key;
	try {
		const run = await launchAction.submit({ template: template.key });
		if (launchAction.error || !run?.bench) return;
		labsResource.reload();
		// The catalog carries the lab a template has already been used for, and
		// that is what flips this card to "Go to lab" — without the reload the
		// same template can be launched a second time.
		templates.reload();

		toast.success(
			run.will_build
				? `Building ${run.lab_title} — it deploys on its own when the image is ready.`
				: `Deploying ${run.lab_title}.`
		);
		openDeployRun({
			labId: run.lab,
			labTitle: run.lab_title,
			benchName: run.bench,
			willBuild: run.will_build,
		});
	} finally {
		pendingKey.value = "";
	}
}
</script>
