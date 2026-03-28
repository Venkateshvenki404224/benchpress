import { createResource } from "frappe-ui";
import { computed, reactive } from "vue";

const userContextResource = createResource({
	url: "benchpress.api.get_user_context",
	auto: true,
	cache: "UserContext",
});

export const userContext = reactive({
	isAdmin: computed(() => userContextResource.data?.is_admin ?? false),
	user: computed(() => userContextResource.data?.user ?? ""),
	roles: computed(() => userContextResource.data?.roles ?? []),
	loading: computed(() => !userContextResource.data && userContextResource.loading),
	ready: computed(() => !!userContextResource.data),
});

/** Wait until the user context API has resolved. Call in router guards. */
export function waitForUserContext() {
	if (userContextResource.data) return Promise.resolve();
	return userContextResource.promise;
}
