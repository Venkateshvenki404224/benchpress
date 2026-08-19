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

export function matches(value, filter) {
	return filter === ALL || value === filter;
}
