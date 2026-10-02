import { describe, expect, it } from "vitest";
import { installedApps, markApp, resourceChips } from "./labSpecs";

describe("installedApps", () => {
	it("reads a bare bench as Frappe", () => {
		expect(installedApps([])).toEqual(["frappe"]);
	});
});

describe("markApp", () => {
	it("picks the first app that is not Frappe", () => {
		expect(markApp(["frappe", "erpnext"])).toBe("erpnext");
	});

	it("falls back to the Frappe mark on a bare bench", () => {
		expect(markApp([])).toBe("frappe");
	});
});

describe("resourceChips", () => {
	it("reads memory, then CPU", () => {
		expect(resourceChips({ memory_limit: "512m", cpu_cores: 2 })).toEqual([
			"512 MB",
			"2 vCPU",
		]);
	});
});
