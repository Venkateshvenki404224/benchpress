import { userResource } from "@/data/user";
import { createRouter, createWebHistory } from "vue-router";
import { session } from "./data/session";

const routes = [
	{
		path: "/",
		name: "Home",
		component: () => import("@/pages/Labs.vue"),
	},
	{
		path: "/labs",
		name: "Labs",
		component: () => import("@/pages/Labs.vue"),
	},
	{
		path: "/bench-instances",
		name: "BenchInstances",
		component: () => import("@/pages/BenchInstances.vue"),
	},
	{
		path: "/labs/new",
		name: "NewLab",
		component: () => import("@/pages/NewLab.vue"),
	},
	{
		path: "/labs/:labId",
		name: "LabDetail",
		component: () => import("@/pages/LabDetail.vue"),
	},
	{
		path: "/deploy-logs",
		name: "DeployLogs",
		component: () => import("@/pages/DeployLogs.vue"),
	},
	{
		path: "/build-logs",
		name: "BuildLogs",
		component: () => import("@/pages/BuildLogs.vue"),
	},
	{
		path: "/devices",
		name: "Devices",
		component: () => import("@/pages/Devices.vue"),
	},
	{
		path: "/settings",
		name: "Settings",
		component: () => import("@/pages/Settings.vue"),
	},
];

const router = createRouter({
	history: createWebHistory("/frontend"),
	routes,
});

router.beforeEach(async (to, from, next) => {
	let isLoggedIn = session.isLoggedIn;
	try {
		await userResource.promise;
	} catch (error) {
		isLoggedIn = false;
	}

	if (!isLoggedIn) {
		window.location.href = "/login";
	} else {
		next();
	}
});

export default router;
