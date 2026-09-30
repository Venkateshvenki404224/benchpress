/** Sentinel filter value meaning "no filter applied". */
export const ALL = "__all__";

/** "All" plus each value actually present, so no filter offers an empty result. */
export function optionsFrom(label, values, labelFor = (value) => value) {
	const present = [...new Set(values.filter(Boolean))].sort();
	return [
		{ label: `${label}: all`, value: ALL },
		...present.map((value) => ({ label: labelFor(value), value })),
	];
}

/** A list value matches when any member does. */
export function matches(value, filter) {
	if (filter === ALL) return true;
	return Array.isArray(value) ? value.includes(filter) : value === filter;
}

/** True when the query is blank or any value contains it, ignoring case. */
export function matchesSearch(values, query) {
	const needle = query.trim().toLowerCase();
	return !needle || values.some((value) => (value || "").toLowerCase().includes(needle));
}
