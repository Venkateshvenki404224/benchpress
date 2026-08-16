import { describe, expect, it } from "vitest";
import { NEVER_MEASURED_NOTE, STALE_AFTER_SECONDS, percent, usageFor } from "./benchUsage";
import { labelFor, toneFor } from "./statusThemes";

const IDLE = { cpu_usage: 0, memory_usage: 0 };
const BUSY = { cpu_usage: 18.4, memory_usage: 34.6 };

const FRESH = 30;
const STALE = STALE_AFTER_SECONDS + 1;
const NEVER = null;

describe("the two status axes of an Instances row", () => {
	// A bench's own state and what Docker reports about its container are
	// independent — the table renders each as its own badge.
	it("renders a Running bench that is Unhealthy as green and red", () => {
		expect(toneFor("Running")).toBe("green");
		expect(toneFor("Unhealthy")).toBe("red");
	});

	it("never leaves the health cell blank for a bench that was never polled", () => {
		// container_health's leading enum option is a real persisted empty string.
		expect(labelFor("")).toBe("Unknown");
		expect(toneFor("")).toBe("gray");
	});
});

describe("usageFor", () => {
	it("distinguishes a genuinely idle bench from a stale reading", () => {
		const idle = usageFor(IDLE, FRESH);
		const stale = usageFor(IDLE, STALE);

		expect(idle.label).toBe("0% CPU · 0% mem");
		expect(idle.note).toBe("");
		expect(stale.label).toBe("—");
		expect(stale.note).toMatch(/^stale — last read/);
		expect(stale).not.toEqual(idle);
	});

	it("distinguishes a bench that was never measured from one reading zero", () => {
		const never = usageFor(IDLE, NEVER);

		expect(never.measured).toBe(false);
		expect(never.label).toBe("—");
		expect(never.note).toBe(NEVER_MEASURED_NOTE);
		expect(usageFor(IDLE, FRESH).measured).toBe(true);
	});

	it("reports both percentages when the reading is trustworthy", () => {
		const usage = usageFor(BUSY, FRESH);

		expect(usage.label).toBe("18% CPU · 35% mem");
		expect(usage.value).toBe(18);
		expect(usage.tone).toBe("green");
	});

	it("keeps the bar neutral and empty whenever the reading is not trustworthy", () => {
		for (const age of [STALE, NEVER]) {
			const usage = usageFor(BUSY, age);
			expect(usage.value).toBe(0);
			expect(usage.tone).toBe("gray");
		}
	});

	it("keeps an idle bar neutral so zero never reads as activity", () => {
		expect(usageFor(IDLE, FRESH).tone).toBe("gray");
	});
});

describe("percent", () => {
	it("rounds, clamps and survives a missing stat", () => {
		expect(percent(18.4)).toBe(18);
		expect(percent(-5)).toBe(0);
		expect(percent(140)).toBe(100);
		expect(percent(undefined)).toBe(0);
		expect(percent(null)).toBe(0);
	});
});
