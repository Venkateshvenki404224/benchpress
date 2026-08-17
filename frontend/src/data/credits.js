import { userContext } from "@/data/userContext";
import { createResource } from "frappe-ui";
import { computed, reactive } from "vue";

/**
 * The credit surfaces, all behind one gate.
 *
 * `get_user_context` already carries `credits.enabled` — the same switch the API
 * enforces — so nothing here asks the server whether credits exist. When the
 * switch is off the chip and the statement route never render, and neither
 * resource is ever fetched.
 *
 * The balance is never summed from the ledger: `get_credit_summary` returns the
 * stored balance minus the burn accrued since it was settled, which is why a
 * refresh is one indexed read and can be called on navigation without cost.
 */

export const creditsEnabled = computed(() => userContext.credits?.enabled === true);

export const creditSummary = reactive({
	balance: 0,
	burnRate: 0,
	isSuspended: false,
});

export const creditSummaryResource = createResource({
	url: "/api/method/benchpress.api.get_credit_summary",
	transform(data) {
		return data?.message ?? data;
	},
	onSuccess(summary) {
		creditSummary.balance = summary?.balance ?? 0;
		creditSummary.burnRate = summary?.burn_rate ?? 0;
		creditSummary.isSuspended = summary?.is_suspended ?? false;
	},
});

export const creditStatementResource = createResource({
	url: "/api/method/benchpress.api.get_credit_statement",
	transform(data) {
		return data?.message ?? data;
	},
});

/** Seed the chip from the context call the SPA already made, then keep it fresh. */
export function primeCreditSummary() {
	if (!creditsEnabled.value) return;
	creditSummary.balance = userContext.credits?.balance ?? 0;
	creditSummary.burnRate = userContext.credits?.burn_rate ?? 0;
	creditSummary.isSuspended = userContext.credits?.is_suspended ?? false;
}

export function refreshCreditSummary() {
	if (!creditsEnabled.value) return;
	creditSummaryResource.reload();
}

export function loadStatement(limitStart = 0, limitPageLength = 20) {
	return creditStatementResource.submit({
		limit_start: limitStart,
		limit_page_length: limitPageLength,
	});
}
