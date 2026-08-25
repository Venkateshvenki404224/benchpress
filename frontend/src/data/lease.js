import { refreshCreditSummary } from "@/data/credits";
import { createResource } from "frappe-ui";
import { reactive } from "vue";

/**
 * Buying more time.
 *
 * The catalog is the same for everyone, so it is fetched once per session. The
 * renewal itself carries a `request_id` the client generates and *keeps* across
 * retries: the server charges once per id, so a second click, a retried request
 * or a third tab costs nothing extra. Dropping the id on retry would defeat the
 * whole guard, which is why `renewBench` takes one rather than making one.
 *
 * Nothing here is optimistic. A renewal spends credits and may start a
 * container, and both can fail — so the countdown moves when the server says it
 * moved, from this response or from the `lease_renewed` push.
 */

export const leasePlans = reactive({ loaded: false, plans: [] });

export const leasePlansResource = createResource({
	url: "/api/method/benchpress.api.get_lease_plans",
	transform: (data) => data?.message ?? data,
	onSuccess(plans) {
		leasePlans.loaded = true;
		leasePlans.plans = plans ?? [];
	},
});

export const renewResource = createResource({
	url: "benchpress.api.renew_bench",
	transform: (data) => data?.message ?? data,
});

export function loadLeasePlans() {
	if (!leasePlans.loaded) leasePlansResource.fetch();
}

/** Renew one bench. Resolves with the server's new lease state. */
export async function renewBench({ benchName, plan, requestId }) {
	const renewed = await renewResource.submit({
		bench_name: benchName,
		plan,
		request_id: requestId,
	});
	refreshCreditSummary();
	return renewed;
}

/** A fresh idempotency key, made once per dialog rather than once per click. */
export function newRequestId() {
	return crypto.randomUUID();
}
