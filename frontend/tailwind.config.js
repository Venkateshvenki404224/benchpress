import frappeUIPreset from "frappe-ui/tailwind";

// Only what the design handoff needs on top of the Espresso preset: the type
// steps the preset has no name for (11.5, 12.5, 19, 22px — 11px is `2xs`,
// 12px `xs`, 13px `sm`), the two radii it lacks (dialogs are `rounded-lg`,
// pills `rounded-full`), the four named shadows, the monospace stack and the
// only two animations the design permits. No colour is redefined here.
export default {
	presets: [frappeUIPreset],
	content: [
		"./index.html",
		"./src/**/*.{vue,js,ts,jsx,tsx}",
		"./node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}",
	],
	theme: {
		extend: {
			fontSize: {
				meta: ["11.5px", { lineHeight: "1.3", letterSpacing: "0.01em" }],
				body: ["12.5px", { lineHeight: "1.35", letterSpacing: "0.01em" }],
				title: ["19px", { lineHeight: "1.25", letterSpacing: "-0.02em" }],
				stat: ["22px", { lineHeight: "1.15", letterSpacing: "-0.02em" }],
			},
			borderRadius: {
				control: "7px",
				card: "11px",
			},
			boxShadow: {
				dropdown: "0 8px 24px rgba(0, 0, 0, 0.12)",
				dialog: "0 20px 46px rgba(0, 0, 0, 0.2)",
				"card-hover": "0 2px 8px rgba(0, 0, 0, 0.06)",
				"nav-active": "0 1px 2px rgba(0, 0, 0, 0.06)",
			},
			fontFamily: {
				mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
			},
			keyframes: {
				"step-spin": { to: { transform: "rotate(360deg)" } },
				"vpn-pulse": {
					"0%, 100%": { opacity: "1" },
					"50%": { opacity: "0.35" },
				},
			},
			animation: {
				"step-spin": "step-spin 0.8s linear infinite",
				"vpn-pulse": "vpn-pulse 1.8s ease-in-out infinite",
			},
		},
	},
	plugins: [],
};
