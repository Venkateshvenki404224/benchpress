import { useCall } from "frappe-ui";

export const userResource = useCall({
	url: "/api/v2/method/frappe.auth.get_logged_user",
	method: "GET",
	immediate: true,
	cacheKey: "User",
	onError(error) {
		if (error?.type === "AuthenticationError") {
			window.location.href = "/login";
		}
	},
});
