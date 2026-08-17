import { describe, expect, it } from "vitest";
import { NEUTRAL_TONE, TONES, labelFor, themeFor, toneFor } from "./statusThemes";

// Every option of every status enum in the product, verbatim from the
// DocType JSON — including the leading empty string on container_health,
// which is a real persisted value for a bench that has never been polled.
const ENUMS = {
	"Lab.status": {
		Draft: "gray",
		Building: "blue",
		Ready: "green",
		Error: "red",
	},
	"Bench Instance.status": {
		Draft: "gray",
		Deploying: "blue",
		Running: "green",
		Stopped: "gray",
		Error: "red",
	},
	"Bench Instance.container_health": {
		"": "gray",
		Healthy: "green",
		Unhealthy: "red",
		Unknown: "gray",
	},
	"Bench Site.status": {
		Creating: "blue",
		Active: "green",
		Inactive: "gray",
		Error: "red",
	},
	"Database Server.status": {
		Pending: "gray",
		Active: "green",
		Stopped: "gray",
		Error: "red",
	},
	"VPN Peer.status": {
		Pending: "gray",
		Active: "green",
		Stale: "orange",
		Disabled: "gray",
		Revoked: "red",
	},
	"Deploy Log.log_type": {
		info: "blue",
		success: "green",
		error: "red",
		warning: "orange",
	},
};

describe("status themes", () => {
	for (const [enumName, options] of Object.entries(ENUMS)) {
		for (const [status, tone] of Object.entries(options)) {
			it(`maps ${enumName} "${status}" to ${tone}`, () => {
				expect(toneFor(status)).toBe(tone);
				expect(themeFor(status)).toBe(TONES[tone]);
			});
		}
	}

	it("degrades an unrecognised value to grey instead of throwing", () => {
		for (const status of ["Exploded", "  ", null, undefined, 42]) {
			expect(toneFor(status)).toBe(NEUTRAL_TONE);
		}
	});

	it("labels a never-polled container_health as Unknown", () => {
		expect(labelFor("")).toBe("Unknown");
		expect(labelFor(null)).toBe("Unknown");
		expect(labelFor(" Running ")).toBe("Running");
	});

	it("corrects only the blue badge, which frappe-ui renders as a solid fill", () => {
		expect(TONES.blue.badgeClass).toContain("bg-surface-blue-1");
		for (const tone of ["green", "orange", "red", "gray"]) {
			expect(TONES[tone].badgeClass).toBe("");
		}
	});
});
