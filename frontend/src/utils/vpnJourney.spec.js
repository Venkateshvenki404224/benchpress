import { describe, expect, it } from "vitest";
import { ADD_DEVICE, RECHECK, bannerState, formatBytes, transferLabel } from "./vpnJourney";

describe("transfer counters", () => {
	it("reads whole bytes below a kilobyte and one decimal above it", () => {
		expect(formatBytes(0)).toBe("0 B");
		expect(formatBytes(512)).toBe("512 B");
		expect(formatBytes(1024)).toBe("1.0 KB");
		expect(formatBytes(1_503_238_553)).toBe("1.4 GB");
	});

	it("never invents a number from a missing counter", () => {
		// A peer the poller has never seen has null counters, not zeroed ones.
		for (const value of [null, undefined, "", Number.NaN, -5]) {
			expect(formatBytes(value)).toBe("0 B");
		}
	});

	it("labels both directions on one line", () => {
		expect(transferLabel(1024, 2048)).toBe("1.0 KB ↓ / 2.0 KB ↑");
	});
});

describe("the status banner", () => {
	it("names the handshake age when the tunnel is up", () => {
		const banner = bannerState({ connected: true, handshakeAgeSeconds: 14, deviceCount: 1 });

		expect(banner).toMatchObject({
			tone: "green",
			title: "WireGuard is up on this device",
			action: RECHECK,
		});
		expect(banner.body).toContain("Handshake 14s ago");
	});

	it("stays green without claiming an age it does not have", () => {
		const banner = bannerState({ connected: true, handshakeAgeSeconds: null, deviceCount: 1 });

		expect(banner.tone).toBe("green");
		expect(banner.body).not.toContain("ago");
	});

	it("offers registration when the account has no device at all", () => {
		expect(bannerState({ connected: false, deviceCount: 0 })).toMatchObject({
			tone: "amber",
			title: "This device is not on the VPN",
			action: ADD_DEVICE,
			actionLabel: "Add this device",
		});
	});

	it("says the devices exist but are quiet, rather than asking for another", () => {
		const banner = bannerState({ connected: false, deviceCount: 2 });

		expect(banner.action).toBe(RECHECK);
		expect(banner.body).toContain("2 machines registered");
	});

	it("counts one machine in the singular", () => {
		expect(bannerState({ connected: false, deviceCount: 1 }).body).toContain("1 machine ");
	});

	it("treats an unanswered status as disconnected", () => {
		expect(bannerState().tone).toBe("amber");
	});
});
