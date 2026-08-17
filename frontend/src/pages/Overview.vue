<template>
	<div class="page-shell" data-test="overview">
		<OnboardingPanel v-if="showOnboarding" />

		<div class="mb-3.5 flex flex-wrap items-end gap-3">
			<div>
				<h1 class="text-title font-semibold text-ink-gray-9" data-test="greeting">
					{{ greeting }}
				</h1>
				<p class="mt-0.5 text-body text-ink-gray-5">{{ subLine }}</p>
			</div>
			<div class="ml-auto flex gap-2">
				<Button
					variant="subtle"
					data-test="from-template"
					@click="router.push('/labs/templates')"
				>
					From template
				</Button>
				<Button variant="solid" data-test="primary-cta" @click="startPrimaryAction">
					<template #prefix><PlusIcon class="size-3.5" /></template>
					{{ primaryLabel }}
				</Button>
			</div>
		</div>

		<div
			v-if="showVpnBanner"
			class="mb-4 flex flex-wrap items-center gap-3 rounded-md border border-outline-amber-2 bg-surface-amber-1 px-4 py-3"
			data-test="vpn-banner"
		>
			<ShieldAlertIcon class="size-4 flex-none text-ink-amber-3" />
			<p class="min-w-0 flex-1 text-body text-ink-amber-3">
				<strong class="font-semibold">VPN is not connected.</strong>
				Sites, SSH and VS Code links stay unreachable until this device is on WireGuard.
			</p>
			<Button variant="solid" data-test="connect-device" @click="router.push('/devices')">
				Connect device
			</Button>
		</div>

		<div class="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4" data-test="stats">
			<StatTile
				label="Running"
				:value="counts.running"
				:note="`of ${counts.total}`"
				:tone="counts.running ? 'green' : ''"
			/>
			<StatTile label="Stopped" :value="counts.stopped" />
			<StatTile
				label="Needs attention"
				:value="counts.needs_attention"
				:tone="counts.needs_attention ? 'red' : ''"
				note="errored or unhealthy"
			/>
			<StatTile label="Deploy time (avg)" :value="deployTimeValue" :note="deployTimeNote" />
		</div>

		<div class="grid items-start gap-4 lg:grid-cols-[minmax(0,1.55fr)_minmax(250px,1fr)]">
			<EnvironmentList
				:environments="overview.environments || []"
				:is-admin="isAdmin"
				:vpn-connected="vpnStatus.connected"
			/>
			<div class="flex flex-col gap-4">
				<ActivityFeed :events="overview.activity || []" :window-days="windowDays" />
				<InfrastructureCard v-if="isAdmin" :checks="overview.infrastructure || []" />
			</div>
		</div>
	</div>
</template>

<script setup>
import StatTile from "@/components/StatTile.vue";
import ActivityFeed from "@/components/overview/ActivityFeed.vue";
import EnvironmentList from "@/components/overview/EnvironmentList.vue";
import InfrastructureCard from "@/components/overview/InfrastructureCard.vue";
import OnboardingPanel from "@/components/overview/OnboardingPanel.vue";
import { overviewResource } from "@/data/overview";
import { vpnStatus } from "@/data/vpnStatus";
import { Button } from "frappe-ui";
import { computed } from "vue";
import { useRouter } from "vue-router";

import PlusIcon from "~icons/lucide/plus";
import ShieldAlertIcon from "~icons/lucide/shield-alert";

const router = useRouter();

const overview = computed(() => overviewResource.data ?? {});
const isAdmin = computed(() => overview.value.is_admin ?? false);
const counts = computed(
	() =>
		overview.value.counts ?? {
			total: 0,
			running: 0,
			stopped: 0,
			needs_attention: 0,
		}
);
const deployTime = computed(() => overview.value.deploy_time ?? {});
const windowDays = computed(() => deployTime.value.window_days ?? 7);

const showOnboarding = computed(() => overviewResource.data != null && counts.value.total === 0);
const showVpnBanner = computed(() => vpnStatus.ready && !vpnStatus.connected);

const greeting = computed(() => {
	const name = overview.value.first_name;
	return name ? `${timeOfDay()}, ${name}` : timeOfDay();
});

const subLine = computed(() => {
	const { total, running, stopped } = counts.value;
	const scope = isAdmin.value ? "instance" : "environment";
	return `${total} ${scope}${total === 1 ? "" : "s"} · ${running} running, ${stopped} stopped`;
});

// A BenchPress User cannot create labs, so their CTA starts from a template.
const primaryLabel = computed(() => (isAdmin.value ? "New lab" : "New environment"));

// Log retention bounds the sample, so the caption always names the window.
const deployTimeValue = computed(() => deployTime.value.average_label || "—");
const deployTimeNote = computed(() => {
	const runs = deployTime.value.sample_size;
	if (!runs) return `no runs in the last ${windowDays.value} days`;
	return `${runs} run${runs === 1 ? "" : "s"}, last ${windowDays.value} days`;
});

function timeOfDay() {
	const hour = new Date().getHours();
	if (hour < 12) return "Good morning";
	if (hour < 18) return "Good afternoon";
	return "Good evening";
}

function startPrimaryAction() {
	router.push(isAdmin.value ? "/labs/new" : "/labs/templates");
}
</script>
