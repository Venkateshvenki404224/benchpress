import { describe, expect, it } from "vitest";
import {
	MEMORY_WARNING_PERCENT,
	NEVER_CHECKED,
	NOT_RUNNING_NOTE,
	NO_READING,
	cpuMeter,
	healthCaption,
	memoryMeter,
} from "./containerStats";

const LAB = { cpu_cores: 2, memory_limit: "512m" };
// `get_container_stats` writes zeros on failure and `stats_collector` leaves the
// last reading behind when a container stops, so a stopped bench can carry any
// numbers at all. Neither may be reported as a live measurement.
const STOPPED = { status: "Stopped", cpu_usage: 42, memory_usage: 88 };
const RUNNING = { status: "Running", cpu_usage: 12.4, memory_usage: 34.6 };
const HOT = { status: "Running", cpu_usage: 5, memory_usage: MEMORY_WARNING_PERCENT + 1 };

describe("a container that is not running", () => {
	it("reports em-dashes and says why, rather than zeros", () => {
		for (const bench of [STOPPED, { status: "Draft" }, { status: "Error" }, {}]) {
			for (const meter of [cpuMeter(bench, LAB), memoryMeter(bench, LAB)]) {
				expect(meter.label).toBe(NO_READING);
				expect(meter.note).toBe(NOT_RUNNING_NOTE);
				expect(meter.value).toBe(0);
				expect(meter.tone).toBe("gray");
			}
		}
	});
});

describe("a running container", () => {
	it("reports CPU against the lab's core quota", () => {
		expect(cpuMeter(RUNNING, LAB)).toMatchObject({
			label: "12%",
			note: "quota 2 vCPU",
			value: 12,
			tone: "green",
		});
	});

	it("reports memory against the lab's limit", () => {
		expect(memoryMeter(RUNNING, LAB)).toMatchObject({
			label: "35%",
			note: "of 512 MB limit",
			value: 35,
			tone: "green",
		});
	});

	it("turns memory amber once it runs hot", () => {
		expect(memoryMeter(HOT, LAB).tone).toBe("orange");
		expect(cpuMeter(HOT, LAB).tone).toBe("green");
	});
});

describe("healthCaption", () => {
	it("says a never-polled bench was never checked", () => {
		expect(healthCaption(null)).toBe(NEVER_CHECKED);
		expect(healthCaption(undefined)).toBe(NEVER_CHECKED);
	});

	it("ages the reading in the one unit worth reading", () => {
		expect(healthCaption(30)).toBe("checked 30s ago");
		expect(healthCaption(240)).toBe("checked 4m ago");
		expect(healthCaption(7200)).toBe("checked 2h ago");
	});
});
