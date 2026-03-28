<template>
	<div class="flex h-screen">
		<Sidebar :header="sidebarConfig.header" :sections="sidebarConfig.sections" />
		<div class="flex-1 overflow-auto bg-surface-white">
			<router-view />
		</div>
	</div>
</template>

<script setup>
import { Sidebar } from "frappe-ui";
import { reactive, computed, watchEffect } from "vue";
import { session } from "@/data/session";
import { userContext } from "@/data/userContext";

import ServerIcon from "~icons/lucide/server";
import FlaskConicalIcon from "~icons/lucide/flask-conical";
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

const sidebarConfig = reactive({
	header: {
		title: "Benchpress",
		subtitle: session.user || "",
		logo: "/assets/benchpress/images/logo/favicon.svg",
		menuItems: [],
	},
	sections: [],
});

watchEffect(() => {
	const isAdmin = userContext.isAdmin;

	const menuItems = [];
	if (isAdmin) {
		menuItems.push({
			label: "Switch to Desk",
			icon: LayoutDashboardIcon,
			onClick: switchToDesk,
		});
	}
	menuItems.push({ label: "Toggle Theme", icon: MoonIcon, onClick: toggleTheme });
	menuItems.push({ label: "Logout", icon: LogOutIcon, onClick: logout });
	sidebarConfig.header.menuItems = menuItems;

	const sections = [
		{
			label: "",
			items: [
				{ label: "Labs", icon: FlaskConicalIcon, to: "/labs" },
				{ label: "Bench Instances", icon: ServerIcon, to: "/bench-instances" },
				{ label: "VPN Devices", icon: ShieldIcon, to: "/devices" },
			],
		},
	];

	const logItems = [{ label: "Deploy Logs", icon: ScrollTextIcon, to: "/deploy-logs" }];
	if (isAdmin) {
		logItems.push({ label: "Build Logs", icon: HammerIcon, to: "/build-logs" });
	}
	sections.push({ label: "Logs", collapsible: true, items: logItems });

	if (isAdmin) {
		sections.push({
			label: "",
			items: [{ label: "Settings", icon: SettingsIcon, to: "/settings" }],
		});
	}

	sidebarConfig.sections = sections;
});
</script>
