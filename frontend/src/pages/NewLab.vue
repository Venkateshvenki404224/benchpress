<template>
	<div class="mx-auto max-w-2xl p-6">
		<div class="mb-6 flex items-center justify-between">
			<h1 class="text-xl font-semibold text-ink-gray-9">New Lab</h1>
			<div class="flex gap-2">
				<Button appearance="minimal" @click="$router.push('/labs')">Cancel</Button>
				<Button appearance="primary" :loading="lab.insert.loading" @click="createLab">
					Create Lab
				</Button>
			</div>
		</div>

		<ErrorMessage class="mb-4" :message="lab.insert.error" />

		<!-- Basic Info -->
		<div class="mb-6 rounded-lg border border-outline-gray-1 bg-surface-white p-4">
			<h2 class="mb-4 text-base font-medium text-ink-gray-8">Basic Info</h2>
			<div class="grid grid-cols-2 gap-4">
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
					placeholder="e.g. CRM Development Lab"
					:required="true"
				/>
				<FormControl
					label="Frappe Version"
					v-model="form.frappe_version"
					type="select"
					:options="versionOptions"
					:required="true"
				/>
				<FormControl
					label="Status"
					v-model="form.status"
					type="select"
					:options="statusOptions"
					disabled
				/>
			</div>
			<div class="mt-4">
				<FormControl
					label="Description"
					v-model="form.description"
					type="textarea"
					placeholder="Optional description for this lab"
				/>
			</div>
		</div>

		<!-- Resource Limits -->
		<div class="mb-6 rounded-lg border border-outline-gray-1 bg-surface-white p-4">
			<h2 class="mb-4 text-base font-medium text-ink-gray-8">Resource Limits</h2>
			<div class="grid grid-cols-2 gap-4">
				<FormControl
					label="Memory Limit"
					v-model="form.memory_limit"
					type="text"
					placeholder="e.g. 512m"
				/>
				<FormControl label="CPU Cores" v-model="form.cpu_cores" type="number" />
				<FormControl
					label="Max IOPS (Block I/O)"
					v-model="form.iops_limit"
					type="number"
					description="Per host block device. 0 = default (1000)."
				/>
				<FormControl
					label="Max Bytes/sec (Block I/O)"
					v-model="form.bps_limit"
					type="number"
					description="Per host block device. 0 = default (40 MiB/s)."
				/>
			</div>
		</div>

		<!-- Apps -->
		<div class="mb-6 rounded-lg border border-outline-gray-1 bg-surface-white p-4">
			<div class="mb-4 flex items-center justify-between">
				<h2 class="text-base font-medium text-ink-gray-8">Apps</h2>
				<Button icon-left="plus" appearance="minimal" @click="addApp">Add App</Button>
			</div>

			<div v-if="form.apps.length === 0" class="py-4 text-center text-sm text-ink-gray-5">
				No apps added yet. Click "Add App" to get started.
			</div>

			<div
				v-for="(app, idx) in form.apps"
				:key="idx"
				class="mb-3 rounded border border-outline-gray-1 p-3"
			>
				<div class="mb-2 flex items-center justify-between">
					<span class="text-sm font-medium text-ink-gray-7">App {{ idx + 1 }}</span>
					<Button icon="x" appearance="minimal" size="sm" @click="removeApp(idx)" />
				</div>
				<div class="grid grid-cols-3 gap-3">
					<FormControl
						label="App Name"
						v-model="app.app_name"
						type="text"
						placeholder="e.g. erpnext"
						:required="true"
					/>
					<FormControl
						label="Git URL"
						v-model="app.git_url"
						type="text"
						placeholder="https://github.com/..."
						:required="true"
					/>
					<FormControl
						label="Branch"
						v-model="app.branch"
						type="text"
						placeholder="e.g. version-15"
						:required="true"
					/>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { reactive } from "vue";
import { useRouter } from "vue-router";
import { createListResource, toast, Button, FormControl, ErrorMessage } from "frappe-ui";

const router = useRouter();

const versionOptions = [
	{ label: "Version 14", value: "version-14" },
	{ label: "Version 15", value: "version-15" },
	{ label: "Version 16", value: "version-16" },
	{ label: "Develop", value: "develop" },
];

const statusOptions = [{ label: "Draft", value: "Draft" }];

const form = reactive({
	lab_id: "",
	title: "",
	frappe_version: "version-15",
	status: "Draft",
	description: "",
	memory_limit: "512m",
	cpu_cores: 1,
	iops_limit: 0,
	bps_limit: 0,
	apps: [],
});

function addApp() {
	form.apps.push({ app_name: "", git_url: "", branch: "" });
}

function removeApp(idx) {
	form.apps.splice(idx, 1);
}

const lab = createListResource({
	doctype: "Lab",
	fields: ["name"],
});

async function createLab() {
	if (!form.lab_id || !form.title || !form.frappe_version) {
		toast.error("Please fill all required fields");
		return;
	}

	try {
		await lab.insert.submit({
			lab_id: form.lab_id,
			title: form.title,
			frappe_version: form.frappe_version,
			status: form.status,
			description: form.description,
			memory_limit: form.memory_limit,
			cpu_cores: form.cpu_cores,
			iops_limit: form.iops_limit,
			bps_limit: form.bps_limit,
			apps: form.apps.filter((a) => a.app_name && a.git_url && a.branch),
		});
		router.push("/labs");
	} catch (err) {
		// lab.insert.error is rendered by the ErrorMessage above
	}
}
</script>
