<template>
	<SectionCard :padded="false" data-test="device-list">
		<header class="flex items-center gap-2 border-b border-outline-gray-1 px-4 py-3">
			<h2 class="text-sm font-semibold text-ink-gray-9">Registered devices</h2>
			<span class="text-2xs text-ink-gray-5" data-test="device-count">{{ countLabel }}</span>
		</header>

		<p v-if="loading" class="px-4 py-6 text-body text-ink-gray-5">Loading devices…</p>

		<EmptyState
			v-else-if="!devices.length"
			message="No machine can reach your benches yet. Register the one you work from and its config arrives immediately."
			:icon="ShieldIcon"
		/>

		<div
			v-for="device in devices"
			:key="device.name"
			class="flex flex-wrap items-center gap-3 border-b border-outline-gray-1 px-4 py-3"
			:data-test="`device-row-${device.device_name}`"
		>
			<span
				class="flex size-[30px] flex-none items-center justify-center rounded-md border border-outline-gray-1 bg-surface-gray-1 text-ink-gray-7"
			>
				<component :is="iconFor(device.device_type)" class="size-4" />
			</span>

			<div class="min-w-[130px] flex-1">
				<p class="truncate text-body font-semibold text-ink-gray-9">
					{{ device.device_name }}
				</p>
				<p class="text-2xs text-ink-gray-5">{{ subtitle(device) }}</p>
			</div>

			<div class="w-[92px]">
				<p class="text-2xs text-ink-gray-5">IP</p>
				<p class="font-mono text-2xs text-ink-gray-8">{{ device.wg_ip || "—" }}</p>
			</div>

			<div class="w-[140px]">
				<p class="text-2xs text-ink-gray-5">Transfer</p>
				<p class="text-2xs tabular-nums text-ink-gray-8">
					{{ transferLabel(device.wg_rx_bytes, device.wg_tx_bytes) }}
				</p>
			</div>

			<StatusBadge :status="device.status" />

			<div class="ml-auto flex items-center gap-1.5">
				<Button size="sm" data-test="device-config" @click="emit('config', device)">
					Config
				</Button>
				<Button size="sm" data-test="device-qr" @click="emit('qr', device)">QR</Button>
				<Dropdown :options="menuFor(device)" placement="right">
					<Button size="sm" data-test="device-menu">
						<template #icon><EllipsisIcon class="size-3.5" /></template>
					</Button>
				</Dropdown>
			</div>
		</div>

		<button
			class="flex w-full items-center gap-2 px-4 py-3 text-left text-body text-ink-gray-7 hover:bg-surface-gray-1"
			data-test="add-another-machine"
			@click="emit('add')"
		>
			<PlusIcon class="size-3.5" />
			Add another machine
		</button>
	</SectionCard>
</template>

<script setup>
// The device list is full width rather than a card grid, and the last row is
// the add action — so the primary thing a stranded user needs is always in
// reach without hunting for a header button.
import EmptyState from "@/components/EmptyState.vue";
import SectionCard from "@/components/SectionCard.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { deviceSubtitle, transferLabel } from "@/utils/vpnJourney";
import { Button, Dropdown, dayjsLocal } from "frappe-ui";
import { computed } from "vue";

import CpuIcon from "~icons/lucide/cpu";
import DownloadIcon from "~icons/lucide/download";
import EllipsisIcon from "~icons/lucide/ellipsis";
import FileTextIcon from "~icons/lucide/file-text";
import LaptopIcon from "~icons/lucide/laptop";
import MonitorIcon from "~icons/lucide/monitor";
import PlusIcon from "~icons/lucide/plus";
import ServerIcon from "~icons/lucide/server";
import ShieldIcon from "~icons/lucide/shield";
import SmartphoneIcon from "~icons/lucide/smartphone";
import TabletIcon from "~icons/lucide/tablet";
import Trash2Icon from "~icons/lucide/trash-2";

const TYPE_ICONS = {
	Mobile: SmartphoneIcon,
	Laptop: LaptopIcon,
	Desktop: MonitorIcon,
	Tablet: TabletIcon,
	Server: ServerIcon,
	IoT: CpuIcon,
	Embedded: CpuIcon,
};

const props = defineProps({
	devices: { type: Array, default: () => [] },
	loading: { type: Boolean, default: false },
});

const emit = defineEmits(["add", "config", "qr", "download", "remove"]);

const countLabel = computed(() =>
	props.devices.length === 1 ? "1 machine" : `${props.devices.length} machines`
);

function iconFor(deviceType) {
	return TYPE_ICONS[deviceType] ?? ShieldIcon;
}

function subtitle(device) {
	const registered = device.registered_on ? dayjsLocal(device.registered_on).format("D MMM") : "";
	return deviceSubtitle(device.device_type, registered);
}

function menuFor(device) {
	return [
		{
			label: "Show configuration",
			icon: FileTextIcon,
			onClick: () => emit("config", device),
		},
		{
			label: "Download .conf",
			icon: DownloadIcon,
			onClick: () => emit("download", device),
		},
		{
			label: "Remove device",
			icon: Trash2Icon,
			theme: "red",
			onClick: () => emit("remove", device),
		},
	];
}
</script>
