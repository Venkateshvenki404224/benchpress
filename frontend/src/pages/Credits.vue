<template>
	<div class="page-shell" data-test="credits">
		<div class="mb-3.5">
			<h1 class="text-title font-semibold text-ink-gray-9">Credits</h1>
			<p class="mt-0.5 max-w-[620px] text-body text-ink-gray-5">
				Two things cost credits: the lease an instance runs on, and a custom image build
				that nobody has built before. Sites, devices and failed builds are free.
			</p>
		</div>

		<div class="mb-3 grid gap-3 sm:grid-cols-2">
			<StatTile
				label="Balance"
				:value="meter.balanceLabel"
				:note="`of ${meter.allocatedLabel} allocated`"
			/>
			<StatTile label="Entries" :value="String(total)" />
		</div>

		<div class="mb-3">
			<CreditPacks @bought="reload" />
		</div>

		<p v-if="loading && !rows.length" class="text-body text-ink-gray-5">Loading statement…</p>

		<DataTable
			v-else-if="rows.length"
			:columns="COLUMNS"
			:rows="rows"
			data-test="credits-table"
		>
			<template #cell="{ column, row }">
				<span v-if="column.key === 'entry_type'" class="truncate text-xs text-ink-gray-7">
					{{ row.entry_type }}
				</span>

				<span
					v-else-if="column.key === 'credits'"
					class="truncate text-body font-medium tabular-nums"
					:class="amountTone(row)"
				>
					{{ signedCreditLabel(row.credits) }}
				</span>

				<span
					v-else-if="column.key === 'balance_after'"
					class="truncate text-xs tabular-nums text-ink-gray-6"
				>
					{{ creditLabel(row.balance_after) }}
				</span>

				<span
					v-else-if="column.key === 'description'"
					class="truncate text-xs text-ink-gray-6"
				>
					{{ row.description || EM_DASH }}
				</span>

				<span v-else-if="column.key === 'when'" class="truncate text-meta text-ink-gray-5">
					{{ whenLabel(row) }}
				</span>
			</template>
		</DataTable>

		<SectionCard v-else :padded="false">
			<EmptyState message="Nothing has been charged yet." />
		</SectionCard>

		<div v-if="pages > 1" class="mt-2.5 flex items-center gap-2" data-test="credits-pager">
			<Button variant="subtle" :disabled="page === 0" @click="turn(-1)">Newer</Button>
			<Button variant="subtle" :disabled="page >= pages - 1" @click="turn(1)">Older</Button>
			<span class="text-2xs text-ink-gray-5">Page {{ page + 1 }} of {{ pages }}</span>
		</div>
	</div>
</template>

<script setup>
// The statement paginates the ledger on its `(account, creation)` index and never
// sums it: `balance_after` is stored on every row, and the headline balance comes
// from the account. A page is one indexed range scan however long the ledger is.
import DataTable from "@/components/DataTable.vue";
import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";
import StatTile from "@/components/StatTile.vue";
import CreditPacks from "@/components/credit/CreditPacks.vue";
import {
	creditStatementResource,
	creditSummary,
	loadStatement,
	primeCreditSummary,
	refreshCreditSummary,
} from "@/data/credits";
import { creditLabel, creditMeter, signedCreditLabel } from "@/utils/credits";
import { Button, dayjsLocal } from "frappe-ui";
import { computed, onMounted, ref } from "vue";

const EM_DASH = "—";
const PAGE_LENGTH = 20;

const COLUMNS = [
	{ label: "Type", key: "entry_type", width: "110px" },
	{ label: "Credits", key: "credits", width: "110px" },
	{ label: "Balance after", key: "balance_after", width: "120px" },
	{ label: "What happened", key: "description", width: "320px" },
	{ label: "When", key: "when", width: "110px" },
];

const page = ref(0);

onMounted(() => {
	primeCreditSummary();
	loadStatement(0, PAGE_LENGTH);
});

const statement = computed(() => creditStatementResource.data ?? {});
const rows = computed(() => statement.value.rows ?? []);
const total = computed(() => statement.value.total ?? 0);
const loading = computed(() => creditStatementResource.loading);
const pages = computed(() => Math.max(Math.ceil(total.value / PAGE_LENGTH), 1));
// The same figures the sidebar gauge reads, so the page it opens cannot disagree with it.
const meter = computed(() => creditMeter(creditSummary.balance, creditSummary.allocated));

function turn(direction) {
	page.value = Math.min(Math.max(page.value + direction, 0), pages.value - 1);
	loadStatement(page.value * PAGE_LENGTH, PAGE_LENGTH);
}

/** After a purchase the balance and the statement have both changed; re-read both from the server. */
function reload() {
	refreshCreditSummary();
	loadStatement(page.value * PAGE_LENGTH, PAGE_LENGTH);
}

/** Green adds, plain spends. A zero row — a session starting — is not an event to colour. */
function amountTone(row) {
	if (Number(row.credits) > 0) return "text-ink-green-3";
	if (Number(row.credits) < 0) return "text-ink-gray-9";
	return "text-ink-gray-5";
}

function whenLabel(row) {
	return row.creation ? dayjsLocal(row.creation).fromNow() : EM_DASH;
}
</script>
