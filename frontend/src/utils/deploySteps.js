/**
 * The deploy pipeline as the screen reads it.
 *
 * Every step state here is derived from lines the backend actually emitted —
 * `benchpress/deploy_pipeline.py` writes one `=== Step i/11: … [key @12.3s] ===`
 * marker per boundary, and this module turns a log into a stepper. Nothing is
 * timed in the browser: the prototype advanced a fake step every 520ms, and a
 * progress bar that moves while the server is stuck is worse than none.
 *
 * The same derivation serves a live stream, a page reloaded mid-run and a run
 * opened from history months later, because all three are the same string.
 *
 * `DEPLOY_STEPS` mirrors `DEPLOY_STEPS` in `benchpress/deploy_pipeline.py`,
 * including the order — the WireGuard peer is step 5 because the code
 * configures it there, whatever DESIGN_BRIEF §4 says. Keys are the contract;
 * a key that changes on one side must change on the other.
 */

export const DEPLOY_STEPS = [
	{ key: "infrastructure", label: "Checking shared infrastructure" },
	{ key: "image", label: "Preparing the lab image" },
	{ key: "container", label: "Creating the container" },
	{ key: "container_ip", label: "Waiting for the container IP" },
	{ key: "vpn_peer", label: "Configuring the WireGuard peer" },
	{ key: "site_config", label: "Writing common_site_config.json" },
	{ key: "site", label: "Creating the site" },
	{ key: "assets", label: "Building assets" },
	{ key: "ssh_user", label: "Provisioning the SSH user" },
	{ key: "code_server", label: "Provisioning code-server" },
	{ key: "complete", label: "Deploy complete" },
];

export const COMPLETE_KEY = "complete";

export const DONE = "done";
export const ACTIVE = "active";
export const PENDING = "pending";
export const FAILED = "failed";

const STEP_LINE = /^===\s*Step\s+(\d+)\/(\d+):\s*(.*?)\s*\[([a-z_]+)\s*@(\d+(?:\.\d+)?)s\]\s*===$/;
const FAILED_LINE = /^===\s*(?:Deploy|Build) failed:\s*(.*?)\s*===$/;
const MARKER_LINE = /^===.*===$/;
const ERROR_LINE = /^(ERROR|Traceback)/;

/** The step a line opens, or null when it opens no step. */
export function parseStepLine(line) {
	const match = STEP_LINE.exec(String(line ?? "").trim());
	if (!match) return null;
	return {
		index: Number(match[1]),
		total: Number(match[2]),
		label: match[3],
		key: match[4],
		elapsed: Number(match[5]),
	};
}

/** What a raw log line is, for colour only — the persisted log is one blob. */
export function classifyLine(line) {
	const text = String(line ?? "").trim();
	if (FAILED_LINE.test(text) || ERROR_LINE.test(text)) return "error";
	const step = parseStepLine(text);
	if (step) return step.key === COMPLETE_KEY ? "success" : "step";
	if (!MARKER_LINE.test(text)) return "info";
	return /complete/i.test(text) ? "success" : "step";
}

/**
 * The whole run: its steps, its outcome and how long it took.
 *
 * `structured` is false for a log written before the pipeline emitted step
 * markers. Those runs get no stepper at all rather than eleven grey rows,
 * which would read as "nothing has happened yet" about a finished deploy.
 */
export function deriveRun(rawLog) {
	const lines = String(rawLog ?? "").split("\n");
	const { observed, details, failure } = readLines(lines);
	const completed = observed.some((marker) => marker.key === COMPLETE_KEY);
	const totalElapsed = observed.length ? observed[observed.length - 1].elapsed : 0;

	return {
		structured: observed.length > 0,
		steps: buildSteps({ observed, details, failure, completed, totalElapsed }),
		failure,
		state: runState({ failure, completed, started: observed.length > 0 }),
		totalElapsed,
		lineCount: lines.filter((line) => line.trim()).length,
	};
}

function readLines(lines) {
	const observed = [];
	const details = new Map();
	let failure = "";

	for (const raw of lines) {
		const line = raw.trim();
		if (!line) continue;
		const failed = FAILED_LINE.exec(line);
		if (failed) {
			failure = failed[1];
			continue;
		}
		const marker = parseStepLine(line);
		if (marker) {
			observed.push(marker);
			continue;
		}
		// The freshest line inside a step is what that step is doing.
		if (observed.length && !MARKER_LINE.test(line)) {
			details.set(observed[observed.length - 1].key, line);
		}
	}
	return { observed, details, failure };
}

function buildSteps({ observed, details, failure, completed, totalElapsed }) {
	const byKey = new Map(observed.map((marker) => [marker.key, marker]));
	const reachedIndex = observed.reduce((highest, marker) => Math.max(highest, marker.index), 0);

	return DEPLOY_STEPS.map((step, position) => {
		const index = position + 1;
		const state = stateFor({ index, reachedIndex, failure, completed });
		return {
			...step,
			index,
			state,
			detail: details.get(step.key) ?? "",
			elapsed: state === DONE ? durationOf(step.key, byKey, observed, totalElapsed) : null,
		};
	});
}

/**
 * The pipeline is strictly sequential, so a marker at step 7 is proof steps
 * 1-6 finished even when the log no longer carries their lines — which is what
 * a run truncated at the size ceiling looks like. Nothing after the step that
 * failed is ever marked.
 */
function stateFor({ index, reachedIndex, failure, completed }) {
	if (index > reachedIndex) return PENDING;
	if (index < reachedIndex) return DONE;
	if (failure) return FAILED;
	return completed ? DONE : ACTIVE;
}

/** A step lasts until the next one opens; the last one reports the whole run. */
function durationOf(key, byKey, observed, totalElapsed) {
	if (key === COMPLETE_KEY) return totalElapsed;
	const marker = byKey.get(key);
	if (!marker) return null;
	const next = observed.find((candidate) => candidate.index > marker.index);
	return next ? Math.max(0, next.elapsed - marker.elapsed) : null;
}

function runState({ failure, completed, started }) {
	if (failure) return "failed";
	if (completed) return "success";
	return started ? "running" : "idle";
}

/** Seconds as the run reports them: "42s", "3m 8s". */
export function formatDuration(seconds) {
	if (seconds === null || seconds === undefined) return "";
	const whole = Math.round(seconds);
	if (whole < 60) return `${whole}s`;
	return `${Math.floor(whole / 60)}m ${whole % 60}s`;
}

/** The right-hand column of a step row. */
export function stepTiming(step) {
	if (step.state === ACTIVE) return "running";
	if (step.state === FAILED) return "failed";
	if (step.state === DONE) return formatDuration(step.elapsed) || "—";
	return "";
}
