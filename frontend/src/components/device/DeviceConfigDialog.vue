<template>
	<Dialog v-model="isOpen" :options="{ title, size: 'xl' }" data-test="device-config-dialog">
		<template #body-content>
			<div class="flex flex-wrap gap-4">
				<pre
					class="max-h-80 min-w-[260px] flex-1 overflow-auto rounded-md bg-surface-gray-2 p-3 font-mono text-2xs text-ink-gray-8"
					data-test="config-text"
					>{{ config }}</pre
				>
				<QrPanel :text="config" :size="200" />
			</div>
			<p class="mt-3 text-2xs text-ink-gray-5">
				One config per machine — importing the same one twice disconnects the other device.
			</p>
		</template>

		<template #actions>
			<Button variant="solid" data-test="download-config" @click="emit('download')">
				<template #prefix><DownloadIcon class="size-3.5" /></template>
				Download .conf
			</Button>
		</template>
	</Dialog>
</template>

<script setup>
// The stored config of an existing device, text and QR side by side: a laptop
// imports the file, a phone scans the code, and both come from one fetch.
import QrPanel from "@/components/device/QrPanel.vue";
import { Button, Dialog } from "frappe-ui";
import { computed } from "vue";

import DownloadIcon from "~icons/lucide/download";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	deviceName: { type: String, default: "" },
	config: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue", "download"]);

const isOpen = computed({
	get: () => props.modelValue,
	set: (value) => emit("update:modelValue", value),
});

const title = computed(() => props.deviceName || "Device configuration");
</script>
