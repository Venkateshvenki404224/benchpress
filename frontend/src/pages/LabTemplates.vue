<template>
	<div class="p-4">
		<div class="mb-4 flex items-center justify-between">
			<div>
				<h1 class="text-xl font-semibold text-ink-gray-9">Lab Templates</h1>
				<p class="mt-1 text-sm text-ink-gray-5">
					Spin up a ready-made stack in one click, then tweak it like any other lab.
				</p>
			</div>
			<Button appearance="minimal" @click="$router.push('/labs')">Back to Labs</Button>
		</div>

		<div
			v-if="templates.data && templates.data.length"
			class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
		>
			<div
				v-for="template in templates.data"
				:key="template.key"
				class="flex flex-col rounded-lg border border-outline-gray-1 bg-surface-white p-4"
			>
				<div class="mb-2 flex items-start justify-between gap-2">
					<h2 class="text-base font-medium text-ink-gray-8">{{ template.title }}</h2>
					<Badge theme="blue" variant="subtle" :label="template.frappe_version" />
				</div>
				<p class="mb-3 flex-1 text-sm text-ink-gray-5">{{ template.description }}</p>

				<div class="mb-3 flex flex-wrap gap-1">
					<Badge
						v-for="app in template.apps"
						:key="app.app_name"
						theme="gray"
						variant="subtle"
						:label="app.app_label || app.app_name"
					/>
					<Badge
						v-if="!template.apps.length"
						theme="gray"
						variant="subtle"
						label="Bare bench"
					/>
				</div>

				<div class="mb-4 flex items-center gap-4 text-xs text-ink-gray-5">
					<span>{{ template.memory_limit }} RAM</span>
					<span
						>{{ template.cpu_cores }}
						{{ template.cpu_cores === 1 ? "core" : "cores" }}</span
					>
				</div>

				<Button class="w-full" appearance="primary" @click="openCreate(template)">
					Use this template
				</Button>
			</div>
		</div>
		<div v-else-if="templates.loading" class="text-base text-ink-gray-5">Loading...</div>
		<div v-else class="py-12 text-center text-base text-ink-gray-5">
			No templates available.
		</div>

		<Dialog
			:options="{ title: `New lab from ${selectedTemplate?.title || 'template'}` }"
			v-model="showCreateDialog"
		>
			<template #body-content>
				<div class="space-y-4">
					<FormControl
						label="Lab ID"
						v-model="form.lab_id"
						type="text"
						placeholder="e.g. crm-lab"
						description="Lowercase letters, numbers and single '.', '_' or '-' separators"
						:required="true"
					/>
					<FormControl
						label="Title"
						v-model="form.title"
						type="text"
						:placeholder="selectedTemplate?.title"
						description="Optional — defaults to the template name"
					/>
					<ErrorMessage :message="createAction.error" />
				</div>
			</template>
			<template #actions>
				<Button
					appearance="primary"
					class="w-full"
					:loading="createAction.loading"
					@click="createFromTemplate"
				>
					Create Lab
				</Button>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import {
	Badge,
	Button,
	Dialog,
	ErrorMessage,
	FormControl,
	createResource,
	toast,
} from "frappe-ui";

const router = useRouter();

const showCreateDialog = ref(false);
const selectedTemplate = ref(null);
const form = reactive({ lab_id: "", title: "" });

const templates = createResource({
	url: "benchpress.api.get_lab_templates",
	auto: true,
});

const createAction = createResource({
	url: "benchpress.api.create_lab_from_template",
	onSuccess(data) {
		showCreateDialog.value = false;
		toast.success("Lab created from template");
		router.push({ name: "LabDetail", params: { labId: data.name } });
	},
});

function openCreate(template) {
	selectedTemplate.value = template;
	form.lab_id = "";
	form.title = "";
	createAction.error = null;
	showCreateDialog.value = true;
}

function createFromTemplate() {
	if (!form.lab_id) {
		toast.error("Lab ID is required");
		return;
	}
	createAction.submit({
		template: selectedTemplate.value.key,
		lab_id: form.lab_id,
		title: form.title || null,
	});
}
</script>
