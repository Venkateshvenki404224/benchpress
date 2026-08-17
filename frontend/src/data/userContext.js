import { createResource } from "frappe-ui";
import { reactive } from "vue";

export const userContext = reactive({
	isAdmin: false,
	user: "",
	roles: [],
	// `{enabled}` at minimum, plus the balance when credits are switched on. Every credit
	// surface hides behind this flag — the same gate the API enforces — so the SPA never
	// asks a second endpoint whether the feature exists.
	credits: { enabled: false },
	loading: true,
	ready: false,
});

const userContextResource = createResource({
	url: "/api/method/benchpress.api.get_user_context",
	auto: true,
	cache: "UserContext",
	onSuccess(data) {
		const ctx = data?.message ?? data;
		userContext.isAdmin = ctx?.is_admin ?? false;
		userContext.user = ctx?.user ?? "";
		userContext.roles = ctx?.roles ?? [];
		userContext.credits = ctx?.credits ?? { enabled: false };
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
