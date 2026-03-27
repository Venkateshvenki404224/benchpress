<template>
	<div class="p-6">
		<div class="mb-6 flex items-start justify-between">
			<div>
				<h1 class="text-2xl font-bold text-ink-gray-9">VPN Devices</h1>
				<p class="mt-1 text-sm text-ink-gray-5">
					Register your devices once to access all lab containers over WireGuard VPN.
				</p>
			</div>
			<Button appearance="primary" icon-left="plus" @click="showAddDialog = true">
				Add Device
			</Button>
		</div>

		<div v-if="devices.loading" class="text-sm text-ink-gray-5">Loading devices...</div>

		<div v-else-if="devices.data?.length" class="grid gap-4">
			<div
				v-for="device in devices.data"
				:key="device.name"
				class="flex items-center justify-between rounded-lg border border-outline-gray-1 bg-surface-white px-5 py-4"
			>
				<div class="flex items-center gap-4">
					<div>
						<div class="font-medium text-ink-gray-9">{{ device.device_name }}</div>
						<div class="mt-1 flex items-center gap-2">
							<Badge :label="device.device_type" theme="blue" variant="outline" size="sm" />
							<Badge
								:label="device.status"
								:theme="device.status === 'Active' ? 'green' : 'gray'"
								variant="outline"
								size="sm"
							/>
							<code
								v-if="device.wg_ip"
								class="rounded bg-surface-gray-1 px-2 py-0.5 font-mono text-xs text-ink-gray-7"
								>{{ device.wg_ip }}</code
							>
						</div>
					</div>
				</div>
				<div class="flex items-center gap-2">
					<Button
						size="sm"
						icon-left="download"
						:loading="downloadingConfig === device.name"
						@click="downloadConfig(device)"
					>
						Config
					</Button>
					<Button
						size="sm"
						theme="red"
						variant="subtle"
						icon-left="trash-2"
						:loading="removingDevice === device.name"
						@click="confirmRemove(device)"
					>
						Remove
					</Button>
				</div>
			</div>
		</div>

		<div
			v-else
			class="rounded-lg border border-outline-gray-1 bg-surface-white p-10 text-center"
		>
			<div class="text-sm text-ink-gray-5">No devices registered yet.</div>
			<p class="mt-1 text-xs text-ink-gray-4">
				Add a device to get a WireGuard config that connects you to all your lab containers.
			</p>
		</div>

		<Dialog
			:options="{ title: 'Add Device', size: 'sm' }"
			v-model="showAddDialog"
		>
			<template #body-content>
				<div class="space-y-4">
					<FormControl
						label="Device Name"
						v-model="newDevice.name"
						type="text"
						placeholder="e.g. My Laptop"
						:required="true"
					/>
					<FormControl
						label="Device Type"
						v-model="newDevice.type"
						type="select"
						:options="deviceTypeOptions"
						:required="true"
					/>
					<div>
						<label class="mb-1 flex items-center gap-2 text-xs font-medium text-ink-gray-6">
							<input type="checkbox" v-model="autoGenKey" class="accent-surface-blue-2" />
							Auto Generate Keypair
						</label>
						<FormControl
							v-if="!autoGenKey"
							label="WireGuard Public Key"
							v-model="newDevice.publicKey"
							type="text"
							placeholder="Paste your WireGuard public key"
						/>
						<p v-else class="text-xs text-ink-gray-4">
							A keypair will be generated automatically. Download your config after adding.
						</p>
					</div>
					<ErrorMessage :message="addAction.error" />
				</div>
			</template>
			<template #actions>
				<Button
					appearance="primary"
					class="w-full"
					:loading="addAction.loading"
					@click="addDevice"
				>
					Add Device
				</Button>
			</template>
		</Dialog>

		<Dialog
			:options="{ title: 'Remove Device', size: 'sm' }"
			v-model="showRemoveDialog"
		>
			<template #body-content>
				<p class="text-sm text-ink-gray-6">
					Are you sure you want to remove
					<strong>{{ deviceToRemove?.device_name }}</strong>? This will revoke its VPN access
					immediately.
				</p>
			</template>
			<template #actions>
				<Button
					theme="red"
					variant="solid"
					class="w-full"
					:loading="removeAction.loading"
					@click="removeDevice"
				>
					Remove Device
				</Button>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { ref } from "vue";
import { createResource, Badge, Button, Dialog, FormControl, ErrorMessage } from "frappe-ui";

const showAddDialog = ref(false);
const showRemoveDialog = ref(false);
const deviceToRemove = ref(null);
const downloadingConfig = ref(null);
const removingDevice = ref(null);
const autoGenKey = ref(true);

const newDevice = ref({ name: "", type: "Laptop", publicKey: "" });

const deviceTypeOptions = [
	{ label: "Mobile", value: "Mobile" },
	{ label: "Laptop", value: "Laptop" },
	{ label: "Desktop", value: "Desktop" },
	{ label: "Tablet", value: "Tablet" },
	{ label: "Server", value: "Server" },
	{ label: "IoT", value: "IoT" },
	{ label: "Embedded", value: "Embedded" },
];

const devices = createResource({
	url: "benchpress.api.list_devices",
	auto: true,
});

const addAction = createResource({
	url: "benchpress.api.add_device",
	onSuccess(data) {
		showAddDialog.value = false;
		newDevice.value = { name: "", type: "Laptop", publicKey: "" };
		autoGenKey.value = true;
		devices.reload();

		if (data.wg_config) {
			const blob = new Blob([data.wg_config], { type: "text/plain" });
			const url = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = url;
			a.download = `${newDevice.value.name || "device"}.conf`;
			a.click();
			URL.revokeObjectURL(url);
		}
	},
});

function addDevice() {
	if (!newDevice.value.name) return;
	addAction.submit({
		device_name: newDevice.value.name,
		device_type: newDevice.value.type,
		public_key: autoGenKey.value ? null : newDevice.value.publicKey || null,
	});
}

const removeAction = createResource({
	url: "benchpress.api.remove_device",
	onSuccess() {
		showRemoveDialog.value = false;
		deviceToRemove.value = null;
		devices.reload();
	},
});

function confirmRemove(device) {
	deviceToRemove.value = device;
	showRemoveDialog.value = true;
}

function removeDevice() {
	if (!deviceToRemove.value) return;
	removingDevice.value = deviceToRemove.value.name;
	removeAction.submit(
		{ device_name: deviceToRemove.value.name },
		{ onSuccess() { removingDevice.value = null; } },
	);
}

const configAction = createResource({
	url: "benchpress.api.get_device_wg_config",
});

async function downloadConfig(device) {
	downloadingConfig.value = device.name;
	configAction.submit(
		{ device_name: device.name },
		{
			onSuccess(data) {
				downloadingConfig.value = null;
				const blob = new Blob([data], { type: "text/plain" });
				const url = URL.createObjectURL(blob);
				const a = document.createElement("a");
				a.href = url;
				a.download = `${device.device_name}.conf`;
				a.click();
				URL.revokeObjectURL(url);
			},
			onError() {
				downloadingConfig.value = null;
			},
		},
	);
}
</script>
