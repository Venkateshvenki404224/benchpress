<template>
	<div class="p-4">
		<div class="mb-4 flex items-center justify-between">
			<h2 class="text-base font-semibold text-ink-gray-9">Sites</h2>
			<Button
				variant="solid"
				theme="gray"
				:icon-left="PlusIcon"
				:disabled="!activeBench"
				@click="open = true"
				>New Site</Button
			>
		</div>

		<ListView
			v-if="rows?.length"
			:columns="siteColumns"
			:rows="rows"
			:options="{ selectable: false, showTooltip: true, resizeColumn: true }"
			row-key="name"
		/>
		<div
			v-else-if="!activeBench"
			class="rounded-lg border border-outline-gray-1 bg-surface-white p-8 text-center"
		>
			<div class="text-sm text-ink-gray-5">Deploy this lab first to create sites.</div>
		</div>
		<div
			v-else
			class="rounded-lg border border-outline-gray-1 bg-surface-white p-8 text-center"
		>
			<div class="text-sm text-ink-gray-5">No sites yet. Create your first site.</div>
		</div>

		<Dialog :options="{ title: 'Create New Site', size: 'sm' }" v-model="open">
			<template #body-content>
				<div class="space-y-4">
					<FormControl
						label="Site Name"
						v-model="siteName"
						type="text"
						placeholder="e.g. mysite"
						:required="true"
					/>
					<div v-if="apps?.length">
						<label class="mb-2 block text-xs font-medium text-ink-gray-6"
							>Apps to Install</label
						>
						<div class="flex flex-wrap gap-2">
							<label
								v-for="app in apps"
								:key="app.app_name"
								class="flex cursor-pointer items-center gap-2 rounded border border-outline-gray-1 px-3 py-2 text-sm"
								:class="
									selectedApps.includes(app.app_name)
										? 'border-outline-blue-2 bg-surface-blue-1'
										: ''
								"
							>
								<Checkbox
									:modelValue="selectedApps.includes(app.app_name)"
									@update:modelValue="(c) => toggleApp(app.app_name, c)"
								/>
								{{ app.app_label || app.app_name }}
							</label>
						</div>
					</div>
				</div>
			</template>
			<template #actions>
				<Button
					variant="solid"
					theme="gray"
					class="w-full"
					:loading="createLoading"
					@click="submit"
					>Create Site</Button
				>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { Button, Checkbox, Dialog, FormControl, ListView } from "frappe-ui";
import PlusIcon from "~icons/lucide/plus";

const props = defineProps({
	rows: { type: Array, default: () => [] },
	apps: { type: Array, default: () => [] },
	activeBench: { type: Object, default: null },
	createLoading: { type: Boolean, default: false },
	modelValue: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue", "create"]);

const siteColumns = [
	{ label: "Site Name", key: "site_name", width: "200px" },
	{ label: "Domain", key: "full_domain", width: "250px" },
	{ label: "Status", key: "status", width: "120px" },
];

const open = computed({
	get: () => props.modelValue,
	set: (v) => emit("update:modelValue", v),
});

const siteName = ref("");
const selectedApps = ref([]);

watch(
	() => props.modelValue,
	(isOpen) => {
		if (!isOpen) {
			siteName.value = "";
			selectedApps.value = [];
		}
	}
);

function toggleApp(name, checked) {
	if (checked) {
		if (!selectedApps.value.includes(name)) selectedApps.value.push(name);
	} else {
		selectedApps.value = selectedApps.value.filter((n) => n !== name);
	}
}

function submit() {
	if (!siteName.value) return;
	emit("create", { siteName: siteName.value, apps: [...selectedApps.value] });
}
</script>
