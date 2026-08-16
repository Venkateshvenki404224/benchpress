<template>
	<Dialog v-model="isOpen" :options="{ title: 'Add this device', size: 'lg' }" data-test="add-device-dialog">
		<template #body-content>
			<p class="text-2xs text-ink-gray-5">Two minutes, once per machine.</p>

			<div class="mt-3 flex gap-3">
				<FormControl
					class="flex-1"
					label="Device name"
					type="text"
					v-model="deviceName"
					:disabled="registered"
					placeholder="e.g. Priya — MacBook Pro"
					data-test="device-name"
				/>
				<FormControl
					class="w-[132px]"
					label="Type"
					type="select"
					v-model="deviceType"
					:options="deviceTypes"
					:disabled="registered"
					data-test="device-type"
				/>
			</div>

			<div class="mt-4 flex flex-wrap gap-4">
				<QrPanel :text="config" />
				<div class="min-w-[220px] flex-1 text-2xs leading-5 text-ink-gray-7">
					<p>
						Scan with the WireGuard app on a phone, or download the
						<span class="font-mono">.conf</span> file and import it on a laptop. This
						device gets a fixed IP on the lab network — nothing else routes through the
						tunnel.
					</p>
					<p v-if="registered" class="mt-2 text-ink-green-3" data-test="registered-note">
						Registered as {{ assignedIp }}. Import the config and turn the tunnel on.
					</p>
					<Button
						class="mt-3"
						:disabled="!config"
						data-test="download-conf"
						@click="emit('download-config', config, deviceName)"
					>
						<template #prefix><DownloadIcon class="size-3.5" /></template>
						Download .conf
					</Button>
				</div>
			</div>

			<ErrorMessage class="mt-3" :message="addDevice.error" />
		</template>

		<template #actions>
			<div class="flex items-center gap-2">
				<Button data-test="cancel-add-device" @click="close">
					{{ registered ? "Close" : "Cancel" }}
				</Button>
				<Button
					v-if="!registered"
					class="ml-auto"
					variant="solid"
					:loading="addDevice.loading"
					:disabled="!deviceName.trim()"
					data-test="register-and-connect"
					@click="register"
				>
					Register and connect
				</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
// The config only exists once the peer does, so the dialog registers first and
// then shows the QR it just created — a QR before registration would be a
// picture of nothing.
import QrPanel from "@/components/device/QrPanel.vue";
import { Button, Dialog, ErrorMessage, FormControl, createResource } from "frappe-ui";
import { computed, nextTick, ref, watch } from "vue";

import DownloadIcon from "~icons/lucide/download";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	deviceTypes: { type: Array, default: () => [] },
});

const emit = defineEmits(["update:modelValue", "registered", "download-config"]);

const deviceName = ref("");
const deviceType = ref("Laptop");
const config = ref("");
const assignedIp = ref("");

const isOpen = computed({
	get: () => props.modelValue,
	set: (value) => emit("update:modelValue", value),
});

const registered = computed(() => Boolean(config.value));

const addDevice = createResource({
	url: "benchpress.api.add_device",
	onSuccess(data) {
		config.value = data.wg_config;
		assignedIp.value = data.wg_ip;
		emit("registered");
	},
});

watch(isOpen, (open) => (open ? onOpen() : reset()));

async function onOpen() {
	reset();
	await nextTick();
	// FormControl forwards unknown attributes to the input itself, so this is
	// the input, not a wrapper.
	document.querySelector('[data-test="device-name"]')?.focus();
}

function reset() {
	deviceName.value = "";
	deviceType.value = defaultType();
	config.value = "";
	assignedIp.value = "";
	addDevice.error = null;
}

/** The machine a developer registers first, when the backend offers it. */
function defaultType() {
	return props.deviceTypes.includes("Laptop") ? "Laptop" : (props.deviceTypes[0] ?? "Laptop");
}

async function register() {
	await addDevice.submit({
		device_name: deviceName.value.trim(),
		device_type: deviceType.value,
		public_key: null,
	});
}

function close() {
	isOpen.value = false;
}
</script>
