import { createResource } from "frappe-ui";

/**
 * The session user's device peers. Bench container peers share `owner_user`
 * with them and are excluded server-side — never filter that here.
 */
export const devicesResource = createResource({
	url: "/api/method/benchpress.api.list_devices",
	auto: true,
	transform(data) {
		return data?.message ?? data ?? [];
	},
});

/** The types `register_device` accepts, so no screen hand-types the list. */
export const deviceTypesResource = createResource({
	url: "/api/method/benchpress.api.get_device_types",
	auto: true,
	transform(data) {
		return data?.message ?? data ?? [];
	},
});

/** The user-facing tunnel test — their own peer, not the shared infrastructure. */
export const connectionTestResource = createResource({
	url: "/api/method/benchpress.api.run_connection_test",
	transform(data) {
		return data?.message ?? data ?? [];
	},
});

export async function reloadDevices() {
	await devicesResource.reload();
}
