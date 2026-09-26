<template>
	<div class="page-shell" data-test="benches">
		<div class="mb-4">
			<h1 class="text-title font-semibold text-ink-gray-9">Benches</h1>
			<p class="mt-0.5 max-w-[600px] text-body text-ink-gray-5">
				A Frappe bench you manage like your own machine: SSH, root, code-server. No site
				until you make one.
			</p>
		</div>

		<SectionCard class="mb-4" title="Your SSH keys" data-test="ssh-keys">
			<p class="mb-2 text-xs text-ink-gray-6">
				Paste the contents of <code class="font-mono">~/.ssh/id_ed25519.pub</code>. One key
				per line. A new key reaches a bench on its next deploy.
			</p>
			<textarea
				v-model="keysDraft"
				rows="3"
				spellcheck="false"
				class="block w-full resize-y rounded border border-outline-gray-2 bg-surface-white px-2 py-1.5 font-mono text-xs text-ink-gray-8 focus:border-outline-gray-4 focus:ring-0"
				placeholder="ssh-ed25519 AAAA… you@laptop"
				aria-label="SSH public keys"
				data-test="ssh-keys-input"
			/>
			<ErrorMessage class="mt-2" :message="saveKeys.error" />
			<div class="mt-2.5 flex items-center gap-2">
				<span class="min-w-0 text-meta text-ink-gray-4">
					{{ hasKey ? "Saved" : "No key saved" }}
				</span>
				<Button
					class="ml-auto flex-none"
					:loading="saveKeys.loading"
					:disabled="keysDraft === savedKeys"
					data-test="save-ssh-keys"
					@click="saveSshKeys"
				>
					Save keys
				</Button>
			</div>
		</SectionCard>

		<p v-if="templates.loading && !allTemplates.length" class="text-body text-ink-gray-5">
			Loading benches…
		</p>

		<div
			v-else-if="allTemplates.length"
			class="grid gap-3.5"
			style="grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr))"
		>
			<article
				v-for="template in allTemplates"
				:key="template.key"
				class="flex flex-col rounded-card border border-outline-gray-1 bg-surface-white px-4 pb-3 pt-4"
				:data-test="`bench-template-${template.key}`"
			>
				<div class="flex items-center gap-2.5">
					<span
						class="grid size-8 flex-none place-items-center rounded-md border border-outline-gray-1 bg-surface-white"
					>
						<AppIcon app="frappe" :size="20" />
					</span>
					<div class="min-w-0 flex-1">
						<h2 class="truncate text-sm font-semibold text-ink-gray-9">
							{{ template.title }}
						</h2>
						<p class="truncate text-meta text-ink-gray-4">
							{{ template.frappe_version }}
						</p>
					</div>
				</div>

				<p class="mb-3 mt-2.5 min-h-[34px] text-xs text-ink-gray-6">
					{{ template.description }}
				</p>

				<div class="mb-3 flex flex-wrap items-center gap-1.5">
					<span
						v-for="chip in resourceChips(template)"
						:key="chip"
						class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-2xs text-ink-gray-6"
					>
						{{ chip }}
					</span>
				</div>

				<div class="mt-auto flex items-center gap-2 border-t border-outline-gray-1 pt-2.5">
					<span v-if="!hasKey" class="min-w-0 text-meta text-ink-gray-6">
						Add an SSH key first
					</span>
					<span v-else class="min-w-0 text-meta text-ink-gray-4">
						{{
							template.image_ready
								? "About a minute"
								: "First launch builds, about 30 minutes"
						}}
					</span>
					<Button
						class="ml-auto flex-none"
						variant="solid"
						:loading="pendingKey === template.key"
						:disabled="Boolean(pendingKey) || !hasKey"
						:data-test="`prepare-bench-${template.key}`"
						@click="prepareBench(template)"
					>
						Prepare bench
					</Button>
				</div>
			</article>
		</div>

		<SectionCard v-else :padded="false">
			<EmptyState message="No bench templates are available yet." />
		</SectionCard>

		<ErrorMessage class="mt-3" :message="launchAction.error" />

		<section class="mt-6" data-test="my-benches">
			<h2 class="mb-2.5 text-sm font-semibold text-ink-gray-9">Your benches</h2>
			<DataTable
				v-if="myBenches.length"
				:columns="COLUMNS"
				:rows="myBenches"
				:row-route="(row) => `/labs/${row.lab}`"
				data-test="my-benches-table"
			>
				<template #cell="{ column, row }">
					<span v-if="column.key === 'bench'" class="min-w-0">
						<span class="block truncate text-body font-medium text-ink-gray-9">
							{{ benchLabel(row.lab) }}
						</span>
						<span class="block truncate font-mono text-2xs text-ink-gray-4">
							{{ row.wg_ip || "no address" }}
						</span>
					</span>
					<StatusBadge v-else-if="column.key === 'status'" :status="row.status" />
					<span v-else-if="column.key === 'age'" class="text-meta text-ink-gray-5">
						{{ dayjsLocal(row.creation).fromNow() }}
					</span>
				</template>
			</DataTable>
			<SectionCard v-else :padded="false">
				<EmptyState message="No benches yet. Prepare one from a card above." />
			</SectionCard>
		</section>
	</div>
</template>

<script setup>
import AppIcon from "@/components/AppIcon.vue";
import DataTable from "@/components/DataTable.vue";
import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { openDeployRun } from "@/data/deployRun";
import { labsResource } from "@/data/labs";
import { benchLabel, cpuLabel, memoryLabel } from "@/utils/labSpecs";
import { Button, ErrorMessage, createResource, dayjsLocal, toast } from "frappe-ui";
import { computed, ref, watch } from "vue";

const COLUMNS = [
	{ label: "Bench", key: "bench", width: "240px" },
	{ label: "Status", key: "status", width: "110px" },
	{ label: "Age", key: "age", width: "120px" },
];

const pendingKey = ref("");

const templates = createResource({ url: "benchpress.api.get_bench_templates", auto: true });
const benches = createResource({ url: "benchpress.api.get_my_benches", auto: true });
const launchAction = createResource({ url: "benchpress.api.launch_template" });

const keys = createResource({ url: "benchpress.user.get_ssh_keys", auto: true });
const saveKeys = createResource({ url: "benchpress.user.set_ssh_keys" });

const allTemplates = computed(() => templates.data ?? []);
const myBenches = computed(() => benches.data ?? []);
const savedKeys = computed(() => keys.data ?? "");
const hasKey = computed(() => Boolean(savedKeys.value.trim()));
const keysDraft = ref("");

watch(savedKeys, (value) => (keysDraft.value = value), { immediate: true });

async function saveSshKeys() {
	try {
		keys.setData(await saveKeys.submit({ keys: keysDraft.value }));
	} catch {
		return;
	}
	toast.success("SSH keys saved.");
}

function resourceChips(template) {
	return [memoryLabel(template.memory_limit), cpuLabel(template.cpu_cores)];
}

async function prepareBench(template) {
	pendingKey.value = template.key;
	try {
		const run = await launchAction.submit({ template: template.key });
		if (launchAction.error || !run?.bench) return;
		labsResource.reload();
		templates.reload();
		benches.reload();

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
