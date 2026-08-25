import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { anchorClock } from "./serverClock";
import { resetClock, serverNow } from "@/utils/clock";

const call = vi.fn();
vi.mock("frappe-ui", () => ({ call: (...args) => call(...args) }));

const NOW = 1_787_654_321_000;

beforeEach(() => {
	vi.useFakeTimers();
	vi.setSystemTime(NOW);
	resetClock();
	call.mockReset();
});

afterEach(() => {
	resetClock();
	vi.useRealTimers();
});

describe("anchoring the clock against the server", () => {
	it("takes the anchor as it arrives, in milliseconds", async () => {
		call.mockResolvedValue({ server_now_ms: NOW + 4000 });
		await anchorClock();
		expect(serverNow()).toBe(NOW + 4000);
	});

	// Seconds on the wire round the anchor down by up to a second, and `leaseFor` rounds the
	// remainder up again — a running lease then reads about 1.6s longer than it is.
	it("keeps the sub-second part rather than rounding the anchor down", async () => {
		call.mockResolvedValue({ server_now_ms: NOW + 1_800_940 });
		await anchorClock();
		expect(serverNow()).toBe(NOW + 1_800_940);
	});
});
