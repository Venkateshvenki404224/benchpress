import { describe, expect, it } from "vitest";
import { burnLabel, creditLabel, rateLabel, signedCreditLabel } from "./credits";

describe("creditLabel", () => {
	it("rounds the accounting precision down to something readable", () => {
		expect(creditLabel(39.983333)).toBe("39.98");
		expect(creditLabel(0.0166667)).toBe("0.02");
	});

	it("keeps no decimals on a whole number", () => {
		expect(creditLabel(40)).toBe("40");
		expect(creditLabel(40.000001)).toBe("40");
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
