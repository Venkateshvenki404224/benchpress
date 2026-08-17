import frappeUIPreset from "frappe-ui/tailwind";

// Only what the design handoff needs on top of the Espresso preset: the type
// scale, the two radii it lacks (dialogs are `rounded-lg`, pills
// `rounded-full`), the four named shadows, the monospace stack and the only two
// animations the design permits. No colour is redefined here.
//
// The whole scale lives here, preset steps included, because the Espresso
// defaults (2xs 11px, base 14px) read too small on a desktop console. Every
// step is lifted ~1px and the paragraph steps get looser leading; overriding
// the four token names the app already uses moves all 150-odd call sites at
// once. Weights and tracking stay at the preset's values.
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
				"2xs": ["12px", { lineHeight: "1.2", letterSpacing: "0.01em", fontWeight: "420" }],
				xs: ["13px", { lineHeight: "1.2", letterSpacing: "0.015em", fontWeight: "420" }],
				sm: ["14px", { lineHeight: "1.2", letterSpacing: "0.015em", fontWeight: "420" }],
				base: ["15px", { lineHeight: "1.2", letterSpacing: "0.015em", fontWeight: "420" }],
				lg: ["17px", { lineHeight: "1.2", letterSpacing: "0.01em", fontWeight: "400" }],
				meta: ["12.5px", { lineHeight: "1.3", letterSpacing: "0.01em" }],
				body: ["14px", { lineHeight: "1.45", letterSpacing: "0.01em" }],
				title: ["22px", { lineHeight: "1.25", letterSpacing: "-0.02em" }],
				stat: ["27px", { lineHeight: "1.15", letterSpacing: "-0.02em" }],
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
