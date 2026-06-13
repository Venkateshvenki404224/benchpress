import router from "@/router";
import { useCall } from "frappe-ui";
import { computed, reactive } from "vue";

import { userResource } from "./user";

export function sessionUser() {
	const cookies = new URLSearchParams(document.cookie.split("; ").join("&"));
	let _sessionUser = cookies.get("user_id");
	if (_sessionUser === "Guest") {
		_sessionUser = null;
	}
	return _sessionUser;
}

export const session = reactive({
	login: useCall({
		url: "/api/method/login",
		method: "POST",
		immediate: false,
		onSuccess(data) {
			userResource.reload();
			session.user = sessionUser();
			session.login.reset();
			router.replace(data?.default_route || "/");
		},
	}),
	logout: useCall({
		url: "/api/v2/method/logout",
		method: "POST",
		immediate: false,
		onSuccess() {
			userResource.reset();
			session.user = sessionUser();
			window.location.href = "/login";
		},
	}),
	user: sessionUser(),
	isLoggedIn: computed(() => !!session.user),
});
