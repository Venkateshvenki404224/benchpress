import { createResource } from "frappe-ui";

export const deployHistoryResource = createResource({
	url: "/api/method/benchpress.api.get_deploy_history",
	transform(data) {
		return data?.message ?? data;
	},
});
