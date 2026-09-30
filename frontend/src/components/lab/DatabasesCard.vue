<template>
	<SectionCard title="Databases" :padded="false" data-test="databases-card">
		<template #action>
			<span class="text-2xs tabular-nums text-ink-gray-5" data-test="databases-left">
				{{ leftLabel }}
			</span>
			<Tooltip text="Create database">
				<Button
					variant="solid"
					size="sm"
					aria-label="Create database"
					:disabled="!left"
					:loading="createAction.loading"
					data-test="create-database"
					@click="createDatabase"
				>
					<template #icon><PlusIcon class="size-3.5" /></template>
				</Button>
			</Tooltip>
		</template>

		<p class="border-b border-outline-gray-1 px-4 py-2.5 text-2xs text-ink-gray-5">
			Each database has its own user, which can reach that database only. Paste the command
			over SSH to create a site on it.
		</p>

		<ErrorMessage class="px-4 pt-2.5" :message="error" />

		<ul v-if="databases.length" class="divide-y divide-outline-gray-1">
			<li
				v-for="database in databases"
				:key="database.db_name"
				:data-test="`database-${database.db_name}`"
			>
				<button
					type="button"
					class="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface-gray-1"
					:aria-expanded="open === database.db_name"
					:data-test="`toggle-${database.db_name}`"
					@click="toggle(database.db_name)"
				>
					<span class="min-w-0 flex-1 truncate font-mono text-xs text-ink-gray-9">
						{{ database.db_name }}
					</span>
					<ChevronRightIcon
						class="size-3.5 flex-none text-ink-gray-5 transition-transform duration-150"
						:class="open === database.db_name ? 'rotate-90' : ''"
					/>
				</button>

				<div
					v-if="open === database.db_name"
					class="flex flex-col gap-2 px-4 pb-3"
					:data-test="`panel-${database.db_name}`"
				>
					<div class="flex items-center gap-2">
						<span class="w-20 flex-none text-meta text-ink-gray-7">User</span>
						<code
							class="min-w-0 flex-1 break-all rounded bg-surface-gray-1 px-2.5 py-1.5 font-mono text-2xs text-ink-gray-8"
							data-test="database-user"
						>
							{{ database.db_user }}
						</code>
						<CopyButton label="user" :value="database.db_user" />
					</div>
					<template v-if="shown?.db_name === database.db_name">
						<div class="flex items-center gap-2">
							<span class="w-20 flex-none text-meta text-ink-gray-7">Password</span>
							<code
								class="min-w-0 flex-1 break-all rounded bg-surface-gray-1 px-2.5 py-1.5 font-mono text-2xs text-ink-gray-8"
								data-test="database-password"
							>
								{{ shown.db_password }}
							</code>
							<CopyButton label="password" :value="shown.db_password" />
						</div>
						<div class="flex items-start gap-2">
							<code
								class="min-w-0 flex-1 whitespace-pre-wrap break-all rounded bg-surface-gray-1 px-2.5 py-1.5 font-mono text-2xs text-ink-gray-8"
								data-test="database-command"
							>
								{{ shown.command }}
							</code>
							<CopyButton label="command" :value="shown.command" />
						</div>
					</template>
					<div class="flex justify-end">
						<Button
							variant="subtle"
							theme="red"
							size="sm"
							:loading="deletingName === database.db_name"
							:data-test="`delete-${database.db_name}`"
							@click="askToDelete(database.db_name)"
						>
							<template #prefix><Trash2Icon class="size-3.5" /></template>
							Delete database
						</Button>
					</div>
				</div>
			</li>
		</ul>

		<EmptyState v-else message="No database yet. Create one, then make a site on it." />

		<Dialog
			v-if="confirming"
			:model-value="true"
			:options="{ title: 'Delete this database?' }"
			@update:model-value="confirming = ''"
		>
			<template #body-content>
				<p class="text-p-base text-ink-gray-6" data-test="delete-database-message">
					BenchPress drops
					<span class="break-all font-mono text-sm">{{ confirming }}</span>
					and its user. A site on this database stops working. BenchPress cannot bring
					the database back.
				</p>
			</template>
			<template #actions>
				<div class="flex justify-end gap-2">
					<Button data-test="cancel-delete-database" @click="confirming = ''">
						Cancel
					</Button>
					<Button
						variant="solid"
						theme="red"
						data-test="confirm-delete-database"
						@click="confirmDelete"
					>
						Delete
					</Button>
				</div>
			</template>
		</Dialog>
	</SectionCard>
</template>

<script setup>
import CopyButton from "@/components/CopyButton.vue";
import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";
import { Button, Dialog, ErrorMessage, Tooltip, createResource } from "frappe-ui";
import { computed, ref } from "vue";

import ChevronRightIcon from "~icons/lucide/chevron-right";
import PlusIcon from "~icons/lucide/plus";
import Trash2Icon from "~icons/lucide/trash-2";

const props = defineProps({
	bench: { type: Object, required: true },
});

const emit = defineEmits(["created", "deleted"]);

const createAction = createResource({ url: "benchpress.api.create_bench_database" });
const revealAction = createResource({ url: "benchpress.api.get_bench_database_password" });
const deleteAction = createResource({ url: "benchpress.api.delete_bench_database" });

const open = ref("");
const shown = ref(null);
const confirming = ref("");
const dropped = ref([]);

const databases = computed(() => {
	const listed = (props.bench.databases ?? []).filter(
		(database) => !dropped.value.includes(database.db_name)
	);
	const latest = shown.value;
	if (!latest || listed.some((database) => database.db_name === latest.db_name)) return listed;
	return [...listed, { db_name: latest.db_name, db_user: latest.db_user }];
});

const error = computed(() => createAction.error || revealAction.error || deleteAction.error);
const deletingName = computed(() => (deleteAction.loading ? deleteAction.params?.db_name : ""));

const limit = computed(() => props.bench.database_limit);
const left = computed(() => Math.max(0, limit.value - databases.value.length));
const leftLabel = computed(() =>
	left.value ? `${left.value} of ${limit.value} left` : "No databases left"
);

async function createDatabase() {
	try {
		shown.value = await createAction.submit({ bench: props.bench.name });
	} catch {
		return;
	}
	open.value = shown.value.db_name;
	emit("created");
}

async function toggle(dbName) {
	if (open.value === dbName) {
		open.value = "";
		return;
	}
	open.value = dbName;
	if (shown.value?.db_name === dbName) return;
	const secret = await revealAction
		.submit({ bench: props.bench.name, db_name: dbName })
		.catch(() => null);
	if (secret && open.value === dbName) shown.value = { db_name: dbName, ...secret };
}

function askToDelete(dbName) {
	deleteAction.reset();
	confirming.value = dbName;
}

async function confirmDelete() {
	const dbName = confirming.value;
	confirming.value = "";
	try {
		await deleteAction.submit({ bench: props.bench.name, db_name: dbName });
	} catch {
		return;
	}
	dropped.value = [...dropped.value, dbName];
	if (shown.value?.db_name === dbName) shown.value = null;
	if (open.value === dbName) open.value = "";
	emit("deleted");
}
</script>
