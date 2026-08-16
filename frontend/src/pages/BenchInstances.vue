<template>
	<div class="mx-auto max-w-[1180px] px-6 pb-10 pt-[22px]" data-test="instances">
		<div class="mb-3.5 flex flex-wrap items-start gap-3">
			<div>
				<h1 class="text-title font-semibold text-ink-gray-9">Instances</h1>
				<p class="mt-0.5 text-body text-ink-gray-5" data-test="instances-scope">
					{{ scopeLine }}
				</p>
			</div>
			<Button
				class="ml-auto"
				variant="subtle"
				data-test="deploy-history"
				@click="router.push('/deploy-logs')"
			>
				<template #prefix><ListIcon class="size-3.5" /></template>
				Deploy history
			</Button>
		</div>

		<p v-if="benchesResource.loading && !benches.length" class="text-body text-ink-gray-5">
			Loading instances…
		</p>

		<DataTable
			v-else-if="benches.length"
			:columns="COLUMNS"
			:rows="benches"
			:row-route="benchRoute"
			data-test="instances-table"
		>
			<template #cell="{ column, row }">
				<div v-if="column.key === 'bench'" class="flex min-w-0 items-center gap-2.5">
					<span
						class="grid size-7 flex-none place-items-center rounded-md border border-outline-gray-1 bg-surface-white"
					>
						<AppIcon :app="primaryApp(row)" :size="17" />
					</span>
					<span class="min-w-0" :data-test="`bench-${row.name}`">
						<span class="block truncate text-body font-medium text-ink-gray-9">
							{{ benchLabel(row.lab) }}
						</span>
						<span class="block truncate font-mono text-2xs text-ink-gray-4">
							{{ row.wg_ip || row.container_ip || "no address" }}
						</span>
					</span>
				</div>

				<StatusBadge v-else-if="column.key === 'status'" :status="row.status" />

				<!-- The second axis. A Running bench can be Unhealthy, and a bench
				     that has never been polled carries an empty string — which
				     StatusBadge reads as Unknown rather than a blank pill. -->
				<StatusBadge
					v-else-if="column.key === 'container_health'"
					:status="row.container_health"
				/>

				<UsageBar v-else-if="column.key === 'usage'" :usage="usageOf(row)" />

				<span v-else-if="column.key === 'site'" class="truncate text-xs text-ink-blue-3">
					{{ row.domain || row.site_name || "—" }}
				</span>

				<span
					v-else-if="column.key === 'owner'"
					class="truncate text-meta text-ink-gray-5"
				>
					{{ row.owner }}
				</span>
			</template>
		</DataTable>

		<SectionCard v-else :padded="false">
			<EmptyState
				message="No instances yet — deploying a lab builds one, with its own site, SSH user and IDE."
			>
				<template #action>
					<Button variant="solid" @click="router.push('/labs/templates')">
						Start from a template
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
import UsageBar from "@/components/UsageBar.vue";
import { BENCH_PAGE_LENGTH, benchesResource } from "@/data/benches";
import { labsResource } from "@/data/labs";
import { userContext } from "@/data/userContext";
import { usageFor } from "@/utils/benchUsage";
import { benchLabel } from "@/utils/labSpecs";
import { Button, dayjsLocal } from "frappe-ui";
import { computed, onMounted } from "vue";
import { useRouter } from "vue-router";

import ListIcon from "~icons/lucide/list";

// Fixed widths for the same reason as the Labs table: ListView's grid sits in
// a `w-max` container, so a fractional track sizes to its longest cell.
const COLUMNS = [
	{ label: "Bench", key: "bench", width: "240px" },
	{ label: "Status", key: "status", width: "110px" },
	{ label: "Health", key: "container_health", width: "104px" },
	{ label: "CPU / memory", key: "usage", width: "150px" },
	{ label: "Site", key: "site", width: "170px" },
	{ label: "Owner", key: "owner", width: "100px" },
];

const router = useRouter();

onMounted(() => benchesResource.reload());

const benches = computed(() => benchesResource.data ?? []);

// The list is row-scoped on the server, so an empty table means two very
// different things depending on the role. Say which, rather than leaving the
// user to guess whether the list is empty or filtered.
const scopeLine = computed(() => {
	const scope = userContext.isAdmin
		? "Every container on this server, across all owners."
		: "Containers you own. Ask an admin if you need access to another.";
	return benchesResource.hasNextPage
		? `${scope} Showing the first ${BENCH_PAGE_LENGTH}.`
		: scope;
});

/** The lab's first non-Frappe app decides the mark this bench wears. */
function primaryApp(bench) {
	const lab = (labsResource.data ?? []).find((row) => row.name === bench.lab);
	return (lab?.app_names ?? []).find((app) => app.toLowerCase() !== "frappe") || "frappe";
}

function usageOf(bench) {
	return usageFor(bench, readingAgeSeconds(bench.last_health_check));
}

/** Seconds since the stats sweep last wrote, or null if it never has. */
function readingAgeSeconds(lastHealthCheck) {
	if (!lastHealthCheck) return null;
	return Math.max(0, dayjsLocal().diff(dayjsLocal(lastHealthCheck), "second"));
}

function benchRoute(bench) {
	return { name: "LabDetail", params: { labId: bench.lab } };
}
</script>
