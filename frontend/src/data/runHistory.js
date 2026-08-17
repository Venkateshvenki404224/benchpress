import { createResource } from "frappe-ui";

/**
 * Build and deploy history.
 *
 * Both go through whitelisted endpoints rather than a generic list read: `Build
 * Log` carries no permission query condition, so reading it through
 * `frappe.client.get_list` served every user every other user's image builds.
 * `benchpress/run_history.py` scopes both and derives the last step and the
 * duration each run recorded.
 */

export const buildHistoryResource = createResource({
	url: "/api/method/benchpress.api.get_build_history",
	transform(data) {
		return data?.message ?? data;
	},
});

export const deployHistoryResource = createResource({
	url: "/api/method/benchpress.api.get_deploy_history",
	transform(data) {
		return data?.message ?? data;
	},
});
