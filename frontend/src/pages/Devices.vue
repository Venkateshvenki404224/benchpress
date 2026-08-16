<template>
	<div class="mx-auto max-w-[960px] px-6 pb-10 pt-[22px]" data-test="devices">
		<div class="mb-4 flex flex-wrap items-start gap-3">
			<div>
				<h1 class="text-title font-semibold text-ink-gray-9">Devices</h1>
				<p class="mt-0.5 max-w-[580px] text-body text-ink-gray-5">
					Bench instances live on a private WireGuard network. Register each machine you
					work from, install its config, and the sites become reachable.
				</p>
			</div>
			<Button class="ml-auto" variant="solid" data-test="add-device" @click="openAddDialog">
				<template #prefix><PlusIcon class="size-3.5" /></template>
				Add device
			</Button>
		</div>

		<VpnStatusBanner
			:connected="vpnStatus.connected"
			:handshake-age-seconds="handshakeAgeSeconds"
			:device-count="devices.length"
			:checking="checking"
			@act="onBannerAction"
		/>

		<div class="mt-4 grid items-start gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(240px,1fr)]">
			<DeviceList
				:devices="devices"
				:loading="devicesResource.loading"
				@add="openAddDialog"
				@config="showConfig"
				@qr="showConfig"
				@download="downloadConfig"
				@remove="confirmRemove"
			/>
			<div class="flex flex-col gap-4">
				<HowItWorksCard />
				<ConnectionTestCard @tested="refreshStatus" />
			</div>
		</div>

		<AddDeviceDialog
			v-model="addDialogOpen"
			:device-types="deviceTypesResource.data ?? []"
			@registered="onRegistered"
			@download-config="saveConfigFile"
		/>

		<DeviceConfigDialog
			v-model="configDialogOpen"
			:device-name="selectedDevice?.device_name ?? ''"
			:config="configResource.data ?? ''"
			@download="saveConfigFile(configResource.data, selectedDevice?.device_name)"
		/>

		<ConfirmDialog
			v-if="removing"
			title="Remove this device?"
			:message="removeMessage"
			:onConfirm="runRemove"
			:onCancel="dismissRemove"
		/>

		<ErrorMessage class="mt-3" :message="removeDevice.error || configResource.error" />
	</div>
</template>

<script setup>
import AddDeviceDialog from "@/components/device/AddDeviceDialog.vue";
import ConnectionTestCard from "@/components/device/ConnectionTestCard.vue";
import DeviceConfigDialog from "@/components/device/DeviceConfigDialog.vue";
import DeviceList from "@/components/device/DeviceList.vue";
import HowItWorksCard from "@/components/device/HowItWorksCard.vue";
import VpnStatusBanner from "@/components/device/VpnStatusBanner.vue";
import { devicesResource, deviceTypesResource, reloadDevices } from "@/data/devices";
import { reloadVpnStatus, vpnStatus } from "@/data/vpnStatus";
import { ADD_DEVICE } from "@/utils/vpnJourney";
import { Button, ConfirmDialog, ErrorMessage, createResource, dayjsLocal } from "frappe-ui";
import { computed, ref } from "vue";

import PlusIcon from "~icons/lucide/plus";

// The screen a stranded user is sent to from everywhere else in the app: the
// tunnel's real state, the machines on it, and a test that says which step of
// the journey is broken.
const addDialogOpen = ref(false);
const configDialogOpen = ref(false);
const selectedDevice = ref(null);
const removing = ref(null);
const checking = ref(false);

const devices = computed(() => devicesResource.data ?? []);

/** How old the newest handshake is; null when the server has never seen one. */
const handshakeAgeSeconds = computed(() => {
	if (!vpnStatus.lastHandshake) return null;
	return Math.max(0, dayjsLocal().diff(dayjsLocal(vpnStatus.lastHandshake), "second"));
});

const configResource = createResource({ url: "benchpress.api.get_device_wg_config" });

const removeDevice = createResource({
	url: "benchpress.api.remove_device",
	onSuccess: refreshStatus,
});

function openAddDialog() {
	addDialogOpen.value = true;
}

async function onBannerAction(action) {
	if (action === ADD_DEVICE) return openAddDialog();
	checking.value = true;
	await refreshStatus();
	checking.value = false;
}

async function refreshStatus() {
	await Promise.all([reloadDevices(), reloadVpnStatus()]);
}

function onRegistered() {
	refreshStatus();
}

async function showConfig(device) {
	selectedDevice.value = device;
	await configResource.submit({ device_name: device.name });
	if (!configResource.error) configDialogOpen.value = true;
}

async function downloadConfig(device) {
	await configResource.submit({ device_name: device.name });
	if (!configResource.error) saveConfigFile(configResource.data, device.device_name);
}

/** A WireGuard client reads a plain file, so the config is handed over as one. */
function saveConfigFile(config, deviceName) {
	if (!config) return;
	const url = URL.createObjectURL(new Blob([config], { type: "text/plain" }));
	const link = document.createElement("a");
	link.href = url;
	link.download = `${(deviceName || "device").replace(/\s+/g, "-")}.conf`;
	link.click();
	URL.revokeObjectURL(url);
}

const removeMessage = computed(
	() =>
		`${removing.value?.device_name} loses VPN access immediately and its tunnel IP ` +
		"goes back to the pool. Registering it again issues a new config."
);

function confirmRemove(device) {
	removing.value = device;
}

function dismissRemove() {
	removing.value = null;
}

async function runRemove() {
	await removeDevice.submit({ device_name: removing.value.name });
	removing.value = null;
}
</script>
