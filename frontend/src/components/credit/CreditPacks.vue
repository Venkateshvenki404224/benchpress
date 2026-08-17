<template>
	<SectionCard title="Buy credits" data-test="credit-packs">
		<p v-if="!purchaseOptions.available" class="text-body text-ink-gray-5">
			Payments are not set up on this site, so credits can only be granted by the operator.
		</p>

		<template v-else-if="purchaseOptions.packs.length">
			<div
				class="grid gap-2"
				style="grid-template-columns: repeat(auto-fit, minmax(180px, 1fr))"
			>
				<button
					v-for="pack in purchaseOptions.packs"
					:key="pack.name"
					type="button"
					class="rounded-card border px-3 py-2.5 text-left transition-colors disabled:opacity-60"
					:class="
						pack.highlight
							? 'border-outline-gray-4 bg-surface-gray-2 hover:bg-surface-gray-3'
							: 'border-outline-gray-1 bg-surface-white hover:bg-surface-gray-1'
					"
					:disabled="busy"
					:data-test="`credit-pack-${pack.name}`"
					@click="buy(pack)"
				>
					<span class="flex items-baseline justify-between gap-2">
						<span class="text-xs font-medium text-ink-gray-9">{{
							pack.pack_label
						}}</span>
						<span class="text-2xs text-ink-gray-5">{{ rupees(pack.inr_price) }}</span>
					</span>
					<span class="mt-1 block text-body font-semibold text-ink-gray-9">
						{{ creditLabel(pack.credits) }} credits
					</span>
					<span class="mt-0.5 block text-2xs text-ink-gray-5">{{
						perCredit(pack)
					}}</span>
				</button>
			</div>

			<ErrorMessage v-if="error" class="mt-2" :message="error" />
		</template>

		<p v-else class="text-body text-ink-gray-5">Nothing is on sale right now.</p>
	</SectionCard>
</template>

<script setup>
// Prices are read from Desk, never hard-coded here — the same `Credit Pack` rows the landing page
// quotes and the server settles against. A pack card is a button rather than a form: there is one
// decision to make and the amount is not one of it.
import SectionCard from "@/components/SectionCard.vue";
import { buyPack, loadPurchaseOptions, purchaseOptions } from "@/data/payments";
import { creditLabel } from "@/utils/credits";
import { ErrorMessage } from "frappe-ui";
import { onMounted, ref } from "vue";

const emit = defineEmits(["bought"]);

const busy = ref(false);
const error = ref("");

onMounted(loadPurchaseOptions);

async function buy(pack) {
	busy.value = true;
	error.value = "";
	try {
		if (await buyPack(pack.name)) emit("bought");
	} catch (failure) {
		error.value =
			failure?.messages?.[0] || failure?.message || "That purchase could not be started.";
	} finally {
		busy.value = false;
	}
}

function rupees(price) {
	return `₹${Number(price ?? 0).toLocaleString("en-IN")}`;
}

/** What a credit costs in this pack, which is the only way to compare two packs honestly. */
function perCredit(pack) {
	const credits = Number(pack.credits ?? 0);
	if (!credits) return "";
	return `₹${(Number(pack.inr_price ?? 0) / credits).toFixed(2)} per credit`;
}
</script>
