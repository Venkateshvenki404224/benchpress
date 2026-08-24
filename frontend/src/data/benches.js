import { createListResource } from "frappe-ui";

// Row-level scoping is the server's job: `bench_instance_query_conditions`
// limits a BenchPress User to the benches they own, so this resource never
// filters by owner itself. `hasNextPage` is what the Instances page reads to
// say so when the page ceiling actually bites.
export const BENCH_PAGE_LENGTH = 100;

/**
 * The session user's bench instances — every bench for an admin. Shared by the
 * Instances table and the ⌘K palette.
 */
export const benchesResource = createListResource({
	doctype: "Bench Instance",
	fields: [
		"name",
		"bench_name",
		"lab",
		"frappe_version",
		"domain",
		"site_name",
		"status",
		"container_ip",
		"runtime",
		"wg_ip",
		"cpu_usage",
		"memory_usage",
		"container_health",
		"last_health_check",
		"owner",
	],
	orderBy: "creation desc",
	pageLength: BENCH_PAGE_LENGTH,
	// Deliberately not `auto` — a list resource created at module scope does not
	// fetch on its own in frappe-ui 0.1.278. Every consumer reloads it.
	auto: false,
});

/** Rows as an array, whatever state the resource is in. */
export function benchRows() {
	return benchesResource.data ?? [];
}
