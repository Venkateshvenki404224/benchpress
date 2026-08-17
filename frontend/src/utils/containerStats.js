/**
 * How the container status card reports CPU, memory and health.
 *
 * `get_container_stats` writes zeros on any failure, so a stopped container
 * and a genuinely idle one persist identical numbers. Rendering "0%" for a
 * container that is not running is therefore a claim the data cannot support:
 * these meters read em-dash with a "container not running" caption instead,
 * and only a running container is allowed to report a percentage.
 *
 * The meters return the shape `UsageBar` renders, so the Instances table and
 * this card share one bar.
 */

import { percent, shortAge } from "@/utils/benchUsage";
import { cpuLabel, memoryLabel } from "@/utils/labSpecs";

export const NOT_RUNNING_NOTE = "container not running";
export const NO_READING = "—";
export const NEVER_CHECKED = "never checked";
// Memory turns amber here — the design's warning threshold.
export const MEMORY_WARNING_PERCENT = 60;

/** CPU against the lab's core quota. */
export function cpuMeter(bench, lab) {
	if (!isRunning(bench)) return idleMeter();
	const value = percent(bench.cpu_usage);
	return {
		label: `${value}%`,
		note: `quota ${cpuLabel(lab?.cpu_cores)}`,
		value,
		tone: "green",
	};
}

/** Memory as a share of the lab's limit, amber once it runs hot. */
export function memoryMeter(bench, lab) {
	if (!isRunning(bench)) return idleMeter();
	const value = percent(bench.memory_usage);
	return {
		label: `${value}%`,
		note: memoryNote(lab),
		value,
		tone: value > MEMORY_WARNING_PERCENT ? "orange" : "green",
	};
}

function memoryNote(lab) {
	const limit = memoryLabel(lab?.memory_limit);
	return limit ? `of ${limit} limit` : "of the lab's limit";
}

function idleMeter() {
	return { label: NO_READING, note: NOT_RUNNING_NOTE, value: 0, tone: "gray" };
}

function isRunning(bench) {
	return bench?.status === "Running";
}

/**
 * How old the health reading is.
 *
 * The age arrives already resolved to seconds so this module stays free of the
 * date layer, exactly as `benchUsage` does.
 *
 * @param {number|null} ageSeconds Age of `last_health_check`, null if never polled.
 */
export function healthCaption(ageSeconds) {
	if (ageSeconds === null || ageSeconds === undefined) return NEVER_CHECKED;
	return `checked ${shortAge(ageSeconds)} ago`;
}
