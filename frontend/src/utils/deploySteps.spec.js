import { describe, expect, it } from "vitest";
import {
	ACTIVE,
	DEPLOY_STEPS,
	DONE,
	FAILED,
	PENDING,
	classifyLine,
	deriveRun,
	formatDuration,
	parseStepLine,
	stepTiming,
} from "./deploySteps";

/** A marker exactly as `deploy_pipeline.format_step_line` writes it. */
function marker(key, elapsed) {
	const index = DEPLOY_STEPS.findIndex((step) => step.key === key) + 1;
	const { label } = DEPLOY_STEPS[index - 1];
	return `=== Step ${index}/${DEPLOY_STEPS.length}: ${label} [${key} @${elapsed.toFixed(
		1
	)}s] ===`;
}

function stepsOf(log) {
	const byKey = new Map(deriveRun(log).steps.map((step) => [step.key, step]));
	return byKey;
}

const MID_RUN = [
	"=== Deploy started ===",
	marker("infrastructure", 0.2),
	"MariaDB reachable at benchpress-mariadb:3306",
	marker("image", 4.2),
	"Using cached lab image: benchpress/crm:version-16",
	marker("container", 6.2),
	marker("container_ip", 8.2),
	"container_ip 172.19.0.7",
].join("\n");

describe("a run still in flight", () => {
	it("marks the last emitted step active and everything after it pending", () => {
		const steps = stepsOf(MID_RUN);

		expect(steps.get("infrastructure").state).toBe(DONE);
		expect(steps.get("container").state).toBe(DONE);
		expect(steps.get("container_ip").state).toBe(ACTIVE);
		expect(steps.get("vpn_peer").state).toBe(PENDING);
		expect(steps.get("complete").state).toBe(PENDING);
	});

	it("measures a finished step as the gap to the step that followed it", () => {
		const steps = stepsOf(MID_RUN);

		expect(steps.get("infrastructure").elapsed).toBeCloseTo(4);
		expect(steps.get("image").elapsed).toBeCloseTo(2);
		// The active step has not ended, so it reports no duration at all
		// rather than a number that keeps growing on its own.
		expect(steps.get("container_ip").elapsed).toBeNull();
		expect(stepTiming(steps.get("container_ip"))).toBe("running");
	});

	it("carries the freshest line of a step as its detail", () => {
		const steps = stepsOf(MID_RUN);

		expect(steps.get("container_ip").detail).toBe("container_ip 172.19.0.7");
		expect(steps.get("image").detail).toBe(
			"Using cached lab image: benchpress/crm:version-16"
		);
		expect(steps.get("container").detail).toBe("");
	});

	it("reports the run as running", () => {
		expect(deriveRun(MID_RUN).state).toBe("running");
	});
});

describe("a launch that builds before it deploys", () => {
	// One job opens the Deploy Log, emits the image marker, builds, and only
	// then runs the pipeline — so step 2 is announced before step 1 is.
	const LAUNCH_BUILD = [
		"=== Deploy started ===",
		marker("image", 0.0),
		marker("infrastructure", 0.0),
	].join("\n");

	it("still reads forward when the image marker arrives before step one", () => {
		const run = deriveRun(LAUNCH_BUILD);
		const steps = new Map(run.steps.map((step) => [step.key, step]));

		expect(steps.get("infrastructure").state).toBe(DONE);
		expect(steps.get("image").state).toBe(ACTIVE);
		for (const step of DEPLOY_STEPS.slice(2)) {
			expect(steps.get(step.key).state).toBe(PENDING);
		}
		expect(run.state).toBe("running");
	});

	it("reads a build that broke as a failed run, in the words the job used", () => {
		const run = deriveRun(
			`${LAUNCH_BUILD}\n=== Deploy failed: the lab image could not be built: boom ===`
		);

		expect(run.state).toBe("failed");
		expect(run.failure).toBe("the lab image could not be built: boom");
	});
});

describe("a run that finished", () => {
	const log = DEPLOY_STEPS.map((step, index) => marker(step.key, index * 20)).join("\n");

	it("marks every step done", () => {
		expect(deriveRun(log).steps.every((step) => step.state === DONE)).toBe(true);
	});

	it("reports the total the last marker recorded", () => {
		const run = deriveRun(log);

		expect(run.state).toBe("success");
		expect(run.totalElapsed).toBe(200);
		expect(stepTiming(run.steps.at(-1))).toBe("3m 20s");
	});
});

describe("a run that failed", () => {
	const log = [
		marker("infrastructure", 0.1),
		marker("image", 3.1),
		marker("container", 9.4),
		marker("container_ip", 11.0),
		marker("vpn_peer", 12.7),
		marker("site_config", 14.1),
		marker("site", 15.0),
		"bench new-site demo --install-app crm",
		"=== Deploy failed: bench new-site failed (exit 1): Access denied ===",
		"Cleanup: removed container created by this run",
	].join("\n");

	it("marks the step that broke, and no step after it", () => {
		const run = deriveRun(log);
		const steps = new Map(run.steps.map((step) => [step.key, step]));

		expect(steps.get("site").state).toBe(FAILED);
		expect(stepTiming(steps.get("site"))).toBe("failed");
		for (const key of ["assets", "ssh_user", "code_server", "complete"]) {
			expect(steps.get(key).state).toBe(PENDING);
		}
	});

	it("keeps the reason the run gave", () => {
		const run = deriveRun(log);

		expect(run.state).toBe("failed");
		expect(run.failure).toBe("bench new-site failed (exit 1): Access denied");
	});
});

describe("a log the size ceiling truncated", () => {
	// Everything before the truncation marker is gone, so the early steps have
	// no marker of their own — but a run cannot reach step 8 without them.
	const log = [
		"=== log truncated ===",
		marker("assets", 240.0),
		"bench build finished",
		marker("ssh_user", 301.5),
	].join("\n");

	it("infers the steps whose lines were dropped as done", () => {
		const steps = stepsOf(log);

		expect(steps.get("infrastructure").state).toBe(DONE);
		expect(steps.get("site").state).toBe(DONE);
		expect(steps.get("ssh_user").state).toBe(ACTIVE);
	});

	it("claims no duration for a step whose marker was dropped", () => {
		const steps = stepsOf(log);

		expect(steps.get("site").elapsed).toBeNull();
		expect(stepTiming(steps.get("site"))).toBe("—");
		expect(steps.get("assets").elapsed).toBeCloseTo(61.5);
	});
});

describe("a log from before the pipeline emitted steps", () => {
	const log = [
		"=== Deploy started ===",
		"=== Creating container ===",
		"=== Deploy complete ===",
	].join("\n");

	it("says it has no step data instead of showing eleven empty rows", () => {
		const run = deriveRun(log);

		expect(run.structured).toBe(false);
		expect(run.steps.every((step) => step.state === PENDING)).toBe(true);
	});

	it("still counts its lines for the raw log panel", () => {
		expect(deriveRun(log).lineCount).toBe(3);
	});
});

describe("parseStepLine", () => {
	it("reads the metadata out of a marker", () => {
		expect(parseStepLine(marker("vpn_peer", 12.7))).toMatchObject({
			key: "vpn_peer",
			index: 5,
			total: 11,
			label: "Configuring the WireGuard peer",
			elapsed: 12.7,
		});
	});

	it("ignores a plain line and a legacy marker", () => {
		expect(parseStepLine("Building assets...")).toBeNull();
		expect(parseStepLine("=== Creating container ===")).toBeNull();
	});
});

describe("classifyLine", () => {
	it("colours the raw log by what the line is", () => {
		expect(classifyLine(marker("site", 15))).toBe("step");
		expect(classifyLine(marker("complete", 200))).toBe("success");
		expect(classifyLine("=== Deploy failed: boom ===")).toBe("error");
		expect(classifyLine("ERROR: docker build exited 1")).toBe("error");
		expect(classifyLine("=== Build complete: benchpress/crm ===")).toBe("success");
		expect(classifyLine("cloning frappe…")).toBe("info");
	});
});

describe("formatDuration", () => {
	it("reads in the largest unit that fits", () => {
		expect(formatDuration(0.4)).toBe("0s");
		expect(formatDuration(42)).toBe("42s");
		expect(formatDuration(188)).toBe("3m 8s");
		expect(formatDuration(null)).toBe("");
	});
});
