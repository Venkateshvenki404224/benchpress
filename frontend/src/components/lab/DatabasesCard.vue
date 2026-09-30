<template>
	<SectionCard title="Databases" :padded="false" data-test="databases-card">
		<template #action>
			<span class="text-2xs tabular-nums text-ink-gray-5" data-test="databases-left">
				{{ left }} of {{ limit }} left
			</span>
			<Button
				variant="solid"
				size="sm"
				:loading="createAction.loading"
				data-test="create-database"
				@click="createDatabase"
			>
				Create database
			</Button>
		</template>

		<p class="border-b border-outline-gray-1 px-4 py-2.5 text-2xs text-ink-gray-5">
			Each database has its own user, which can reach that database only. Paste the command
			over SSH to create a site on it.
		</p>

		<ErrorMessage class="px-4 pt-2.5" :message="createAction.error || revealAction.error" />

		<ul v-if="databases.length" class="divide-y divide-outline-gray-1">
			<li
				v-for="database in databases"
				:key="database.db_name"
				class="px-4 py-3"
				:data-test="`database-${database.db_name}`"
			>
				<div class="flex items-center gap-3">
					<div class="min-w-0 flex-1">
						<p class="truncate font-mono text-xs text-ink-gray-9">
							{{ database.db_name }}
						</p>
						<p class="truncate text-2xs text-ink-gray-5">
							User {{ database.db_user }}
						</p>
					</div>
					<Button
						v-if="shown?.db_name !== database.db_name"
						variant="subtle"
						size="sm"
						:loading="revealing === database.db_name"
						:data-test="`show-${database.db_name}`"
						@click="reveal(database.db_name)"
					>
						Show password
					</Button>
				</div>

				<div v-if="shown?.db_name === database.db_name" class="mt-2.5 flex flex-col gap-2">
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
				</div>
			</li>
		</ul>

		<EmptyState v-else message="No database yet. Create one, then make a site on it." />
	</SectionCard>
</template>

<script setup>
import CopyButton from "@/components/CopyButton.vue";
import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";
import { Button, ErrorMessage, createResource } from "frappe-ui";
import { computed, ref } from "vue";

const props = defineProps({
	bench: { type: Object, required: true },
});

const emit = defineEmits(["created"]);

const createAction = createResource({ url: "benchpress.api.create_bench_database" });
const revealAction = createResource({ url: "benchpress.api.get_bench_database_password" });

const shown = ref(null);
const revealing = ref("");

const databases = computed(() => {
	const listed = props.bench.databases ?? [];
	const latest = shown.value;
	if (!latest || listed.some((database) => database.db_name === latest.db_name)) return listed;
	return [...listed, { db_name: latest.db_name, db_user: latest.db_user }];
});

const limit = computed(() => props.bench.database_limit);
const left = computed(() => Math.max(0, limit.value - databases.value.length));

async function createDatabase() {
	try {
		shown.value = await createAction.submit({ bench: props.bench.name });
	} catch {
		return;
	}
	emit("created");
}

async function reveal(dbName) {
	revealing.value = dbName;
	const secret = await revealAction
		.submit({ bench: props.bench.name, db_name: dbName })
		.catch(() => null);
	revealing.value = "";
	if (secret) shown.value = { db_name: dbName, ...secret };
}
</script>
