import { describe, expect, it } from "vitest";
import { ACTIVE, EXPIRING, MINUTE, NONE, SECOND, leaseFor } from "./lease";

// The module is pure, so a test supplies both ends of the subtraction.
const NOW = 1_787_654_321_000;
const at = (msFromNow) => leaseFor(NOW + msFromNow, NOW);

describe("the countdown label", () => {
	it("does not change format at the minute boundary", () => {
		expect(at(29 * MINUTE + 59 * SECOND).label).toBe("29:59");
		expect(at(61 * SECOND).label).toBe("01:01");
		expect(at(60 * SECOND).label).toBe("01:00");
		expect(at(59 * SECOND).label).toBe("00:59");
	});

	it("rounds up, so a lease with time left never reads 00:00", () => {
		expect(at(1).label).toBe("00:01");
		expect(at(999).label).toBe("00:01");
		expect(at(0).label).toBe("00:00");
	});

	it("clamps a passed deadline instead of counting negative", () => {
		expect(at(-14 * SECOND).label).toBe("00:00");
		expect(at(-3 * 60 * MINUTE).label).toBe("00:00");
	});

	it("switches to coarse units once the seconds stop mattering", () => {
		expect(at(2 * 60 * MINUTE + 5 * MINUTE).label).toBe("2h 5m");
		expect(at(7 * 24 * 60 * MINUTE - SECOND).label).toBe("6d 23h");
	});
});

describe("the state a lease is in", () => {
	it("is expiring the moment the deadline passes, and stays clamped", () => {
		expect(at(SECOND).state).toBe(ACTIVE);
		expect(at(0).state).toBe(EXPIRING);
		expect(at(-SECOND).state).toBe(EXPIRING);
	});

	it("renders nothing for a row that has never held a lease", () => {
		// Every Bench Instance that predates this feature has an empty deadline.
		for (const empty of [null, undefined, 0, ""]) {
			const lease = leaseFor(empty, NOW);
			expect(lease.state).toBe(NONE);
			expect(lease.label).toBe("");
		}
	});
});

describe("how often the widget asks to be repainted", () => {
	it("ticks once a second only while the seconds are on screen", () => {
		expect(at(30 * MINUTE).tickPeriod).toBe(SECOND);
		expect(at(59 * MINUTE).tickPeriod).toBe(SECOND);
	});

	it("drops to a minute for a lease measured in days", () => {
		expect(at(7 * 24 * 60 * MINUTE).tickPeriod).toBe(MINUTE);
		expect(at(3 * 60 * MINUTE).tickPeriod).toBe(MINUTE);
	});

	it("schedules no tick at all for a bench with no lease", () => {
		expect(leaseFor(null, NOW).tickPeriod).toBe(0);
	});
});

describe("the tone the countdown carries", () => {
	it("warns before it ends and never before that", () => {
		expect(at(30 * MINUTE).tone).toBe("green");
		expect(at(4 * MINUTE).tone).toBe("orange");
		expect(at(-SECOND).tone).toBe("red");
	});
});
