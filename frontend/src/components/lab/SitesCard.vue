<template>
	<SectionCard title="Sites" :padded="!sites.length" data-test="sites-card">
		<template #action>
			<Button
				v-if="canCreate"
				variant="subtle"
				size="sm"
				data-test="new-site"
				@click="showDialog = true"
			>
				<template #prefix><PlusIcon class="size-3.5" /></template>
				New site
			</Button>
		</template>

		<ul v-if="sites.length" class="divide-y divide-outline-gray-1">
			<li
				v-for="site in sites"
				:key="site.name"
				class="flex flex-wrap items-center gap-3 px-4 py-3"
				:data-test="`site-${site.name}`"
			>
				<div class="min-w-0 flex-1">
					<p class="truncate text-body font-medium text-ink-gray-9">
						{{ site.full_domain || site.site_name }}
					</p>
					<div class="mt-1 flex flex-wrap gap-1">
						<AppChip v-for="app in site.apps" :key="app" :app="app" />
						<span v-if="!site.apps?.length" class="text-2xs text-ink-gray-4">
							Bare site
						</span>
					</div>
				</div>
				<StatusBadge :status="site.status" />
				<Button
					variant="subtle"
					size="sm"
					:disabled="!reachable"
					:data-test="`open-site-${site.name}`"
					@click="emit('open', site)"
				>
					{{ reachable ? "Open" : "Unreachable" }}
				</Button>
			</li>
		</ul>

		<EmptyState
			v-else
			message="No site yet — one is created automatically when this lab is deployed."
		/>

		<Dialog v-model="showDialog" :options="{ title: 'Create a site', size: 'sm' }">
			<template #body-content>
				<div class="space-y-4">
					<FormControl
						v-model="siteName"
						label="Site name"
						type="text"
						placeholder="e.g. mysite"
						data-test="site-name-input"
					/>
					<div v-if="labApps.length">
						<p class="mb-2 text-2xs font-medium text-ink-gray-6">Apps to install</p>
						<div class="flex flex-wrap gap-2">
							<label
								v-for="app in labApps"
								:key="app.app_name"
								class="flex cursor-pointer items-center gap-2 rounded-control border border-outline-gray-1 px-2.5 py-1.5 text-2xs text-ink-gray-7"
								:class="
									selectedApps.includes(app.app_name) ? 'bg-surface-gray-2' : ''
								"
							>
								<input
									v-model="selectedApps"
									type="checkbox"
									:value="app.app_name"
									:data-test="`site-app-${app.app_name}`"
								/>
								{{ app.app_label || app.app_name }}
							</label>
						</div>
					</div>
					<ErrorMessage :message="createError" />
				</div>
			</template>
			<template #actions>
				<Button
					class="w-full"
					variant="solid"
					:loading="creating"
					:disabled="!siteName.trim()"
					data-test="create-site"
					@click="submit"
				>
					Create site
				</Button>
			</template>
		</Dialog>
	</SectionCard>
</template>

<script setup>
// The sites a bench serves, and the only place one is created. A site that
// cannot be reached is never hidden — its button stays, disabled, and says
// "Unreachable" so the tunnel is the obvious suspect.
import AppChip from "@/components/AppChip.vue";
import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { Button, Dialog, ErrorMessage, FormControl } from "frappe-ui";
import { computed, ref, watch } from "vue";

import PlusIcon from "~icons/lucide/plus";

const props = defineProps({
	sites: { type: Array, default: () => [] },
	// The lab's apps, offered as the checklist when creating a site.
	labApps: { type: Array, default: () => [] },
	canCreate: { type: Boolean, default: false },
	reachable: { type: Boolean, default: false },
	creating: { type: Boolean, default: false },
	createError: { type: String, default: "" },
});

const emit = defineEmits(["create", "open"]);

const showDialog = ref(false);
const siteName = ref("");
const selectedApps = ref([]);

const created = computed(() => props.sites.length);

// The dialog closes when the create lands — the site list is what confirms it.
watch(created, () => {
	showDialog.value = false;
});

watch(showDialog, (open) => {
	if (!open) return;
	siteName.value = "";
	selectedApps.value = props.labApps.map((app) => app.app_name);
});

function submit() {
	emit("create", { siteName: siteName.value.trim(), apps: [...selectedApps.value] });
}
</script>
