import { openSettings } from "@/data/benchpressSettings";
import { userResource } from "@/data/user";
import { createRouter, createWebHistory } from "vue-router";
import { session } from "./data/session";
import { userContext, waitForUserContext } from "./data/userContext";

const ADMIN_ONLY_ROUTES = new Set(["NewLab", "LabTemplates", "Settings", "BuildLogs"]);

// `meta.title` is the current crumb in the header breadcrumb.
const routes = [
	{
		path: "/",
		name: "Overview",
		meta: { title: "Overview" },
		component: () => import("@/pages/Overview.vue"),
	},
	{
		path: "/labs",
		name: "Labs",
		meta: { title: "Labs" },
		component: () => import("@/pages/Labs.vue"),
	},
	{
		path: "/bench-instances",
		name: "BenchInstances",
		meta: { title: "Instances" },
		component: () => import("@/pages/BenchInstances.vue"),
	},
	{
		path: "/labs/new",
		name: "NewLab",
		meta: { title: "New lab" },
		component: () => import("@/pages/NewLab.vue"),
	},
	{
		path: "/labs/templates",
		name: "LabTemplates",
		meta: { title: "Templates" },
		component: () => import("@/pages/LabTemplates.vue"),
	},
	{
		path: "/labs/:labId",
		name: "LabDetail",
		meta: { title: "Lab detail" },
		component: () => import("@/pages/LabDetail.vue"),
	},
	{
		path: "/deploy-logs",
		name: "DeployLogs",
		meta: { title: "Deploy history" },
		component: () => import("@/pages/DeployLogs.vue"),
	},
	{
		path: "/build-logs",
		name: "BuildLogs",
		meta: { title: "Build history" },
		component: () => import("@/pages/BuildLogs.vue"),
	},
	{
		path: "/devices",
		name: "Devices",
		meta: { title: "Devices" },
		component: () => import("@/pages/Devices.vue"),
	},
	{
		// Settings is a dialog, not a screen. The route survives so old links
		// and bookmarks still work: it opens the dialog over Overview, and the
		// dialog puts the URL back on Overview when it closes.
		path: "/settings",
		name: "Settings",
		meta: { title: "Settings" },
		component: () => import("@/pages/Overview.vue"),
		beforeEnter() {
			openSettings();
		},
	},
	{
		path: "/:pathMatch(.*)*",
		name: "NotFound",
		meta: { title: "Not found" },
		component: () => import("@/pages/NotFound.vue"),
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
	} else if (ADMIN_ONLY_ROUTES.has(to.name)) {
		await waitForUserContext().catch(() => {});
		if (!userContext.isAdmin) {
			next({ name: "Labs" });
		} else {
			next();
		}
	} else {
		next();
	}
});

export default router;
