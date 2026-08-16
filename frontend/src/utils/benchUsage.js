/**
 * How an Instances row reports CPU and memory.
 *
 * `stats_collector` writes `cpu_usage` and `memory_usage` every minute, and
 * `get_container_stats` returns zeros on *any* failure — so a zero reading is
 * indistinguishable from an idle container unless it is shown next to the age
 * of the reading. Everything here exists to keep those three cases apart:
 * never measured, measured recently, and a reading too old to trust.
 *
 * Ages arrive already resolved to seconds so this module stays free of the
 * date layer and remains directly testable.
 */

// The stats sweep is a `*/1` cron, so a reading older than three ticks is
// either a dead sweep or a container Docker stopped answering for.
export const STALE_AFTER_SECONDS = 180;

export const NEVER_MEASURED_NOTE = "never measured";

/**
 * The CPU/memory cell for a bench.
 *
 * @param {object} bench Bench Instance row.
 * @param {number|null} readingAgeSeconds Age of `last_health_check`, or null
 *   when the bench has never been polled.
 * @returns {{label: string, note: string, value: number, tone: string,
 *   measured: boolean, stale: boolean}}
 */
export function usageFor(bench, readingAgeSeconds) {
	const measured = readingAgeSeconds !== null && readingAgeSeconds !== undefined;
	const stale = measured && readingAgeSeconds > STALE_AFTER_SECONDS;
	const trusted = measured && !stale;
	return {
		measured,
		stale,
		label: trusted ? usageLabel(bench) : "—",
		note: usageNote(measured, stale, readingAgeSeconds),
		value: trusted ? percent(bench.cpu_usage) : 0,
		tone: trusted && percent(bench.cpu_usage) > 0 ? "green" : "gray",
	};
}

function usageLabel(bench) {
	return `${percent(bench.cpu_usage)}% CPU · ${percent(bench.memory_usage)}% mem`;
}

function usageNote(measured, stale, readingAgeSeconds) {
	if (!measured) return NEVER_MEASURED_NOTE;
	if (stale) return `stale — last read ${describeAge(readingAgeSeconds)} ago`;
	return "";
}

function describeAge(seconds) {
	const minutes = Math.round(seconds / 60);
	if (minutes < 60) return `${minutes}m`;
	const hours = Math.round(minutes / 60);
	return hours < 24 ? `${hours}h` : `${Math.round(hours / 24)}d`;
}

/** A stats float as a whole percentage, clamped to the bar's range. */
export function percent(value) {
	const number = Number(value);
	if (!Number.isFinite(number)) return 0;
	return Math.min(100, Math.max(0, Math.round(number)));
}
