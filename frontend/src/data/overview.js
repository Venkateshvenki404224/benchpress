import { createResource } from "frappe-ui";

/** The whole Overview screen in one call. */
export const overviewResource = createResource({
	url: "/api/method/benchpress.api.get_overview",
	auto: true,
	transform(data) {
		return data?.message ?? data;
	},
});
