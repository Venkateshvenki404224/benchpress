import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { onResync, recordSkew, resetClock, serverNow, skew, subscribe } from "./clock";
import { leaseFor } from "./lease";

const START = 1_787_654_321_000;
const SECOND = 1000;

beforeEach(() => {
	vi.useFakeTimers();
	vi.setSystemTime(START);
	resetClock();
});

afterEach(() => {
	resetClock();
	vi.useRealTimers();
});

describe("recordSkew", () => {
	it("charges the browser only half the round trip, not all of it", () => {
		// Ten seconds ahead, 400 ms round trip. Simplifying this back to
		// `serverNow - Date.now()` books the whole response leg as skew.
		const t0 = START;
		const t1 = START + 400;
		const serverStamp = START + 10 * SECOND + 200;

		recordSkew(t0, serverStamp, t1);

		expect(Math.abs(skew() - 10 * SECOND)).toBeLessThan(200);
	});

	it("re-anchors on every reading rather than averaging into the old one", () => {
		recordSkew(START, START + 10 * SECOND, START);
		recordSkew(START, START - 4 * SECOND, START);
		expect(skew()).toBe(-4 * SECOND);
	});

	it("reads zero skew before anything has been recorded", () => {
		expect(skew()).toBe(0);
		expect(serverNow()).toBe(START);
	});
});

describe("a countdown read through the corrected clock", () => {
	it("shows what the server would show, not what the browser thinks", () => {
		// The browser is ten seconds behind. The lease ends at server 15 s.
		recordSkew(START, START + 10 * SECOND, START);
		const deadline = START + 15 * SECOND;

		expect(leaseFor(deadline, serverNow()).label).toBe("00:05");
		expect(leaseFor(deadline, Date.now()).label).toBe("00:15");
	});
});

describe("the shared tick", () => {
	it("delivers the corrected time on a wall-clock boundary", () => {
		recordSkew(START, START + 10 * SECOND, START);
		const seen = [];
		subscribe((now) => seen.push(now), SECOND);

		vi.advanceTimersByTime(2 * SECOND);

		expect(seen).toEqual([START + SECOND + 10 * SECOND, START + 2 * SECOND + 10 * SECOND]);
	});

	it("recomputes after a suspended tab rather than decrementing", () => {
		// Chrome fires no timer at all in a suspended tab, so a decrementing
		// counter wakes an hour stale. Recomputation is simply right.
		const seen = [];
		const resync = vi.fn();
		onResync(resync);
		subscribe((now) => seen.push(now), SECOND);

		vi.setSystemTime(START + 60 * 60 * SECOND);
		vi.advanceTimersByTime(SECOND);

		expect(seen.at(-1)).toBe(Date.now());
		expect(resync).toHaveBeenCalledTimes(1);
	});

	it("leaves no timer behind once the last subscriber goes", () => {
		const first = subscribe(() => {}, SECOND);
		const second = subscribe(() => {}, SECOND);
		expect(vi.getTimerCount()).toBe(1);

		first();
		expect(vi.getTimerCount()).toBe(1);
		second();
		expect(vi.getTimerCount()).toBe(0);
	});
});
