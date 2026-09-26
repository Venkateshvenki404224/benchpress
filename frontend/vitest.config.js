import path from "node:path";
import vue from "@vitejs/plugin-vue";
import Icons from "unplugin-icons/vite";
import { defineConfig } from "vitest/config";

export default defineConfig({
	plugins: [vue(), Icons({ compiler: "vue3" })],
	test: {
		environment: "jsdom",
		include: ["src/**/*.spec.js"],
	},
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "src"),
		},
	},
});
