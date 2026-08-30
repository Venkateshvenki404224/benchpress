<template>
	<FrappeUIProvider>
		<div class="flex h-screen">
			<Sidebar :sections="sections">
				<!-- Search and notifications belong to the account, not to a screen,
				     so they sit under the header rather than in the nav proper. -->
				<template #header>
					<SidebarHeader
						title="BenchPress"
						:subtitle="session.user || ''"
						logo="/assets/benchpress/images/logo/favicon.svg"
						:menu-items="accountMenu"
					/>
					<SidebarSection :items="utilityItems">
						<template #sidebar-item="{ item }">
							<SidebarItem
								:label="item.label"
								:icon="item.icon"
								:suffix="item.suffix"
								:to="item.to"
								:isActive="item.isActive"
								:onClick="item.onClick"
								:data-test="item.dataTest"
							/>
						</template>
					</SidebarSection>
				</template>
				<template #sidebar-item="{ item, isCollapsed }">
					<SidebarItem
						:label="item.label"
						:icon="item.icon"
						:to="item.to"
						:isActive="item.isActive"
						:data-test="item.dataTest"
					/>
				</template>
				<!-- The balance sits at the foot of the rail, above the collapse
				     control, and only on a hosted site. -->
				<template #footer-items="{ isCollapsed }">
					<CreditMeter v-if="creditsEnabled" :is-collapsed="isCollapsed" />
				</template>
			</Sidebar>

			<div class="relative flex min-w-0 flex-1 flex-col">
				<!-- Slides out against the sidebar, over the screen the user is
				     on, so nothing they were reading moves. -->
				<NotificationsPanel />

				<header
					class="flex h-[50px] flex-none items-center gap-3 border-b border-outline-gray-1 bg-surface-white px-5"
					data-test="app-header"
				>
					<Breadcrumbs :items="breadcrumbs" />
					<div class="ml-auto flex items-center gap-2.5">
						<router-link
							to="/devices"
							class="flex h-7 items-center gap-1.5 rounded-control border border-outline-gray-1 px-2.5 text-2xs"
							:class="vpnStatus.connected ? 'text-ink-green-3' : 'text-ink-amber-3'"
							data-test="vpn-chip"
						>
							<span
								class="size-[5px] rounded-full"
								:class="
									vpnStatus.connected
										? 'bg-surface-green-3'
										: 'bg-surface-amber-2 animate-vpn-pulse'
								"
							/>
							{{ vpnStatus.connected ? "VPN connected" : "VPN off" }}
						</router-link>
					</div>
				</header>

				<main class="flex-1 overflow-auto bg-surface-gray-1">
					<router-view />
				</main>
			</div>
		</div>

		<!-- A deploy can be started from three screens and outlives all of
		     them, so the dialog that follows it is mounted once, here. The
		     sidebar's own dialogs are mounted here for the same reason. -->
		<DeployDialog />
		<AppSearch />
		<SettingsDialog v-if="userContext.isAdmin" />
	</FrappeUIProvider>
</template>

<script setup>
import AppSearch from "@/components/AppSearch.vue";
import NotificationsPanel from "@/components/NotificationsPanel.vue";
import CreditMeter from "@/components/credit/CreditMeter.vue";
import DeployDialog from "@/components/deploy/DeployDialog.vue";
import SettingsDialog from "@/components/settings/SettingsDialog.vue";
import { openSettings } from "@/data/benchpressSettings";
import { creditsEnabled, primeCreditSummary, refreshCreditSummary } from "@/data/credits";
import { attentionCount, toggleNotifications } from "@/data/notifications";
import { openSearch, searchShortcut } from "@/data/searchPalette";
import { session } from "@/data/session";
import { userContext } from "@/data/userContext";
import { vpnStatus } from "@/data/vpnStatus";
import { useSocket } from "@/socket";
import {
	Breadcrumbs,
	FrappeUIProvider,
	Sidebar,
	SidebarHeader,
	SidebarItem,
	SidebarSection,
	toast,
	useTheme,
} from "frappe-ui";
import { computed, onMounted, onUnmounted, watch } from "vue";
import { useRoute } from "vue-router";

import BellIcon from "~icons/lucide/bell";
import FlaskConicalIcon from "~icons/lucide/flask-conical";
import LayoutDashboardIcon from "~icons/lucide/layout-dashboard";
import LayoutTemplateIcon from "~icons/lucide/layout-template";
import LogOutIcon from "~icons/lucide/log-out";
import MoonIcon from "~icons/lucide/moon";
import SearchIcon from "~icons/lucide/search";
import ServerIcon from "~icons/lucide/server";
import SettingsIcon from "~icons/lucide/settings";
import ShieldIcon from "~icons/lucide/shield";

// useTheme reads the stored choice on mount and honours prefers-color-scheme;
// the hand-rolled toggle it replaces always resolved to dark on first click.
const { toggleTheme } = useTheme();
const route = useRoute();

// The balance falls while nobody clicks anything — a running instance burns by the
// hour — so the meter starts from the context call the SPA already made and is
// re-read on every navigation. Each read is one indexed lookup, never a ledger sum.
watch(() => userContext.ready, primeCreditSummary, { immediate: true });
watch(() => route.fullPath, refreshCreditSummary);

// `notify_owner` writes a desk alert this SPA never renders, and the
// notifications panel only polls when it is opened — so someone who clicked
// "Run in background" and walked to another screen would hear nothing. The
// event is already published to the bench's owner alone, so there is nothing
// to filter. Nothing else toasts a deploy line: the dialog only appends, and
// Lab detail reloads. Do not add a second toast anywhere.
const socket = useSocket();

function onDeployFinished(data) {
	if (data.type === "success") toast.success("Your lab is deployed.");
	else if (data.type === "error") toast.error("A deploy failed — open the lab to see why.");
}

onMounted(() => socket?.on("bench_deploy_log", onDeployFinished));
onUnmounted(() => socket?.off("bench_deploy_log", onDeployFinished));

function switchToDesk() {
	window.location.href = "/app";
}

function logout() {
	session.logout.submit();
}

// Everything that acts on the account rather than on a lab lives behind the
// sidebar header chevron — Settings included, so the nav stays object-shaped.
const accountMenu = computed(() => {
	const account = [];
	if (userContext.isAdmin) {
		account.push(
			{
				label: "Settings",
				icon: SettingsIcon,
				onClick: openSettings,
			},
			{
				label: "Switch to Desk",
				icon: LayoutDashboardIcon,
				onClick: switchToDesk,
			}
		);
	}
	account.push({ label: "Toggle theme", icon: MoonIcon, onClick: toggleTheme });
	return [
		{ group: "account", hideLabel: true, items: account },
		{
			group: "session",
			hideLabel: true,
			items: [{ label: "Log out", icon: LogOutIcon, onClick: logout }],
		},
	];
});

// The items above the nav proper: the two dialogs that belong to the account
// rather than to any screen. The balance used to sit here as a third chip and
// now lives in the sidebar footer, where a gauge fits — see CreditMeter.vue.
const utilityItems = computed(() => [
	{
		label: "Search",
		icon: SearchIcon,
		suffix: searchShortcut.value,
		dataTest: "nav-search",
		onClick: openSearch,
	},
	{
		label: "Notifications",
		icon: BellIcon,
		suffix: attentionCount.value ? String(attentionCount.value) : undefined,
		dataTest: "nav-notifications",
		onClick: toggleNotifications,
	},
]);

// Five flat items. Deploy and build history are reached from the objects they
// belong to, so the old Logs section is gone; Settings is in the header menu.
const NAV_ITEMS = [
	{
		label: "Overview",
		icon: LayoutDashboardIcon,
		to: "/",
		dataTest: "nav-overview",
		routes: ["Overview"],
	},
	{
		label: "Labs",
		icon: FlaskConicalIcon,
		to: "/labs",
		dataTest: "nav-labs",
		routes: ["Labs", "LabDetail", "NewLab", "BuildLogs"],
	},
	{
		label: "Templates",
		icon: LayoutTemplateIcon,
		to: "/labs/templates",
		dataTest: "nav-templates",
		routes: ["LabTemplates"],
		adminOnly: true,
	},
	{
		label: "Instances",
		icon: ServerIcon,
		to: "/bench-instances",
		dataTest: "nav-instances",
		routes: ["BenchInstances", "DeployLogs"],
	},
	{
		label: "Devices",
		icon: ShieldIcon,
		to: "/devices",
		dataTest: "nav-devices",
		routes: ["Devices"],
	},
];

const sections = computed(() => {
	const items = NAV_ITEMS.filter((item) => !item.adminOnly || userContext.isAdmin).map(
		(item) => ({
			...item,
			isActive: item.routes.includes(route.name),
		})
	);
	return [{ label: "", items }];
});

const breadcrumbs = computed(() => {
	const parent = { label: "BenchPress", route: { name: "Overview" } };
	const current = route.meta?.title;
	return current ? [parent, { label: current, route: route.path }] : [parent];
});
</script>
