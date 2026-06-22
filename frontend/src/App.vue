<template>
	<FrappeUIProvider>
		<div class="flex h-screen">
			<Sidebar :header="headerConfig" :sections="sections" />
			<div class="flex-1 overflow-auto bg-surface-white">
				<router-view />
			</div>
		</div>
	</FrappeUIProvider>
</template>

<script setup>
import { FrappeUIProvider, Sidebar } from "frappe-ui";
import { computed } from "vue";
import { session } from "@/data/session";
import { userContext } from "@/data/userContext";

import ServerIcon from "~icons/lucide/server";
import FlaskConicalIcon from "~icons/lucide/flask-conical";
import LayoutTemplateIcon from "~icons/lucide/layout-template";
import ScrollTextIcon from "~icons/lucide/scroll-text";
import HammerIcon from "~icons/lucide/hammer";
import ShieldIcon from "~icons/lucide/shield";
import SettingsIcon from "~icons/lucide/settings";
import LayoutDashboardIcon from "~icons/lucide/layout-dashboard";
import MoonIcon from "~icons/lucide/moon";
import LogOutIcon from "~icons/lucide/log-out";

function switchToDesk() {
	window.location.href = "/app";
}

function toggleTheme() {
	const current = document.documentElement.getAttribute("data-theme");
	document.documentElement.setAttribute("data-theme", current === "dark" ? "light" : "dark");
}

function logout() {
	session.logout.submit();
}

const headerConfig = computed(() => {
	const menuItems = [];
	if (userContext.isAdmin) {
		menuItems.push({
			label: "Switch to Desk",
			icon: LayoutDashboardIcon,
			onClick: switchToDesk,
		});
	}
	menuItems.push({ label: "Toggle Theme", icon: MoonIcon, onClick: toggleTheme });
	menuItems.push({ label: "Logout", icon: LogOutIcon, onClick: logout });

	return {
		title: "Benchpress",
		subtitle: session.user || "",
		logo: "/assets/benchpress/images/logo/favicon.svg",
		menuItems,
	};
});

const sections = computed(() => {
	const labItems = [{ label: "Labs", icon: FlaskConicalIcon, to: "/labs" }];
	if (userContext.isAdmin) {
		labItems.push({ label: "Templates", icon: LayoutTemplateIcon, to: "/labs/templates" });
	}
	labItems.push(
		{ label: "Bench Instances", icon: ServerIcon, to: "/bench-instances" },
		{ label: "VPN Devices", icon: ShieldIcon, to: "/devices" }
	);

	const items = [{ label: "", items: labItems }];

	const logItems = [{ label: "Deploy Logs", icon: ScrollTextIcon, to: "/deploy-logs" }];
	if (userContext.isAdmin) {
		logItems.push({ label: "Build Logs", icon: HammerIcon, to: "/build-logs" });
	}
	items.push({ label: "Logs", collapsible: true, items: logItems });

	if (userContext.isAdmin) {
		items.push({
			label: "",
			items: [{ label: "Settings", icon: SettingsIcon, to: "/settings" }],
		});
	}

	return items;
});
</script>
