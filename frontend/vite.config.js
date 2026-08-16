import path from "node:path";
import vue from "@vitejs/plugin-vue";
import frappeui from "frappe-ui/vite";
import { defineConfig } from "vite";

// https://vitejs.dev/config/
export default defineConfig({
	plugins: [
		frappeui({
			frappeProxy: true,
			jinjaBootData: true,
			lucideIcons: true,
			buildConfig: {
				outDir: "../benchpress/public/frontend",
				indexHtmlPath: "../benchpress/www/frontend.html",
				emptyOutDir: true,
				// A 3.2 MB .js.map used to ship to every browser. This block is the
				// only place outDir/emptyOutDir/sourcemap are declared — the plugin
				// writes them into `build`, so repeating them below only invited drift.
				sourcemap: false,
			},
		}),
		vue(),
	],
	build: {
		chunkSizeWarningLimit: 1500,
		target: "es2015",
	},
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "src"),
			"tailwind.config.js": path.resolve(__dirname, "tailwind.config.js"),
		},
	},
	optimizeDeps: {
		include: ["feather-icons", "highlight.js/lib/core"],
		exclude: ["frappe-ui"],
	},
	server: {
		allowedHosts: true,
	},
});
