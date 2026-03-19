import { createRouter, createWebHistory } from "vue-router";
import authRoutes from "./auth";

const routes = [
	{
		path: "/",
		name: "Labs",
		component: () => import("@/pages/LabsPage.vue"),
	},
	{
		path: "/benches",
		name: "Benches",
		component: () => import("@/pages/BenchListPage.vue"),
	},
	{
		path: "/deploy/:lab",
		name: "Deploy",
		component: () => import("@/pages/DeployPage.vue"),
	},
	{
		path: "/bench/:id",
		name: "BenchDetail",
		component: () => import("@/pages/BenchDetailPage.vue"),
	},
	...authRoutes,
];

const router = createRouter({
	history: createWebHistory("/dashboard"),
	routes,
});

export default router;
