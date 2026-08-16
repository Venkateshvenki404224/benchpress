<template>
	<FrappeUIProvider>
		<div class="flex h-screen">
			<Sidebar :header="headerConfig" :sections="sections">
				<template #sidebar-item="{ item, isCollapsed }">
					<SidebarItem
						:label="item.label"
						:icon="item.icon"
						:to="item.to"
						:isActive="item.isActive"
						:data-test="item.dataTest"
					/>
				</template>
				<template #footer-items>
					<SidebarItem
						v-if="userContext.isAdmin"
						label="Settings"
						:icon="SettingsIcon"
						to="/settings"
						:isActive="route.name === 'Settings'"
						data-test="nav-settings"
					/>
				</template>
			</Sidebar>

			<div class="flex min-w-0 flex-1 flex-col">
				<header
					class="flex h-[50px] flex-none items-center gap-3 border-b border-outline-gray-1 px-5"
					data-test="app-header"
				>
					<Breadcrumbs :items="breadcrumbs" />
					<div class="ml-auto flex items-center gap-2.5">
						<!-- Phase 2 fills this slot with CommandPalette. -->
						<slot name="search" />
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
						<Dropdown :options="accountMenu" placement="right">
							<Button variant="subtle" data-test="account-menu">
								<template #icon><EllipsisIcon class="size-4" /></template>
							</Button>
						</Dropdown>
					</div>
				</header>

				<main class="flex-1 overflow-auto bg-surface-gray-1">
					<router-view />
				</main>
			</div>
		</div>
	</FrappeUIProvider>
</template>

<script setup>
import { session } from "@/data/session";
import { userContext } from "@/data/userContext";
import { vpnStatus } from "@/data/vpnStatus";
import {
	Breadcrumbs,
	Button,
	Dropdown,
	FrappeUIProvider,
	Sidebar,
	SidebarItem,
	useTheme,
} from "frappe-ui";
import { computed } from "vue";
import { useRoute } from "vue-router";

import EllipsisIcon from "~icons/lucide/ellipsis";
import FlaskConicalIcon from "~icons/lucide/flask-conical";
import LayoutDashboardIcon from "~icons/lucide/layout-dashboard";
import LayoutTemplateIcon from "~icons/lucide/layout-template";
import LogOutIcon from "~icons/lucide/log-out";
import MoonIcon from "~icons/lucide/moon";
import ServerIcon from "~icons/lucide/server";
import SettingsIcon from "~icons/lucide/settings";
import ShieldIcon from "~icons/lucide/shield";

// useTheme reads the stored choice on mount and honours prefers-color-scheme;
// the hand-rolled toggle it replaces always resolved to dark on first click.
const { toggleTheme } = useTheme();
const route = useRoute();

function switchToDesk() {
	window.location.href = "/app";
}

function logout() {
	session.logout.submit();
}

const headerConfig = computed(() => ({
	title: "BenchPress",
	subtitle: session.user || "",
	logo: "/assets/benchpress/images/logo/favicon.svg",
	menuItems: [],
}));

// "Keyboard shortcuts" joins this menu in phase 2, with the ⌘K palette that
// is the only shortcut to list.
const accountMenu = computed(() => {
	const items = [];
	if (userContext.isAdmin) {
		items.push({
			label: "Switch to Desk",
			icon: LayoutDashboardIcon,
			onClick: switchToDesk,
		});
	}
	items.push(
		{ label: "Toggle theme", icon: MoonIcon, onClick: toggleTheme },
		{ label: "Log out", icon: LogOutIcon, onClick: logout }
	);
	return items;
});

// Five flat items. Deploy and build history are reached from the objects they
// belong to, so the old Logs section is gone; Settings sits in the footer.
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
