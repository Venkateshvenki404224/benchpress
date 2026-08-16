<template>
	<div class="mx-auto max-w-[1180px] px-6 pb-10 pt-[22px]" data-test="templates">
		<div class="mb-4">
			<h1 class="text-title font-semibold text-ink-gray-9">Templates</h1>
			<p class="mt-0.5 max-w-[600px] text-body text-ink-gray-5">
				Ready-made recipes. Pick one and BenchPress creates the lab for you — no form to
				fill in.
			</p>
		</div>

		<p v-if="templates.loading && !rows.length" class="text-body text-ink-gray-5">
			Loading templates…
		</p>

		<div
			v-else-if="rows.length"
			class="grid gap-3.5"
			style="grid-template-columns: repeat(auto-fill, minmax(300px, 1fr))"
		>
			<article
				v-for="template in rows"
				:key="template.key"
				class="flex flex-col rounded-card border border-outline-gray-1 bg-surface-white px-4 pb-3 pt-4 transition-shadow duration-150 ease-out hover:shadow-card-hover"
				:data-test="`template-${template.key}`"
			>
				<div class="flex items-center gap-2.5">
					<span
						class="grid size-8 flex-none place-items-center rounded-md border border-outline-gray-1 bg-surface-white"
					>
						<AppIcon :app="markFor(template)" :size="20" />
					</span>
					<div class="min-w-0 flex-1">
						<h2 class="truncate text-sm font-semibold text-ink-gray-9">
							{{ template.title }}
						</h2>
						<p class="truncate text-meta text-ink-gray-4">
							{{ template.frappe_version }}
						</p>
					</div>
					<Badge
						v-if="template.most_used"
						theme="green"
						variant="subtle"
						size="sm"
						label="Most used"
						data-test="most-used"
					/>
				</div>

				<p class="mb-3 mt-2.5 min-h-[34px] text-xs text-ink-gray-6">
					{{ template.description }}
				</p>

				<div class="mb-3 flex flex-wrap items-center gap-1.5">
					<AppChip v-for="app in appsOf(template)" :key="app" :app="app" />
					<span
						v-for="chip in resourceChips(template)"
						:key="chip"
						class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-2xs text-ink-gray-6"
					>
						{{ chip }}
					</span>
				</div>

				<div class="mt-auto flex items-center gap-2 border-t border-outline-gray-1 pt-2.5">
					<span class="text-meta text-ink-gray-4">{{
						etaLabel(template.eta_minutes)
					}}</span>
					<Button
						class="ml-auto"
						variant="solid"
						:loading="pendingKey === template.key"
						:disabled="Boolean(pendingKey)"
						:data-test="`use-template-${template.key}`"
						@click="useTemplate(template)"
					>
						Use template
					</Button>
				</div>
			</article>
		</div>

		<SectionCard v-else :padded="false">
			<EmptyState
				message="The template catalog is empty — create a lab from scratch instead."
			>
				<template #action>
					<Button variant="solid" @click="router.push('/labs/new')">New lab</Button>
				</template>
			</EmptyState>
		</SectionCard>

		<ErrorMessage class="mt-3" :message="createAction.error || deployAction.error" />
	</div>
</template>

<script setup>
import AppChip from "@/components/AppChip.vue";
import AppIcon from "@/components/AppIcon.vue";
import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";
import { openDeployRun } from "@/data/deployRun";
import { labsResource } from "@/data/labs";
import { cpuLabel, etaLabel, memoryLabel } from "@/utils/labSpecs";
import { Badge, Button, ErrorMessage, createResource, toast } from "frappe-ui";
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

// The catalog is `benchpress/lab_templates.py` — every entry, its apps, its
// resources, its estimate and the "Most used" flag come from there. Nothing
// about a template is restated in this file.
const router = useRouter();
const pendingKey = ref("");

const templates = createResource({ url: "benchpress.api.get_lab_templates", auto: true });

const rows = computed(() => templates.data ?? []);

const createAction = createResource({ url: "benchpress.api.create_lab_from_template" });
const deployAction = createResource({ url: "benchpress.api.create_bench" });

/** Every app a template installs; a bare bench is still Frappe. */
function appsOf(template) {
	const apps = template.apps.map((app) => app.app_name);
	return apps.length ? apps : ["frappe"];
}

/** The card's mark — the first app that is not Frappe itself. */
function markFor(template) {
	return appsOf(template).find((app) => app.toLowerCase() !== "frappe") || "frappe";
}

function resourceChips(template) {
	return [memoryLabel(template.memory_limit), cpuLabel(template.cpu_cores)];
}

/**
 * The whole loop from one click: the lab is created from the template, its
 * bench is deployed, and the deploy dialog follows the run. `createResource`
 * resolves with the last successful payload even when a call fails, so each
 * step checks `error` before using its result.
 */
async function useTemplate(template) {
	pendingKey.value = template.key;
	try {
		const lab = await createAction.submit({ template: template.key });
		if (createAction.error || !lab?.name) return;
		labsResource.reload();

		const bench = await deployAction.submit({ data: JSON.stringify({ lab: lab.name }) });
		if (deployAction.error || !bench?.name) return;

		toast.success(`Deploying ${lab.name}.`);
		openDeployRun({ labId: lab.name, benchName: bench.name });
	} finally {
		pendingKey.value = "";
	}
}
</script>
