import { useCall } from "frappe-ui";
import { reactive } from "vue";

export const userContext = reactive({
	isAdmin: false,
	user: "",
	roles: [],
	loading: true,
	ready: false,
});

const userContextResource = useCall({
	url: "/api/v2/method/benchpress.api.get_user_context",
	method: "GET",
	immediate: true,
	cacheKey: "UserContext",
	onSuccess(data) {
		const ctx = data?.message ?? data;
		userContext.isAdmin = ctx?.is_admin ?? false;
		userContext.user = ctx?.user ?? "";
		userContext.roles = ctx?.roles ?? [];
		userContext.loading = false;
		userContext.ready = true;
	},
	onError() {
		userContext.loading = false;
	},
});

export function waitForUserContext() {
	if (userContext.ready) return Promise.resolve();
	return userContextResource.promise;
}
