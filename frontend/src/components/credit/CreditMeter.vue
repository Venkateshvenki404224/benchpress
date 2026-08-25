<template>
	<router-link
		to="/credits"
		class="block rounded-card transition-colors hover:bg-surface-gray-2"
		:class="[
			// Collapsed, the rail is a column of bare icons and a card would shout; expanded, the
			// meter is the only figure in the sidebar and earns its own surface.
			isCollapsed
				? 'px-1.5 py-1.5'
				: 'border border-outline-gray-1 bg-surface-white px-2.5 py-2',
			isActive ? '!bg-surface-selected shadow-nav-active' : '',
		]"
		:aria-label="`Credits — ${tooltip}`"
		data-test="credit-meter"
	>
		<Tooltip :text="tooltip" placement="right">
			<div v-if="isCollapsed" class="flex flex-col items-center gap-2">
				<CoinsIcon class="size-4 text-ink-gray-6" />
				<Progress class="w-5" :class="fillClass" size="sm" :value="meter.value" />
			</div>

			<div v-else class="min-w-0">
				<p class="text-2xs text-ink-gray-5">Credits</p>
				<div class="mt-0.5 flex items-baseline gap-1.5">
					<span
						class="truncate text-lg font-semibold tabular-nums"
						:class="balanceClass"
						data-test="credit-meter-balance"
					>
						{{ meter.balanceLabel }}
					</span>
					<span class="truncate text-2xs tabular-nums text-ink-gray-4">
						of {{ meter.allocatedLabel }}
					</span>
				</div>
				<Progress class="mt-1.5" :class="fillClass" size="sm" :value="meter.value" />
			</div>
		</Tooltip>
	</router-link>
</template>

<script setup>
// The balance is the one number a user wants in view while they work, so it lives at the foot of
// the sidebar beside the collapse control rather than in the nav proper — it is an account meter,
// not a destination. The statement it links to *is* a destination, and stays a page: a ledger read
// in a 240px column would be neither readable nor pageable.
//
// The bar empties rather than fills. Its denominator is everything ever allocated to the account
// and its fill is what is left, which is the shape of a fuel gauge and reads the same way at a
// glance: full is fine, a sliver is not.
import { creditSummary } from "@/data/credits";
import { creditMeter } from "@/utils/credits";
import { TONES, fillFor } from "@/utils/statusThemes";
import { Progress, Tooltip } from "frappe-ui";
import { computed } from "vue";
import { useRoute } from "vue-router";

import CoinsIcon from "~icons/lucide/coins";

// A green gauge needs no colouring — the figure reads as ink until the tank is low, and only then
// does it take the warning tone the bar has already gone.
const WARNING_TONES = new Set(["orange", "red"]);

const props = defineProps({
	// The sidebar's own collapse state, handed down by its `footer-items` slot.
	isCollapsed: { type: Boolean, default: false },
});

const route = useRoute();

const meter = computed(() =>
	creditMeter(creditSummary.balance, creditSummary.allocated, creditSummary.isSuspended)
);

const isActive = computed(() => route.name === "Credits");
const fillClass = computed(() => fillFor(meter.value.tone));

const balanceClass = computed(() =>
	WARNING_TONES.has(meter.value.tone) ? TONES[meter.value.tone].text : "text-ink-gray-9"
);

/** What the collapsed rail cannot show: the figures behind the bar. */
const tooltip = computed(() => meter.value.label);
</script>
