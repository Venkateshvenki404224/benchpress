import { describe, expect, it } from "vitest";
import { burnLabel, creditLabel, creditMeter, rateLabel, signedCreditLabel } from "./credits";

describe("creditLabel", () => {
	it("rounds the accounting precision down to something readable", () => {
		expect(creditLabel(39.983333)).toBe("39.98");
		expect(creditLabel(0.0166667)).toBe("0.02");
	});

	it("keeps no decimals on a whole number", () => {
		expect(creditLabel(40)).toBe("40");
		expect(creditLabel(40.000001)).toBe("40");
	});

	it("groups a figure the meter renders at heading size", () => {
		expect(creditLabel(1480)).toBe("1,480");
		expect(creditLabel(1480.5)).toBe("1,480.50");
	});

	it("reads a missing balance as zero rather than NaN", () => {
		expect(creditLabel(null)).toBe("0");
		expect(creditLabel(undefined)).toBe("0");
		expect(creditLabel("not a number")).toBe("0");
	});
});

describe("signedCreditLabel", () => {
	it("signs the way a statement signs", () => {
		expect(signedCreditLabel(200)).toBe("+200");
		expect(signedCreditLabel(-3.5)).toBe("−3.50");
	});

	it("leaves a zero row unsigned — a start row spends nothing", () => {
		expect(signedCreditLabel(0)).toBe("0");
	});
});

describe("rateLabel", () => {
	it("names the unit the price is quoted in", () => {
		expect(rateLabel(2)).toBe("2 credits/hr");
		expect(rateLabel(1.5)).toBe("1.50 credits/hr");
		expect(rateLabel(0)).toBe("0 credits/hr");
	});
});

describe("burnLabel", () => {
	it("explains a falling balance while something runs", () => {
		expect(burnLabel(1.5)).toBe("Burning 1.50 credits/hr");
	});

	it("says nothing when nothing is running", () => {
		expect(burnLabel(0)).toBe("");
		expect(burnLabel(null)).toBe("");
	});
});

describe("creditMeter", () => {
	it("gauges what is left of the allocation", () => {
		const meter = creditMeter(34, 40);
		expect(meter.value).toBe(85);
		expect(meter.tone).toBe("green");
		expect(meter.label).toBe("34 of 40 credits left");
	});

	it("warns once the tank is nearly empty", () => {
		expect(creditMeter(7, 40).tone).toBe("orange");
		expect(creditMeter(8, 40).tone).toBe("green");
	});

	it("reads an empty or suspended account as a problem", () => {
		expect(creditMeter(0, 40).tone).toBe("red");
		expect(creditMeter(-3, 40).tone).toBe("red");
		expect(creditMeter(34, 40, true).tone).toBe("red");
	});

	it("has nothing to gauge before anything is allocated", () => {
		const meter = creditMeter(0, 0);
		expect(meter.value).toBe(0);
		expect(meter.tone).toBe("gray");
		expect(meter.label).toBe("No credits allocated yet");
	});

	it("never overfills when an adjustment puts the balance above the allocation", () => {
		expect(creditMeter(50, 40).value).toBe(100);
	});

	it("reads a missing summary as an empty gauge rather than NaN", () => {
		expect(creditMeter(undefined, null).value).toBe(0);
		expect(creditMeter("not a number", 40).value).toBe(0);
	});
});
