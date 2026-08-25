import { describe, expect, it } from "vitest";
import {
	ACTIVE,
	EXPIRING,
	MINUTE,
	NONE,
	REDEPLOY,
	RENEW,
	SECOND,
	applyPush,
	graceFor,
	leaseFor,
} from "./lease";

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

describe("applying a renewal push", () => {
	const held = { expiresAtTs: 1_787_654_400, revision: 2000 };

	it("writes one field, so the countdown is derived rather than restarted", () => {
		const next = applyPush(held, { expires_at_ts: 1_787_656_200, revision: 3000 });
		expect(next).toEqual({ expiresAtTs: 1_787_656_200, revision: 3000 });
	});

	it("drops a push older than the one already held", () => {
		expect(applyPush(held, { expires_at_ts: 1, revision: 1000 })).toBe(held);
		expect(applyPush(held, { expires_at_ts: 1, revision: 2000 })).toBe(held);
	});

	it("takes the first push on a tab that holds nothing yet", () => {
		const next = applyPush(null, { expires_at_ts: 1_787_656_200, revision: 3000 });
		expect(next).toEqual({ expiresAtTs: 1_787_656_200, revision: 3000 });
	});

	it("ignores a push carrying no revision, which cannot be ordered", () => {
		expect(applyPush(held, { expires_at_ts: 1_787_656_200 })).toBe(held);
		expect(applyPush(held, null)).toBe(held);
	});

	it("carries an expiry through as the cleared deadline it is", () => {
		const next = applyPush(held, { expires_at_ts: 0, revision: 3000 });
		expect(next).toEqual({ expiresAtTs: null, revision: 3000 });
	});
});

describe("the grace window after a lease ends", () => {
	const grace = (msFromNow) => graceFor(NOW + msFromNow, NOW);

	it("counts down through the same clock the lease used", () => {
		expect(grace(90 * MINUTE).label).toBe("1h 30m");
		expect(grace(45 * SECOND).label).toBe("00:45");
	});

	it("offers Renew while the container is still there", () => {
		expect(grace(2 * MINUTE).action).toBe(RENEW);
		expect(grace(2 * 24 * 60 * MINUTE).action).toBe(RENEW);
	});

	it("changes the call to action to Redeploy once grace ends", () => {
		expect(grace(0).action).toBe(REDEPLOY);
		expect(grace(-SECOND).action).toBe(REDEPLOY);
		expect(grace(-30 * 24 * 60 * MINUTE).action).toBe(REDEPLOY);
	});

	it("keeps Renew on offer when nothing reaps the bench at all", () => {
		expect(graceFor(null, NOW).action).toBe(RENEW);
		expect(graceFor(null, NOW).label).toBe("");
	});
});
