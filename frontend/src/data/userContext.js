import { createResource } from "frappe-ui";
import { reactive } from "vue";

export const userContext = reactive({
	isAdmin: false,
	user: "",
	roles: [],
	ready: false,
});

function setUserContext(ctx) {
	userContext.isAdmin = ctx?.is_admin ?? false;
	userContext.user = ctx?.user ?? "";
	userContext.roles = ctx?.roles ?? [];
	userContext.ready = true;
}

let userContextResource = null;

if (window.benchpress) {
	setUserContext(window.benchpress);
} else {
	// boot data is only injected in production builds; fetch in vite dev mode
	userContextResource = createResource({
		url: "/api/method/benchpress.api.get_user_context",
		auto: true,
		cache: "UserContext",
		onSuccess(data) {
			setUserContext(data?.message ?? data);
		},
	});
}

export function waitForUserContext() {
	if (userContext.ready) return Promise.resolve();
	return userContextResource ? userContextResource.promise : Promise.resolve();
}
