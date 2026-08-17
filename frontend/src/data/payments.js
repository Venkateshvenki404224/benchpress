import { creditsEnabled, refreshCreditSummary } from "@/data/credits";
import { userContext } from "@/data/userContext";
import { createResource, toast } from "frappe-ui";
import { reactive } from "vue";

/**
 * Buying, end to end.
 *
 * The order is always opened by our own API, never by Razorpay's `/razorpay-api/initiate-order`
 * endpoint, even though that endpoint exists and would be one call shorter. That one takes the
 * amount from the caller — this one takes it from the Credit Pack — and the server settles a
 * payment only against a price it set itself.
 *
 * Razorpay's checkout script is fetched the first time somebody actually buys something, not from
 * `index.html`. A site with credits switched off, or with no gateway installed, therefore never
 * loads a third-party script at all.
 *
 * Neither half of this decides whether the balance moved. `handler` reports the payment to the
 * server, the server credits it, and the chip is then re-read from the server. If the browser is
 * closed between paying and reporting, the `payment.captured` webhook settles the same order
 * instead — both paths land on one idempotent write.
 */

const CHECKOUT_JS = "https://checkout.razorpay.com/v1/checkout.js";
const CHECKOUT_NAME = "BenchPress";

export const purchaseOptions = reactive({
	loaded: false,
	available: false,
	packs: [],
	alwaysOnInr: 0,
	alwaysOnDays: 30,
});

export const purchaseOptionsResource = createResource({
	url: "/api/method/benchpress.api.get_purchase_options",
	transform: (data) => data?.message ?? data,
	onSuccess(options) {
		purchaseOptions.loaded = true;
		purchaseOptions.available = options?.payments_available === true;
		purchaseOptions.packs = options?.packs ?? [];
		purchaseOptions.alwaysOnInr = options?.always_on_inr ?? 0;
		purchaseOptions.alwaysOnDays = options?.always_on_days ?? 30;
	},
});

export const buyCreditsResource = createResource({
	url: "benchpress.api.buy_credits",
	transform: (data) => data?.message ?? data,
});

export const buyPassResource = createResource({
	url: "benchpress.api.buy_always_on_pass",
	transform: (data) => data?.message ?? data,
});

const confirmResource = createResource({ url: "/razorpay-api/success-handler" });
const abandonResource = createResource({ url: "/razorpay-api/failure-handler" });

/** Prices are the same for everyone, so they are fetched once per session. */
export function loadPurchaseOptions() {
	if (!creditsEnabled.value || purchaseOptions.loaded) return;
	purchaseOptionsResource.reload();
}

export async function buyPack(pack) {
	const order = await buyCreditsResource.submit({ pack });
	return checkout(order, `${pack} added to your balance.`);
}

export async function buyAlwaysOnPass(benchName, label) {
	const order = await buyPassResource.submit({ bench_name: benchName });
	return checkout(order, `${label} is always on for ${purchaseOptions.alwaysOnDays} days.`);
}

/**
 * Open Razorpay's checkout and resolve to whether it was paid.
 *
 * A dismissed modal resolves `false` rather than throwing: closing a payment window is a decision,
 * not an error, and nothing was charged either way.
 */
async function checkout(order, paidMessage) {
	await loadCheckoutScript();
	return new Promise((resolve) => {
		const razorpay = new window.Razorpay({
			key: order.key_id,
			order_id: order.order_id,
			amount: order.amount * 100,
			currency: order.currency,
			name: CHECKOUT_NAME,
			description: order.description,
			prefill: { email: userContext.user },
			modal: { ondismiss: () => resolve(false) },
			handler: async (response) => {
				await confirmPayment(response);
				toast.success(paidMessage);
				refreshCreditSummary();
				resolve(true);
			},
		});
		razorpay.on("payment.failed", (response) => {
			abandon(response?.error?.metadata?.order_id);
			toast.error("That payment did not go through. Nothing was charged.");
			resolve(false);
		});
		razorpay.open();
	});
}

/**
 * Tell the server the payment succeeded — which is what marks the order Paid and credits it.
 *
 * A failure here is reported but not raised: the money has already moved, and the webhook settles
 * the same order shortly afterwards, so the one thing that must not happen is the user being told
 * their payment failed.
 */
async function confirmPayment(response) {
	try {
		await confirmResource.submit({
			order_id: response.razorpay_order_id,
			payment_id: response.razorpay_payment_id,
			signature: response.razorpay_signature,
		});
	} catch (error) {
		console.error("Could not confirm the payment; the webhook will settle it.", error);
	}
}

function abandon(orderId) {
	if (!orderId) return;
	abandonResource.submit({ order_id: orderId }).catch(() => {});
}

let checkoutScript = null;

function loadCheckoutScript() {
	if (window.Razorpay) return Promise.resolve();
	if (!checkoutScript) {
		checkoutScript = new Promise((resolve, reject) => {
			const tag = document.createElement("script");
			tag.src = CHECKOUT_JS;
			tag.onload = resolve;
			tag.onerror = () => {
				checkoutScript = null;
				reject(new Error("Razorpay checkout could not be loaded."));
			};
			document.head.appendChild(tag);
		});
	}
	return checkoutScript;
}
