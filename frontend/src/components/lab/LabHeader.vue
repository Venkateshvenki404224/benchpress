<template>
	<header class="flex flex-wrap items-start gap-4" data-test="lab-header">
		<span
			class="grid size-10 flex-none place-items-center rounded-md border border-outline-gray-1 bg-surface-white"
		>
			<AppIcon :app="primaryApp" :size="24" />
		</span>

		<div class="min-w-0 flex-1">
			<div class="flex flex-wrap items-center gap-2.5">
				<h1 class="text-title font-semibold text-ink-gray-9" data-test="lab-title">
					{{ lab.title || lab.lab_id }}
				</h1>
				<StatusBadge :status="lab.status" />
			</div>
			<code class="mt-1 block font-mono text-2xs text-ink-gray-5" data-test="lab-id">
				{{ lab.lab_id }}
			</code>
			<p
				v-if="lab.description"
				class="mt-2 max-w-[620px] text-body text-ink-gray-6"
				data-test="lab-description"
			>
				{{ lab.description }}
			</p>
			<div class="mt-2.5 flex flex-wrap gap-1.5" data-test="lab-specs">
				<span
					v-for="chip in specChips"
					:key="chip"
					class="rounded bg-surface-gray-2 px-1.5 py-px text-2xs text-ink-gray-7"
				>
					{{ chip }}
				</span>
				<!-- The price sits with the specs that decide it, in view at the moment
				     of choosing rather than discovered later on a statement. -->
				<span
					v-if="rateChip"
					class="rounded bg-surface-amber-1 px-1.5 py-px text-2xs text-ink-amber-3"
					data-test="lab-rate"
				>
					{{ rateChip }}
				</span>
			</div>
		</div>

		<div class="flex flex-col items-end gap-1">
			<div class="flex items-center gap-2">
				<!-- A tunnel-only IDE address is unreachable off-tunnel; a public one opens
				     from anywhere. The caption below covers both buttons. -->
				<Button
					v-if="showCodeServer"
					variant="subtle"
					:disabled="!vpnConnected && urlNeedsVpn(ideUrl(bench))"
					data-test="open-code-server"
					@click="emit('code-server')"
				>
					Open VS Code
				</Button>
				<Button
					variant="solid"
					:disabled="primary.disabled"
					:loading="busy"
					data-test="primary-action"
					@click="runPrimary"
				>
					{{ primary.label }}
				</Button>
				<Dropdown :options="overflowOptions" align="end">
					<Button variant="subtle" data-test="lab-overflow" aria-label="More actions">
						<template #icon><EllipsisIcon class="size-4" /></template>
					</Button>
				</Dropdown>
			</div>
			<!-- An unreachable action stays visible and says why, rather than
			     disappearing. A disabled button emits no hover events, so the
			     reason is a caption and never a tooltip. -->
			<p v-if="primary.hint" class="text-2xs text-ink-gray-5" data-test="primary-hint">
				{{ primary.hint }}
			</p>
		</div>

		<ConfirmDialog
			v-if="confirming"
			:title="confirming.title"
			:message="confirming.message"
			:onConfirm="runConfirmed"
			:onCancel="dismissConfirm"
		/>
	</header>
</template>

<script setup>
import AppIcon from "@/components/AppIcon.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { rateLabel } from "@/utils/credits";
import { OPEN, REBUILD, ideUrl, primaryAction, urlNeedsVpn } from "@/utils/labActions";
import { cpuLabel, memoryLabel } from "@/utils/labSpecs";
import { Button, ConfirmDialog, Dropdown } from "frappe-ui";
import { computed, ref } from "vue";

import EllipsisIcon from "~icons/lucide/ellipsis";
import HammerIcon from "~icons/lucide/hammer";
import SquareIcon from "~icons/lucide/square";
import Trash2Icon from "~icons/lucide/trash-2";

// Both destructive actions name what they destroy before they run. Deleting a
// bench is irreversible and takes data with it, so the copy says so.
const CONFIRMATIONS = {
	stop: {
		event: "stop",
		title: "Stop this bench?",
		message:
			"The container stops and the site goes offline until it is deployed again. Nothing is deleted.",
	},
	delete: {
		event: "delete",
		title: "Delete this bench?",
		message:
			"This removes the container, its Docker volume and every site database on the shared MariaDB server. Site data and uploaded files are destroyed and cannot be recovered.",
	},
};

const props = defineProps({
	lab: { type: Object, required: true },
	bench: { type: Object, default: null },
	vpnConnected: { type: Boolean, default: false },
	isAdmin: { type: Boolean, default: false },
	// A lifecycle call is already in flight.
	busy: { type: Boolean, default: false },
	siteUrl: { type: String, default: null },
});

const emit = defineEmits(["deploy", "rebuild", "open", "stop", "delete", "code-server"]);

const confirming = ref(null);

const primary = computed(() =>
	primaryAction({
		labStatus: props.lab.status,
		benchStatus: props.bench?.status ?? "",
		vpnConnected: props.vpnConnected,
		siteUrl: props.siteUrl,
		isAdmin: props.isAdmin,
	})
);

const isRunning = computed(() => props.bench?.status === "Running");

const showCodeServer = computed(
	() => isRunning.value && props.lab.enable_code_server && !!props.bench?.code_server_url
);

/** The mark the lab wears — its first non-Frappe app, else the Frappe mark. */
const primaryApp = computed(
	() =>
		(props.lab.apps ?? [])
			.map((app) => app.app_name)
			.find((name) => name && name.toLowerCase() !== "frappe") || "frappe"
);

const specChips = computed(() => {
	const chips = [
		props.lab.frappe_version,
		memoryLabel(props.lab.memory_limit),
		cpuLabel(props.lab.cpu_cores),
	];
	if (props.lab.enable_code_server) chips.push("code-server");
	if (props.lab.enable_ssh) chips.push("SSH");
	return chips.filter(Boolean);
});

// `null` means credits do not exist on this site, which is not the same as a size
// that is free — so the chip is absent in the first case and reads "0" in the second.
const rateChip = computed(() =>
	props.lab.credits_per_hour === null || props.lab.credits_per_hour === undefined
		? ""
		: rateLabel(props.lab.credits_per_hour)
);

// Stop and Delete are reachable only from here, each behind a confirmation.
const overflowOptions = computed(() => {
	const options = [];
	if (props.isAdmin && primary.value.action !== REBUILD) {
		options.push({
			label: "Rebuild image",
			icon: HammerIcon,
			onClick: () => emit("rebuild"),
		});
	}
	if (isRunning.value) {
		options.push({
			label: "Stop bench",
			icon: SquareIcon,
			onClick: () => askConfirm("stop"),
		});
	}
	if (props.bench && props.isAdmin) {
		options.push({
			label: "Delete bench",
			icon: Trash2Icon,
			theme: "red",
			onClick: () => askConfirm("delete"),
		});
	}
	return options;
});

function runPrimary() {
	if (primary.value.action === OPEN) return emit("open");
	if (primary.value.action === REBUILD) return emit("rebuild");
	emit("deploy");
}

function askConfirm(key) {
	confirming.value = CONFIRMATIONS[key];
}

function runConfirmed({ hideDialog }) {
	emit(confirming.value.event);
	hideDialog();
	confirming.value = null;
}

function dismissConfirm() {
	confirming.value = null;
}
</script>
