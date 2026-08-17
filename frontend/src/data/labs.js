import { createResource } from "frappe-ui";

/**
 * Every lab the session user may see, with its apps, its deployment and its
 * last run. Shared by the Labs table and the ⌘K palette so the palette never
 * issues a second, differently-scoped read.
 */
export const labsResource = createResource({
	url: "/api/method/benchpress.api.get_labs",
	auto: true,
	transform(data) {
		return data?.message ?? data;
	},
});

/** Rows as an array, whatever state the resource is in. */
export function labRows() {
	return labsResource.data ?? [];
}
