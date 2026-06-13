<template>
	<div class="p-6">
		<div class="mb-6 flex items-start justify-between">
			<div>
				<h1 class="text-2xl font-bold text-ink-gray-9">VPN Devices</h1>
				<p class="mt-1 text-sm text-ink-gray-5">
					Register your devices once to access all lab containers over WireGuard VPN.
				</p>
			</div>
			<Button
				variant="solid"
				theme="gray"
				:icon-left="PlusIcon"
				@click="showAddDialog = true"
			>
				Add Device
			</Button>
		</div>

		<div v-if="devices.loading" class="text-sm text-ink-gray-5">Loading devices...</div>

		<div
			v-else-if="devices.data?.length"
			class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
		>
			<div
				v-for="device in devices.data"
				:key="device.name"
				class="flex items-center justify-between rounded-lg border border-outline-gray-1 bg-surface-white px-5 py-4"
			>
				<div class="flex items-center gap-4">
					<div>
						<div class="font-medium text-ink-gray-9">{{ device.device_name }}</div>
						<div class="mt-1 flex items-center gap-2">
							<Badge
								:label="device.device_type"
								theme="blue"
								variant="outline"
								size="sm"
							/>
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
						<div
							v-if="device.wg_rx_bytes || device.wg_tx_bytes"
							class="mt-2 flex gap-3 text-xs text-ink-gray-5"
						>
							<span
								>Received:
								<strong class="text-ink-gray-7">{{
									formatBytes(device.wg_rx_bytes)
								}}</strong></span
							>
							<span
								>Sent:
								<strong class="text-ink-gray-7">{{
									formatBytes(device.wg_tx_bytes)
								}}</strong></span
							>
						</div>
					</div>
				</div>
				<Dropdown
					:options="getDeviceActions(device)"
					:button="{ icon: MoreIcon, variant: 'ghost', label: 'Device actions' }"
				/>
			</div>
		</div>

		<div
			v-else
			class="rounded-lg border border-outline-gray-1 bg-surface-white p-10 text-center"
		>
			<div class="text-sm text-ink-gray-5">No devices registered yet.</div>
			<p class="mt-1 text-xs text-ink-gray-4">
				Add a device to get a WireGuard config that connects you to all your lab
				containers.
			</p>
		</div>

		<Dialog :options="{ title: 'Add Device', size: 'sm' }" v-model="showAddDialog">
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
						<Checkbox
							v-model="autoGenKey"
							label="Auto Generate Keypair"
							class="mb-2"
						/>
						<FormControl
							v-if="!autoGenKey"
							label="WireGuard Public Key"
							v-model="newDevice.publicKey"
							type="text"
							placeholder="Paste your WireGuard public key"
						/>
						<p v-else class="text-xs text-ink-gray-4">
							A keypair will be generated automatically. Download your config after
							adding.
						</p>
					</div>
					<ErrorMessage :message="addAction.error" />
				</div>
			</template>
			<template #actions>
				<Button
					variant="solid"
					theme="gray"
					class="w-full"
					:loading="addAction.loading"
					@click="addDevice"
				>
					Add Device
				</Button>
			</template>
		</Dialog>

		<Dialog :options="{ title: 'Remove Device', size: 'sm' }" v-model="showRemoveDialog">
			<template #body-content>
				<p class="text-sm text-ink-gray-6">
					Are you sure you want to remove
					<strong>{{ deviceToRemove?.device_name }}</strong
					>? This will revoke its VPN access immediately.
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

		<Dialog :options="{ title: configDeviceName, size: 'xl' }" v-model="showConfigDialog">
			<template #body-content>
				<div class="flex gap-6">
					<pre
						class="max-h-96 flex-1 overflow-auto rounded-lg bg-surface-gray-1 p-4 font-mono text-xs text-ink-gray-8"
						>{{ configText }}</pre
					>
					<div class="flex flex-col items-center gap-3">
						<canvas ref="qrCanvas" />
						<p class="max-w-[200px] text-center text-xs text-ink-gray-5">
							Scan with WireGuard app to import this tunnel
						</p>
					</div>
				</div>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { ref, nextTick } from "vue";
import {
	useCall,
	Badge,
	Button,
	Checkbox,
	Dialog,
	Dropdown,
	FormControl,
	ErrorMessage,
} from "frappe-ui";
import QRCode from "qrcode";
import PlusIcon from "~icons/lucide/plus";
import MoreIcon from "~icons/lucide/more-horizontal";
import FileTextIcon from "~icons/lucide/file-text";
import DownloadIcon from "~icons/lucide/download";
import Trash2Icon from "~icons/lucide/trash-2";
import { downloadFile } from "@/utils/downloadFile";

function formatBytes(bytes) {
	if (!bytes) return "0 B";
	const units = ["B", "KiB", "MiB", "GiB", "TiB"];
	let i = 0;
	let val = bytes;
	while (val >= 1024 && i < units.length - 1) {
		val /= 1024;
		i++;
	}
	return `${val.toFixed(i > 0 ? 2 : 0)} ${units[i]}`;
}

const showAddDialog = ref(false);
const showRemoveDialog = ref(false);
const deviceToRemove = ref(null);
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

function getDeviceActions(device) {
	return [
		{
			group: "Configuration",
			items: [
				{
					label: "Show Configuration",
					icon: FileTextIcon,
					onClick: () => showConfig(device),
				},
				{
					label: "Download Tunnel File",
					icon: DownloadIcon,
					onClick: () => downloadConfig(device),
				},
			],
		},
		{
			group: "Danger",
			items: [
				{
					label: "Delete",
					icon: Trash2Icon,
					theme: "red",
					onClick: () => confirmRemove(device),
				},
			],
		},
	];
}

const showConfigDialog = ref(false);
const configText = ref("");
const configDeviceName = ref("");
const qrCanvas = ref(null);

const wgConfigAction = useCall({
	url: "/api/v2/method/benchpress.api.get_device_wg_config",
	method: "POST",
	immediate: false,
});

async function showConfig(device) {
	configDeviceName.value = device.device_name;
	const data = await wgConfigAction.submit({ device_name: device.name });
	if (!data) return;
	configText.value = data;
	showConfigDialog.value = true;
	nextTick(() => {
		if (qrCanvas.value && configText.value) {
			QRCode.toCanvas(qrCanvas.value, configText.value, {
				width: 200,
				margin: 2,
			});
		}
	});
}

const devices = useCall({
	url: "/api/v2/method/benchpress.api.list_devices",
	immediate: true,
});

const addAction = useCall({
	url: "/api/v2/method/benchpress.api.add_device",
	method: "POST",
	immediate: false,
	onSuccess() {
		showAddDialog.value = false;
		newDevice.value = { name: "", type: "Laptop", publicKey: "" };
		autoGenKey.value = true;
		devices.reload();
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

const removeAction = useCall({
	url: "/api/v2/method/benchpress.api.remove_device",
	method: "POST",
	immediate: false,
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
	removeAction.submit({ device_name: deviceToRemove.value.name });
}

async function downloadConfig(device) {
	const data = await wgConfigAction.submit({ device_name: device.name });
	if (!data) return;
	downloadFile(data, `${device.device_name}.conf`);
}
</script>
