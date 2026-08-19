import { describe, expect, it } from "vitest";
import { ALL, matches, optionsFrom } from "./filters";

describe("optionsFrom", () => {
	it("leads with an all option and sorts the rest", () => {
		const options = optionsFrom("Version", ["version-16", "version-15", "version-16"]);
		expect(options).toEqual([
			{ label: "Version: all", value: ALL },
			{ label: "version-15", value: "version-15" },
			{ label: "version-16", value: "version-16" },
		]);
	});

	it("drops blank values", () => {
		const options = optionsFrom("Owner", ["", null, undefined, "admin@example.com"]);
		expect(options).toEqual([
			{ label: "Owner: all", value: ALL },
			{ label: "admin@example.com", value: "admin@example.com" },
		]);
	});

	it("labels each option through the given labelFor, keyed on the raw value", () => {
		const options = optionsFrom("Apps", ["erpnext", "hrms"], (value) => value.toUpperCase());
		expect(options).toEqual([
			{ label: "Apps: all", value: ALL },
			{ label: "ERPNEXT", value: "erpnext" },
			{ label: "HRMS", value: "hrms" },
		]);
	});
});

describe("matches", () => {
	it("accepts anything when the filter is ALL", () => {
		expect(matches("Running", ALL)).toBe(true);
		expect(matches(undefined, ALL)).toBe(true);
	});

	it("otherwise requires an exact match", () => {
		expect(matches("Running", "Running")).toBe(true);
		expect(matches("Running", "Stopped")).toBe(false);
	});
});
