<template>
	<div class="page-shell" :data-test="dataTest">
		<BackLink :to="backTo" :label="backLabel" />

		<div class="mb-3.5">
			<h1 class="text-title font-semibold text-ink-gray-9">{{ title }}</h1>
			<p class="mt-0.5 max-w-[620px] text-body text-ink-gray-5">{{ description }}</p>
		</div>

		<p v-if="loading && !rows.length" class="text-body text-ink-gray-5">Loading runs…</p>

		<DataTable
			v-else-if="rows.length"
			:columns="columns"
			:rows="rows"
			:row-route="labRoute"
			:data-test="`${dataTest}-table`"
		>
			<template #cell="{ column, row }">
				<span
					v-if="column.key === 'subject'"
					class="truncate text-body font-medium text-ink-gray-9"
					:data-test="`run-${row.name}`"
				>
					{{ row.subject }}
				</span>

				<span
					v-else-if="column.key === 'image_tag'"
					class="truncate font-mono text-2xs text-ink-gray-6"
				>
					{{ row.image_tag || EM_DASH }}
				</span>

				<StatusBadge v-else-if="column.key === 'result'" :status="row.result" />

				<span
					v-else-if="column.key === 'last_step'"
					class="truncate text-xs text-ink-gray-6"
				>
					{{ row.last_step || EM_DASH }}
				</span>

				<span
					v-else-if="column.key === 'duration'"
					class="truncate text-xs tabular-nums text-ink-gray-5"
				>
					{{ row.duration_label || EM_DASH }}
				</span>

				<span
					v-else-if="column.key === 'started'"
					class="truncate text-meta text-ink-gray-5"
				>
					{{ startedLabel(row) }}
				</span>
			</template>
		</DataTable>

		<SectionCard v-else :padded="false">
			<EmptyState :message="emptyMessage">
				<template #action>
					<Button variant="solid" data-test="empty-action" @click="router.push(backTo)">
						{{ emptyAction }}
					</Button>
				</template>
			</EmptyState>
		</SectionCard>

		<p class="mt-2.5 text-2xs text-ink-gray-5" data-test="retention-note">
			{{ retentionNote }}
		</p>
	</div>
</template>

<script setup>
// Build history and deploy history are the same table with a different subject,
// so they are one component. They were near-identical twins before this phase
// and should not become twins again.
//
// Every column that the run itself did not record renders an em-dash. A run
// that predates the pipeline's step markers has no last step and no measured
// duration, and inventing either would be worse than the gap.
import BackLink from "@/components/BackLink.vue";
import DataTable from "@/components/DataTable.vue";
import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { Button, dayjsLocal } from "frappe-ui";
import { computed } from "vue";
import { useRouter } from "vue-router";

const EM_DASH = "—";

const props = defineProps({
	title: { type: String, required: true },
	description: { type: String, required: true },
	backTo: { type: String, required: true },
	backLabel: { type: String, required: true },
	columns: { type: Array, required: true },
	rows: { type: Array, required: true },
	loading: { type: Boolean, default: false },
	emptyMessage: { type: String, required: true },
	emptyAction: { type: String, required: true },
	// Log clearing drops both doctypes on this horizon, so the table says so
	// rather than presenting itself as a complete record.
	windowDays: { type: Number, default: 7 },
	limit: { type: Number, default: 0 },
	truncated: { type: Boolean, default: false },
	dataTest: { type: String, required: true },
});

const router = useRouter();

function startedLabel(row) {
	return row.started ? dayjsLocal(row.started).fromNow() : EM_DASH;
}

/** Rows open the lab behind the run; a run whose lab is gone stays inert. */
function labRoute(row) {
	return row.lab ? { name: "LabDetail", params: { labId: row.lab } } : null;
}

const retentionNote = computed(() => {
	const retention = `Runs are kept for ${props.windowDays} days — anything older has been cleared.`;
	if (!props.truncated) return retention;
	return `Showing the ${props.limit} most recent runs. ${retention}`;
});
</script>
